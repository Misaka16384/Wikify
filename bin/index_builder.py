import os
import sys
import datetime
import yaml
import glob
import argparse

def extract_frontmatter(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: file read error: {e}", file=sys.stderr)
        return {}
    
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
                return fm if fm else {}
            except Exception as e:
                print(f"Warning: YAML parse error: {e}", file=sys.stderr)
    return {}

def build_index_for_dir(dir_path, title):
    if not os.path.exists(dir_path):
        return
        
    md_files = glob.glob(os.path.join(dir_path, "*.md"))
    # filter out _index.md
    md_files = [f for f in md_files if not os.path.basename(f) == "_index.md"]
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    table_rows = []
    categories = {}
    
    for fpath in sorted(md_files):
        fname = os.path.basename(fpath)
        fm = extract_frontmatter(fpath)
        
        summary = fm.get('summary', '').replace('\n', ' ').strip()
        if not summary:
            summary = "No summary provided."
            
        tags = fm.get('tags') or []
        if isinstance(tags, str):
            tags = [tags]
        tags_str = ", ".join(tags) if tags else ""
        
        updated = fm.get('updated', fm.get('created', ''))
        
        table_rows.append(f"| [{fname}]({fname}) | {summary} | {tags_str} | {updated} |")
        
        cat = fm.get('category', fm.get('type', 'Uncategorized'))
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(fname)
        
    table_content = "\n".join(table_rows)
    
    cat_content = ""
    for cat, files in sorted(categories.items()):
        links = ", ".join([f"[{f}]({f})" for f in files])
        cat_content += f"*   **{cat}**: {links}\n"
        
    index_content = f"""# {title} Index

> Auto-generated index of {title}.

Last updated: {today}

## Contents

| File | Summary | Tags | Updated |
| :--- | :--- | :--- | :--- |
{table_content}

## Categories

{cat_content}
"""

    index_path = os.path.join(dir_path, "_index.md")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    print(f"Built index: {index_path}")

def main():
    parser = argparse.ArgumentParser(description="Build index files for wiki directories")
    parser.add_argument("topic_dir", help="Topic directory path")
    args = parser.parse_args()
    
    wiki_dir = os.path.join(args.topic_dir, "wiki")
    
    refs_dir = os.path.join(wiki_dir, "references")
    build_index_for_dir(refs_dir, "References")
    
    concepts_dir = os.path.join(wiki_dir, "concepts")
    build_index_for_dir(concepts_dir, "Concepts")

if __name__ == "__main__":
    main()
