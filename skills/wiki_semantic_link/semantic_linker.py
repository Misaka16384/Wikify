import os
import sys
import json
import re
import shutil
import argparse
import hashlib
import urllib.request
import urllib.error
import numpy as np
import yaml
import subprocess
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

# Add bin/ directory to path for config_loader
_bin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bin")
if _bin_dir not in sys.path:
    sys.path.insert(0, _bin_dir)
from config_loader import load_config, get as cfg_get

def setup_argparse():
    parser = argparse.ArgumentParser(description="Wiki Semantic Linker using Ollama")
    parser.add_argument("topic_dir", help="Path to the root of the topic wiki (containing wiki/concepts/)")
    parser.add_argument("--threshold", type=float, default=None, help="Cosine similarity threshold for linking (default: from config.yaml)")
    parser.add_argument("--merge-threshold", type=float, default=None, help="Cosine similarity threshold for merge suggestions (default: from config.yaml)")
    parser.add_argument("--auto-merge", action="store_true", help="Automatically merge concepts with score >= auto-merge-threshold")
    parser.add_argument("--auto-merge-threshold", type=float, default=None, help="Cosine similarity threshold for auto-merging (default: from config.yaml)")
    parser.add_argument("--dedup-only", action="store_true", help="Only output merge suggestions, do not inject links.")
    parser.add_argument("--update-cache-only", action="store_true", help="Only update the embedding cache and exit. Skips all similarity calculations.")
    parser.add_argument("--model", type=str, default=None, help="Ollama embedding model to use (default: from config.yaml)")
    parser.add_argument("--ollama-url", type=str, default=None, help="Ollama API endpoint (default: from config.yaml)")
    args = parser.parse_args()

    # Resolve defaults from unified config
    cfg = load_config()
    if args.model is None:
        args.model = cfg_get(cfg, "models.embedding", "qwen3-embedding:0.6b")
    if args.ollama_url is None:
        base = cfg_get(cfg, "ollama.base_url", "http://localhost:11434")
        args.ollama_url = f"{base.rstrip('/')}/api/embeddings"
    if args.threshold is None:
        args.threshold = cfg_get(cfg, "semantic_link.threshold", 0.75)
    if args.merge_threshold is None:
        args.merge_threshold = cfg_get(cfg, "semantic_link.merge_threshold", 0.85)
    if args.auto_merge_threshold is None:
        args.auto_merge_threshold = cfg_get(cfg, "semantic_link.auto_merge_threshold", 0.95)

    return args

def check_model_available(ollama_url, model):
    """Preflight: confirm the embedding model is installed before doing any work.

    Fails fast with a clear message instead of 404-ing mid-run (after backups
    and partial embedding). `ollama_url` is the full embeddings endpoint; we
    derive the /api/tags endpoint from it.
    """
    base = ollama_url.rsplit("/api/", 1)[0]
    tags_url = f"{base}/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"[Error] Cannot reach Ollama at {base}: {e}")
        print("[Hint] Is the Ollama server running? Try `ollama serve`.")
        sys.exit(1)
    available = [m.get("name", "") for m in data.get("models", [])]
    if model in available:
        return
    base_name = model.split(":")[0]
    matches = [m for m in available if m.split(":")[0] == base_name]
    print(f"[Error] Embedding model '{model}' is not installed in Ollama.")
    if matches:
        print(f"[Hint] Found related tag(s): {', '.join(matches)}.")
        print(f"[Hint] Set models.embedding in config.yaml to one of those, or pass --model.")
    else:
        print(f"[Hint] Installed models: {', '.join(available) or '(none)'}")
        print(f"[Hint] Install it with: ollama pull {model}")
    sys.exit(1)

def backup_concepts(topic_dir, concepts_dir):
    # Store backups OUTSIDE the scanned wiki/ tree (under scratch/) so backup
    # copies are never parsed as concept files by the graph/lint/density tools.
    backup_dir = os.path.join(topic_dir, "scratch", "concept_backups")
    os.makedirs(backup_dir, exist_ok=True)
    count = 0
    for filename in os.listdir(concepts_dir):
        if filename.endswith(".md"):
            src = os.path.join(concepts_dir, filename)
            dst = os.path.join(backup_dir, filename)
            shutil.copy2(src, dst)
            count += 1
    print(f"[Info] Backed up {count} files to {backup_dir}")

def clean_markdown_text(text):
    """Strip frontmatter and markdown links to get raw text for better embeddings."""
    tags = []
    aliases = []
    
    # Extract YAML frontmatter before removing it
    fm_match = re.search(r'^---([\s\S]*?)---\n', text)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
            tags = fm.get("tags", [])
            if isinstance(tags, str): tags = [tags]
            aliases = fm.get("aliases", [])
            if isinstance(aliases, str): aliases = [aliases]
        except Exception:
            pass
            
    # Remove YAML frontmatter
    text = re.sub(r'^---[\s\S]*?---\n', '', text)
    # Remove markdown links but keep the text (e.g., [[Concept]] -> Concept, [text](url) -> text)
    text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    # Remove template boilerplate that causes false-positive similarity
    text = text.replace("No explicit definition extracted from literature perspective.", "")
    text = text.replace("No explicit mathematical representation extracted from literature perspective.", "")
    text = text.replace("[STUB: Awaiting synthesis]", "")
    text = text.strip()
    
    # Append Metadata Context for Embedding Augmentation
    context_parts = []
    if tags:
        context_parts.append(f"Tags include {', '.join(tags)}.")
    if aliases:
        context_parts.append(f"Known aliases: {', '.join(aliases)}.")
        
    if context_parts:
        text += f"\n\n[Metadata Context: {' '.join(context_parts)}]"
        
    return text, tags, aliases

def get_embedding(text, model, url):
    data = {
        "model": model,
        "prompt": text
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("embedding")
    except urllib.error.URLError as e:
        print(f"[Error] Failed to connect to Ollama: {e}")
        sys.exit(1)

def inject_link(filepath, related_concept_name):
    """Safely injects a related concept link into the markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Idempotency check
    link_syntax_plain = f"[[{related_concept_name}]]"
    link_syntax_alias = f"[[{related_concept_name}|"
    if link_syntax_plain in content or link_syntax_alias in content:
        return False # Already exists
    
    display_name = related_concept_name.replace('-', ' ').title()
    link_syntax = f"[[{related_concept_name}|{display_name}]]"
    heading = "## 语义关联 (Semantic Links)"
    
    if heading in content:
        # Append to existing section
        safe_heading = re.escape(heading)
        content = re.sub(
            f"({safe_heading}.*?)(?=\\n##|$)",
            f"\\1\n- {link_syntax}",
            content,
            flags=re.DOTALL
        )
    else:
        # Create new section at the end
        if not content.endswith('\n'):
            content += '\n'
        content += f"\n{heading}\n- {link_syntax}\n"
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def main():
    args = setup_argparse()
    topic_dir = os.path.abspath(args.topic_dir)
    concepts_dir = os.path.join(topic_dir, "wiki", "concepts")
    
    if not os.path.exists(concepts_dir):
        print(f"[Error] Concepts directory not found at {concepts_dir}")
        sys.exit(1)
        
    print(f"[Info] Starting semantic link generation for: {concepts_dir}")
    print(f"[Info] Model: {args.model}, Threshold: {args.threshold}")
    if args.dedup_only:
        print("[Info] Running in DEDUP-ONLY mode. Links will not be injected.")

    # 0. Preflight: fail fast if the embedding model is missing.
    check_model_available(args.ollama_url, args.model)

    # 1. Backup — only when this run will actually modify files. A read-only
    #    pass (dedup-only with no auto-merge) needs no backup.
    will_modify = (not args.dedup_only) or args.auto_merge
    if will_modify:
        backup_concepts(topic_dir, concepts_dir)
    else:
        print("[Info] Read-only run (dedup-only, no --auto-merge): skipping backup.")
    
    # 2. Read and extract text
    files = []
    texts = []
    concept_names = []
    concept_tags = []
    concept_aliases = []
    
    for filename in os.listdir(concepts_dir):
        if filename.endswith(".md") and not filename.startswith("_"):
            filepath = os.path.join(concepts_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            clean_text, tags, aliases = clean_markdown_text(raw_text)
            if clean_text:
                files.append(filepath)
                texts.append(clean_text)
                concept_names.append(filename[:-3]) # remove .md
                concept_tags.append(tags)
                concept_aliases.append(aliases)
    
    if len(files) < 2:
        print("[Info] Not enough concepts to analyze.")
        sys.exit(0)
        
    # 3. Generate embeddings
    print(f"[Info] Generating embeddings for {len(files)} concepts...")
    
    # --- Caching Logic ---
    # Cache lives under output/ (a generated-artifacts dir), not inside the
    # scanned wiki/concepts/ tree.
    safe_model_name = args.model.replace(":", "_").replace("/", "_")
    cache_dir = os.path.join(topic_dir, "output")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f".embeddings_cache_{safe_model_name}.json")
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"[Info] Loaded embedding cache from {os.path.basename(cache_path)}")
        except Exception as e:
            print(f"[Warning] Failed to load cache: {e}. Starting fresh.")
    
    new_cache = {}
    embeddings = []
    api_calls = 0
    cache_hits = 0
    
    for i, text in enumerate(texts):
        concept_name = concept_names[i]
        print(f"\r  - Embedding {i+1}/{len(texts)}: {concept_name}", end='', flush=True)
        
        # Calculate MD5 of clean text
        text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        # Check cache
        cached_data = cache.get(concept_name)
        if cached_data and cached_data.get("hash") == text_md5 and "embedding" in cached_data:
            emb = cached_data["embedding"]
            cache_hits += 1
        else:
            # API Call
            emb = get_embedding(text, args.model, args.ollama_url)
            if not emb:
                print(f"\n[Error] Failed to get embedding for {concept_name}")
                sys.exit(1)
            api_calls += 1
            
        embeddings.append(emb)
        new_cache[concept_name] = {
            "hash": text_md5,
            "embedding": emb
        }
        
    print(f"\n[Info] Embeddings ready. Cache hits: {cache_hits}, API calls: {api_calls}")
    
    # Save pruned cache (only contains active concepts)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(new_cache, f)
    except Exception as e:
        print(f"[Warning] Failed to save cache: {e}")

    if args.update_cache_only:
        print("[Success] Cache updated successfully. Exiting.")
        sys.exit(0)
    
    # 4. Calculate similarities
    embeddings_matrix = np.array(embeddings)
    print("[Info] Calculating cosine similarity matrix...")
    similarity_matrix = cosine_similarity(embeddings_matrix)
    
    # 5. Pass A: scan the (read-only) similarity matrix and collect candidate
    #    pairs. We never mutate files inside this loop — doing so would
    #    invalidate `files`/`concept_names`/`similarity_matrix` for later
    #    iterations. Merges and link injection happen in dedicated passes below.
    print("[Info] Analyzing similarities...")
    merge_pairs = []  # (score, idx_a, idx_b, boost_reason) where score >= merge_threshold
    link_pairs = []   # (idx_a, idx_b, score, boost_reason) where score >= threshold
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            score = similarity_matrix[i][j]

            # --- Meta-Data Hard Boosting Logic ---
            tags_i = set(t.lower() for t in concept_tags[i])
            tags_j = set(t.lower() for t in concept_tags[j])
            shared_tags = len(tags_i.intersection(tags_j))

            aliases_i = set(a.lower() for a in concept_aliases[i])
            aliases_j = set(a.lower() for a in concept_aliases[j])

            # Alias Collision / Crossmatch Boost
            has_alias_collision = False
            if aliases_i.intersection(aliases_j):
                has_alias_collision = True

            # Check if title of i is in alias of j, or vice versa
            title_i = concept_names[i].replace("-", " ").replace("_", " ").lower()
            title_j = concept_names[j].replace("-", " ").replace("_", " ").lower()
            if title_i in aliases_j or title_j in aliases_i:
                has_alias_collision = True

            boost_reason = ""
            original_score = score
            if has_alias_collision:
                score = min(1.0, score + 0.10)
                boost_reason = f" [Alias Boost: {original_score:.3f}->{score:.3f}]"
            elif shared_tags > 0:
                score = min(1.0, score + (shared_tags * 0.05))
                boost_reason = f" [Tag Boost: {original_score:.3f}->{score:.3f}]"

            if score >= args.merge_threshold:
                merge_pairs.append((float(score), i, j, boost_reason))
            if not args.dedup_only and score >= args.threshold:
                link_pairs.append((i, j, float(score), boost_reason))

    merge_suggestions = len(merge_pairs)
    if args.dedup_only:
        for score, i, j, boost_reason in merge_pairs:
            print(f"[MERGE_SUGGESTION] {concept_names[i]} <--> {concept_names[j]} (Score: {score:.3f}){boost_reason}")

    # 6. Pass B: auto-merge. Runs whenever --auto-merge is set, independent of
    #    --dedup-only. Strongest pairs first, and once a concept has been merged
    #    away we skip any further pair that references it (its file is gone).
    merged_away = set()
    if args.auto_merge:
        refactor_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "bin", "refactor_concept.py"
        )
        for score, i, j, boost_reason in sorted(merge_pairs, key=lambda p: p[0], reverse=True):
            if score < args.auto_merge_threshold:
                continue
            name_i = concept_names[i]
            name_j = concept_names[j]
            if name_i in merged_away or name_j in merged_away:
                continue
            if len(name_i) <= len(name_j):
                canonical, old = name_i, name_j
            else:
                canonical, old = name_j, name_i

            print(f"  [AUTO-MERGING] {old} -> {canonical}")
            result = subprocess.run(
                [sys.executable, refactor_script, "--topic-dir", topic_dir, "--old", old, "--new", canonical]
            )
            if result.returncode == 0:
                merged_away.add(old)
            else:
                print(f"  [Warning] Merge failed ({old} -> {canonical}); refactor_concept exited {result.returncode}. Skipping.")

    # 7. Pass C: inject links (non-dedup-only). Skip any pair whose file was
    #    deleted by an auto-merge in Pass B.
    links_added = 0
    if not args.dedup_only:
        for i, j, score, boost_reason in link_pairs:
            if concept_names[i] in merged_away or concept_names[j] in merged_away:
                continue
            if not os.path.exists(files[i]) or not os.path.exists(files[j]):
                continue
            # Add link to i (linking to j)
            if inject_link(files[i], concept_names[j]):
                links_added += 1
                print(f"  [Linked] {concept_names[i]} <--> {concept_names[j]} (Score: {score:.3f}){boost_reason}")
            # Add link to j (linking to i)
            if inject_link(files[j], concept_names[i]):
                links_added += 1
                # Don't print twice to avoid spam

    if args.dedup_only:
        print(f"[Success] Found {merge_suggestions} potential merges.")
    else:
        print(f"[Success] Added {links_added} new semantic links.")

if __name__ == "__main__":
    main()
