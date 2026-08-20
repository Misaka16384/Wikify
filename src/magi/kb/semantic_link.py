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
import sqlite3
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

from magi.core.config_loader import load_config, get as cfg_get
from magi.core.workspace import find_workspace_root

def setup_argparse(argv=None):
    parser = argparse.ArgumentParser(prog="magi link", description="Wiki Semantic Linker using Ollama")
    parser.add_argument("topic_dir", nargs="?", default=None,
                        help="Path to the root of the topic wiki (containing wiki/concepts/); "
                             "defaults to the workspace you are in")
    parser.add_argument("--threshold", type=float, default=None, help="Cosine similarity threshold for linking (default: from config.yaml)")
    parser.add_argument("--merge-threshold", type=float, default=None, help="Cosine similarity threshold for merge suggestions (default: from config.yaml)")
    parser.add_argument("--auto-merge", action="store_true", help="Automatically merge concepts with score >= auto-merge-threshold")
    parser.add_argument("--auto-merge-threshold", type=float, default=None, help="Cosine similarity threshold for auto-merging (default: from config.yaml)")
    parser.add_argument("--dedup-only", action="store_true", help="Only output merge suggestions, do not inject links.")
    parser.add_argument("--update-cache-only", action="store_true", help="Only update the embedding cache and exit. Skips all similarity calculations.")
    parser.add_argument("--model", type=str, default=None, help="Ollama embedding model to use (default: from config.yaml)")
    parser.add_argument("--ollama-url", type=str, default=None, help="Ollama API endpoint (default: from config.yaml)")
    args = parser.parse_args(argv)

    if args.topic_dir is None:
        root = find_workspace_root()
        if root is None:
            parser.error("no MAGI workspace here - pass a topic directory, or cd into one")
        args.topic_dir = str(root)

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
    and partial embedding). A stopped local server is not a failure — it gets
    started. `ollama_url` is the full embeddings endpoint.
    """
    from magi.core import ollama as ollama_svc

    base = ollama_url.rsplit("/api/", 1)[0]
    state = ollama_svc.ensure(base)
    if state.started:
        print(f"[Info] Started Ollama at {base}.")
    if not state.running:
        print(f"[Error] {ollama_svc.hint(state)}")
        sys.exit(1)
    if state.has_model(model):
        return
    matches = [m for m in state.matching(model) if m != model]
    print(f"[Error] Embedding model '{model}' is not installed in Ollama.")
    if matches:
        print(f"[Hint] Found related tag(s): {', '.join(matches)}.")
        print(f"[Hint] Set models.embedding in config.yaml to one of those, or pass --model.")
    else:
        print(f"[Hint] Installed models: {', '.join(state.models) or '(none)'}")
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
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_bytes = response.read()
            try:
                result = json.loads(resp_bytes.decode('utf-8'))
                return result.get("embedding")
            except Exception as e:
                print(f"\n[Warning] Failed to parse JSON response from Ollama: {e}", file=sys.stderr)
                return None
    except Exception as e:
        print(f"\n[Warning] Failed to connect to Ollama or get embedding: {e}", file=sys.stderr)
        return None

def sync_semantic_links(filepath, target_links):
    """Synchronizes the semantic links in the file to match target_links.
    
    target_links is a set of concept slugs that should be linked.
    Returns (added_count, removed_count).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    heading = "## 语义关联 (Semantic Links)"
    pattern = r"(\n*## 语义关联 \(Semantic Links\)\n.*?)(?=\n##|$)"
    match = re.search(pattern, content, re.DOTALL)
    
    existing_links = set()
    if match:
        existing_links = set(re.findall(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", match.group(1)))
        
    added = target_links - existing_links
    removed = existing_links - target_links
    
    if not added and not removed:
        return 0, 0 # No changes needed
        
    new_links_block = ""
    if target_links:
        sorted_links = sorted(list(target_links))
        lines = []
        for slug in sorted_links:
            display_name = slug.replace('-', ' ').title()
            lines.append(f"- [[{slug}|{display_name}]]")
        new_links_block = f"\n\n{heading}\n" + "\n".join(lines) + "\n"
        
    if match:
        span = match.span(1)
        content = content[:span[0]] + new_links_block + content[span[1]:]
    elif target_links:
        if not content.endswith('\n'):
            content += '\n'
        content += new_links_block
        
    # Standardize newlines at the end of the file
    content = re.sub(r'\n{3,}$', '\n\n', content)
    content = content.rstrip('\n') + '\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return len(added), len(removed)

def main(argv=None):
    args = setup_argparse(argv)
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
    stub_files = []
    
    for filename in os.listdir(concepts_dir):
        if filename.endswith(".md") and not filename.startswith("_"):
            filepath = os.path.join(concepts_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                
            # Check if concept is a stub
            status = "stub"
            fm_match = re.search(r'^---([\s\S]*?)---\n', raw_text)
            if fm_match:
                try:
                    fm = yaml.safe_load(fm_match.group(1)) or {}
                    status = fm.get("status", "stub")
                except Exception:
                    pass
                    
            if status == "stub":
                stub_files.append((filepath, filename[:-3]))
                continue
                
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
    # scanned wiki/concepts/ tree. Use SQLite database to avoid concurrency issues.
    safe_model_name = args.model.replace(":", "_").replace("/", "_")
    cache_dir = os.path.join(topic_dir, "output")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f".embeddings_cache_{safe_model_name}.db")
    cache = {}
    try:
        conn = sqlite3.connect(cache_path, timeout=30.0)
        conn.execute("CREATE TABLE IF NOT EXISTS embeddings (concept_name TEXT PRIMARY KEY, hash TEXT, embedding TEXT)")
        conn.commit()
        cursor = conn.cursor()
        cursor.execute("SELECT concept_name, hash, embedding FROM embeddings")
        for row in cursor.fetchall():
            c_name, text_hash, emb_json = row
            try:
                cache[c_name] = {
                    "hash": text_hash,
                    "embedding": json.loads(emb_json)
                }
            except Exception:
                pass
        conn.close()
        print(f"[Info] Loaded embedding cache from SQLite database: {os.path.basename(cache_path)}")
    except Exception as e:
        print(f"[Warning] Failed to load SQLite embedding cache: {e}. Starting fresh.")

    new_cache = {}
    active_embeddings = []
    active_files = []
    active_texts = []
    active_concept_names = []
    active_concept_tags = []
    active_concept_aliases = []
    
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
                print(f"\n[Warning] Skipped embedding for {concept_name} due to API/JSON failure.")
                continue
            api_calls += 1
            
        active_embeddings.append(emb)
        active_files.append(files[i])
        active_texts.append(texts[i])
        active_concept_names.append(concept_name)
        active_concept_tags.append(concept_tags[i])
        active_concept_aliases.append(concept_aliases[i])
        new_cache[concept_name] = {
            "hash": text_md5,
            "embedding": emb
        }
        
    print(f"\n[Info] Embeddings ready. Cache hits: {cache_hits}, API calls: {api_calls}")
    
    # Save cache to SQLite db
    try:
        conn = sqlite3.connect(cache_path, timeout=30.0)
        with conn:
            for concept_name, data in new_cache.items():
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (concept_name, hash, embedding) VALUES (?, ?, ?)",
                    (concept_name, data["hash"], json.dumps(data["embedding"]))
                )
        conn.close()
        print(f"[Info] Saved embedding cache to SQLite database: {os.path.basename(cache_path)}")
    except Exception as e:
        print(f"[Warning] Failed to save SQLite embedding cache: {e}")

    embeddings = active_embeddings
    files = active_files
    texts = active_texts
    concept_names = active_concept_names
    concept_tags = active_concept_tags
    concept_aliases = active_concept_aliases

    if args.update_cache_only:
        print("[Success] Cache updated successfully. Exiting.")
        sys.exit(0)

    if len(files) < 2:
        print("[Info] Not enough concepts to analyze after filtering.")
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
                [sys.executable, "-m", "magi", "wiki", "refactor-concept", "--topic-dir", topic_dir, "--old", old, "--new", canonical]
            )
            if result.returncode == 0:
                merged_away.add(old)
            else:
                print(f"  [Warning] Merge failed ({old} -> {canonical}); refactor_concept exited {result.returncode}. Skipping.")

    # 7. Pass C: sync links (non-dedup-only). Skip any pair whose file was
    #    deleted by an auto-merge in Pass B.
    total_added = 0
    total_removed = 0
    if not args.dedup_only:
        # Build map of target links for each active concept
        target_links_map = {name: set() for name in concept_names if name not in merged_away}
        
        for idx_a, idx_b, score, boost_reason in link_pairs:
            name_a = concept_names[idx_a]
            name_b = concept_names[idx_b]
            if name_a in merged_away or name_b in merged_away:
                continue
            target_links_map[name_a].add(name_b)
            target_links_map[name_b].add(name_a)
            
        for i, name in enumerate(concept_names):
            if name in merged_away or not os.path.exists(files[i]):
                continue
            
            added, removed = sync_semantic_links(files[i], target_links_map[name])
            total_added += added
            total_removed += removed
            
            if added > 0 or removed > 0:
                print(f"  [Sync] {name}: added {added} link(s), removed {removed} link(s)")

        # Clean up links in stub files
        for filepath, name in stub_files:
            if not os.path.exists(filepath):
                continue
            added, removed = sync_semantic_links(filepath, set())
            total_added += added
            total_removed += removed
            if removed > 0:
                print(f"  [Sync Stub] {name}: cleared {removed} outdated link(s)")

    if args.dedup_only:
        print(f"[Success] Found {merge_suggestions} potential merges.")
    else:
        print(f"[Success] Synchronized semantic links. Added {total_added}, removed {total_removed}.")

if __name__ == "__main__":
    sys.exit(main())
