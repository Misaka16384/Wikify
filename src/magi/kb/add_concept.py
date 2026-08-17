import os
import sys
import argparse
import datetime
import re
import difflib
from filelock import FileLock
from magi.core.wiki_common import slugify, atomic_write


def normalize_slug(s):
    # Remove only non-semantically-distinct prefixes
    s = re.sub(r'^(?:lattice|quantum|topological)-', '', s)
    return s

def are_similar_slugs(slug1, slug2):
    if slug1 == slug2:
        return True

    # Sequence similarity ratio (normalized equality no longer auto-confirms a match)
    ratio = difflib.SequenceMatcher(None, slug1, slug2).ratio()
    if ratio >= 0.82:
        return True

    # Substring containment checks for common suffix/prefix variations (e.g. mapping vs map)
    # or prefix modifiers (e.g. lattice-twisted-gauging vs twisted-gauging)
    if slug1 in slug2 or slug2 in slug1:
        shorter, longer = (slug1, slug2) if len(slug1) < len(slug2) else (slug2, slug1)
        if longer.endswith(shorter) or longer.startswith(shorter):
            if len(shorter) / len(longer) >= 0.65:
                return True

    return False


def resolve_source(topic_dir, source_arg):
    # Path traversal protection: reject source containing directory separators
    if '..' in source_arg:
        print(f"Warning: Invalid source '{source_arg}' — path traversal detected")
        return None, None

    slug = slugify(source_arg)
    
    # 1. Check in raw/papers/
    raw_dir = os.path.join(topic_dir, "raw", "papers")
    if os.path.exists(raw_dir):
        for f in os.listdir(raw_dir):
            if f.endswith(".md") and f != "_index.md":
                f_slug = slugify(os.path.splitext(f)[0])
                if slug in f_slug or f_slug in slug:
                    return f"raw/papers/{f}", os.path.splitext(f)[0]
                    
    # 2. Check in wiki/references/
    ref_dir = os.path.join(topic_dir, "wiki", "references")
    if os.path.exists(ref_dir):
        for f in os.listdir(ref_dir):
            if f.endswith(".md") and f != "_index.md":
                f_slug = slugify(os.path.splitext(f)[0])
                if slug in f_slug or f_slug in slug:
                    return f"wiki/references/{f}", os.path.splitext(f)[0]
                    
    return source_arg, source_arg

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki add-concept", description="Safely add or append concept definitions.")
    parser.add_argument("--name", required=True, help="Name of the concept")
    parser.add_argument("--source", required=True, help="Source paper/document")
    parser.add_argument("--content", required=True, help="Content/Perspective to append")
    parser.add_argument("--topic-dir", default=".", help="Topic directory")
    parser.add_argument("--no-rebuild", action="store_true", help="Bypass automatic database/index rebuild")
    args = parser.parse_args(argv)

    # slugify the concept name (Unicode-aware; supports CJK / accented names)
    slug = slugify(args.name)
    if not slug:
        print("Invalid concept name.")
        sys.exit(1)
        
    concepts_dir = os.path.join(args.topic_dir, "wiki", "concepts")
    os.makedirs(concepts_dir, exist_ok=True)
    
    # 1. Fuzzy check existing concepts
    canonical_slug = slug
    canonical_file = os.path.join(concepts_dir, f"{slug}.md")
    
    from magi.core.wiki_common import parse_frontmatter, split_frontmatter_text, parse_frontmatter_text
    
    if os.path.exists(concepts_dir):
        for filename in os.listdir(concepts_dir):
            if filename.endswith(".md") and not filename.startswith("_"):
                existing_slug = filename[:-3]
                existing_path = os.path.join(concepts_dir, filename)
                
                with open(existing_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                fm = parse_frontmatter(file_content)
                
                existing_title_slug = slugify(fm.get("title", ""))
                aliases = fm.get("aliases", [])
                if isinstance(aliases, str):
                    aliases = [aliases]
                alias_slugs = [slugify(a) for a in aliases if a]
                
                # Check for similarities
                matched = False
                if are_similar_slugs(slug, existing_slug):
                    matched = True
                elif existing_title_slug and are_similar_slugs(slug, existing_title_slug):
                    matched = True
                else:
                    for aslug in alias_slugs:
                        if are_similar_slugs(slug, aslug):
                            matched = True
                            break
                            
                if matched:
                    print(f"[Deduplication] Merging new concept '{args.name}' (slug: {slug}) into canonical concept '{fm.get('title', existing_slug)}' (slug: {existing_slug})")
                    canonical_slug = existing_slug
                    canonical_file = existing_path
                    break

    lock_file = canonical_file + ".lock"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with FileLock(lock_file, timeout=10):
        if not os.path.exists(canonical_file):
            resolved_source_path, resolved_source_name = resolve_source(args.topic_dir, args.source)
            if resolved_source_path is None:
                sys.exit(1)
            
            # Use forward slashes in sources to prevent YAML escaping backslash errors on Windows
            resolved_source_path_escaped = resolved_source_path.replace("\\", "/")

            content = f"""---
title: "{args.name}"
category: concept
status: stub
created: {today}
updated: {today}
tags:
  - mined-concept
aliases: []
volatility: warm
sources:
  - '{resolved_source_path_escaped}'
confidence: medium
summary: 'Dynamically mined concept tracking {args.name}.'
---

# {args.name}

## 1. Core Definition & Physical Intuition
*(This concept is currently a stub. Literature perspectives are compiled under Section 5 below.)*

## 2. Mathematical Formalism & Key Properties
*(Formal definition and properties are compiled under Section 5 below.)*

---

## See Also
*   *None yet.*

## Sources
*   [[{resolved_source_name}]] - Mined from this reference.

## 5. Perspectives from Literature

### Perspective from {args.source}
{args.content}
"""
            atomic_write(canonical_file, content, encoding='utf-8')
            print(f"Created new concept file: {canonical_file}")
        else:
            with open(canonical_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Update aliases in the frontmatter if we are referencing under a new alias name
            import yaml
            parts = split_frontmatter_text(content)
            if parts:
                fm_text, body = parts
                fm = parse_frontmatter_text(fm_text)

                # FIX 1: detect parse failure — if raw frontmatter was non-blank but
                # parsing returned empty/None, do NOT serialize an empty dict over the file.
                fm_parse_failed = (not fm) and bool(fm_text and fm_text.strip())

                if fm_parse_failed:
                    print(f"Warning: could not parse frontmatter YAML in {canonical_file} — alias not added; updating date only.", file=sys.stderr)
                    new_fm_text = re.sub(r'updated:\s*\d{4}-\d{2}-\d{2}', f'updated: {today}', fm_text)
                    content = f"---\n{new_fm_text}\n---" + body
                else:
                    aliases = fm.get("aliases", [])
                    if isinstance(aliases, str):
                        aliases = [aliases]
                    elif aliases is None:
                        aliases = []

                    existing_title = fm.get("title", "")
                    if args.name not in aliases and slugify(args.name) != slugify(existing_title):
                        aliases.append(args.name)
                        fm["aliases"] = aliases
                        fm["updated"] = today
                        new_fm_text = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
                        content = f"---\n{new_fm_text}\n---" + body
                    else:
                        # FIX 3: scope substitution to frontmatter only, not the whole file
                        new_fm_text = re.sub(r'updated:\s*\d{4}-\d{2}-\d{2}', f'updated: {today}', fm_text)
                        content = f"---\n{new_fm_text}\n---" + body
            
            if "## 5. Perspectives from Literature" not in content:
                content += "\n## 5. Perspectives from Literature\n"
                
            content += f"\n### Perspective from {args.source}\n{args.content}\n"
            
            atomic_write(canonical_file, content, encoding='utf-8')
            print(f"Appended perspective to existing concept file: {canonical_file}")

        if not args.no_rebuild:
            # Update knowledge graph and indexes automatically
            import subprocess
            print("Triggering graph database and index updates...")
            try:
                subprocess.run([sys.executable, "-m", "magi", "graph", "build", args.topic_dir], check=True)
                subprocess.run([sys.executable, "-m", "magi", "wiki", "reindex", args.topic_dir], check=True)
                print("Successfully updated graph.db and _index.md files.")
            except Exception as e:
                print(f"Warning: Failed to update graph database or indexes: {e}")

    # Clean up lock file if possible
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception as e:
        print(f"Warning: lock cleanup failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())
