import os
import sys
import argparse
import datetime
import re
from filelock import FileLock

def resolve_source(topic_dir, source_arg):
    # Path traversal protection: reject source containing directory separators
    if '..' in source_arg:
        print(f"Warning: Invalid source '{source_arg}' — path traversal detected")
        return None, None

    slug = re.sub(r'[^a-zA-Z0-9]+', '-', source_arg.lower()).strip('-')
    
    # 1. Check in raw/papers/
    raw_dir = os.path.join(topic_dir, "raw", "papers")
    if os.path.exists(raw_dir):
        for f in os.listdir(raw_dir):
            if f.endswith(".md") and f != "_index.md":
                f_slug = re.sub(r'[^a-zA-Z0-9]+', '-', os.path.splitext(f)[0].lower()).strip('-')
                if slug in f_slug or f_slug in slug:
                    return f"raw/papers/{f}", os.path.splitext(f)[0]
                    
    # 2. Check in wiki/references/
    ref_dir = os.path.join(topic_dir, "wiki", "references")
    if os.path.exists(ref_dir):
        for f in os.listdir(ref_dir):
            if f.endswith(".md") and f != "_index.md":
                f_slug = re.sub(r'[^a-zA-Z0-9]+', '-', os.path.splitext(f)[0].lower()).strip('-')
                if slug in f_slug or f_slug in slug:
                    return f"wiki/references/{f}", os.path.splitext(f)[0]
                    
    return source_arg, source_arg

def main():
    parser = argparse.ArgumentParser(description="Safely add or append concept definitions.")
    parser.add_argument("--name", required=True, help="Name of the concept")
    parser.add_argument("--source", required=True, help="Source paper/document")
    parser.add_argument("--content", required=True, help="Content/Perspective to append")
    parser.add_argument("--topic-dir", default=".", help="Topic directory")
    args = parser.parse_args()

    # slugify the concept name
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', args.name.lower()).strip('-')
    if not slug:
        print("Invalid concept name.")
        sys.exit(1)
        
    concepts_dir = os.path.join(args.topic_dir, "wiki", "concepts")
    os.makedirs(concepts_dir, exist_ok=True)
    
    concept_file = os.path.join(concepts_dir, f"{slug}.md")
    lock_file = concept_file + ".lock"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "..", "skills", "wiki_compile", "templates", "concept_template.md")

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    with FileLock(lock_file, timeout=10):
        if not os.path.exists(concept_file):
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = "---\ntitle: \"Concept Name\"\ncategory: concept\ncreated: YYYY-MM-DD\nupdated: YYYY-MM-DD\n---\n\n# Concept Name\n"
            
            resolved_source_path, resolved_source_name = resolve_source(args.topic_dir, args.source)
            if resolved_source_path is None:
                sys.exit(1)

            new_frontmatter = f"""---
title: "{args.name}"
category: concept
created: {today}
updated: {today}
tags:
  - mined-concept
aliases: []
volatility: warm
sources:
  - "{resolved_source_path}"
confidence: medium
summary: 'Dynamically mined concept tracking {args.name}.'
---"""
            # Wipe and replace dummy frontmatter
            content = re.sub(r'^---\n.*?\n---\n', new_frontmatter + '\n', content, flags=re.DOTALL)
            
            # Wipe and replace dummy See Also and Sources blocks at the bottom
            new_footer = f"## See Also\n*   *None yet.*\n\n## Sources\n*   [[{resolved_source_name}]] - Mined from this reference.\n"
            content = re.sub(r'## See Also.*', new_footer, content, flags=re.DOTALL)
            
            content = re.sub(r'^# Concept Name$', f'# {args.name}', content, flags=re.MULTILINE)
            content = content.replace("YYYY-MM-DD", today)
            
            content += f"\n## 5. Perspectives from Literature\n\n### Perspective from {args.source}\n{args.content}\n"
            
            with open(concept_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created new concept file: {concept_file}")
        else:
            with open(concept_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if "## 5. Perspectives from Literature" not in content:
                content += "\n## 5. Perspectives from Literature\n"
                
            content += f"\n### Perspective from {args.source}\n{args.content}\n"
            
            # update the updated date
            content = re.sub(r'updated:\s*\d{4}-\d{2}-\d{2}', f'updated: {today}', content)
            
            with open(concept_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Appended perspective to existing concept file: {concept_file}")
            
    # Clean up lock file if possible
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception as e:
        print(f"Warning: lock cleanup failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
