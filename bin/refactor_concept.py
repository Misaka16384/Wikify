import argparse
import os
import re
import shutil
import sys
import yaml
from datetime import datetime

try:
    from wiki_common import atomic_write
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wiki_common import atomic_write


def extract_frontmatter(content):
    fm_match = re.search(r'^---([\s\S]*?)---\n', content)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
            body = content[fm_match.end():]
            return fm, body
        except Exception as e:
            print(f"Warning: YAML parse error in frontmatter: {e}", file=sys.stderr)
    return {}, content

def merge_frontmatter(fm1, fm2):
    res = dict(fm1)
    
    def merge_list(key):
        l1 = fm1.get(key, [])
        l2 = fm2.get(key, [])
        if isinstance(l1, str): l1 = [l1]
        if isinstance(l2, str): l2 = [l2]
        merged = list(dict.fromkeys(l1 + l2))
        if merged:
            res[key] = merged
            
    merge_list("tags")
    merge_list("aliases")
    merge_list("sources")
    return res

def format_frontmatter(fm):
    lines = ["---"]
    order = ['title', 'category', 'created', 'updated', 'tags', 'aliases', 'confidence', 'summary', 'sources', 'volatility']
    for key in order:
        if key in fm:
            val = fm[key]
            if isinstance(val, list):
                if not val:
                    lines.append(f"{key}: []")
                elif key in ['tags', 'aliases']:
                    lines.append(f"{key}: [{', '.join(val)}]")
                else:
                    lines.append(f"{key}:")
                    for v in val:
                        lines.append(f"  - \"{v}\"")
            else:
                if key in ['title', 'summary']:
                    lines.append(f"{key}: \"{val}\"")
                else:
                    lines.append(f"{key}: {val}")
    for key, val in fm.items():
        if key not in order:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)

def merge_concept_files(old_path, new_path, old_name):
    if not os.path.exists(old_path) or not os.path.exists(new_path):
        return
        
    with open(old_path, "r", encoding="utf-8") as f:
        old_content = f.read()
    with open(new_path, "r", encoding="utf-8") as f:
        new_content = f.read()
        
    old_fm, old_body = extract_frontmatter(old_content)
    new_fm, new_body = extract_frontmatter(new_content)
    
    merged_fm = merge_frontmatter(new_fm, old_fm)
    new_fm_str = format_frontmatter(merged_fm)
    
    final_content = f"{new_fm_str}\n{new_body.strip()}\n\n---\n## [Merged Content: {old_name}]\n\n{old_body.strip()}\n"
    
    atomic_write(new_path, final_content, encoding="utf-8")
    print(f"Physically merged content from {old_name} into {os.path.basename(new_path)}")


def main():
    parser = argparse.ArgumentParser(description="Refactor and merge concept links across the wiki")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    parser.add_argument("--old", required=True, help="Old concept name")
    parser.add_argument("--new", required=True, help="New concept name")
    parser.add_argument("--no-rebuild", action="store_true", help="Bypass automatic database/index rebuild")
    
    args = parser.parse_args()
    wiki_dir = os.path.join(args.topic_dir, "wiki")
    concepts_dir = os.path.join(wiki_dir, "concepts")
    
    old_name = args.old
    new_name = args.new

    # Path traversal protection: reject names containing directory separators
    for name in [old_name, new_name]:
        if '..' in name or '/' in name or '\\' in name:
            print(f"Error: Invalid concept name '{name}' — path traversal detected")
            sys.exit(1)

    # Backup old concept file
    old_file_path = os.path.join(concepts_dir, f"{old_name}.md")
    new_file_path = os.path.join(concepts_dir, f"{new_name}.md")
    if os.path.exists(old_file_path):
        backup_dir = os.path.join(concepts_dir, ".backup")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_file_path = os.path.join(backup_dir, f"{old_name}_{timestamp}.md")
        shutil.copy2(old_file_path, backup_file_path)
        print(f"Backed up {old_file_path} to {backup_file_path}")
        
        # Merge contents physically
        if os.path.exists(new_file_path):
            merge_concept_files(old_file_path, new_file_path, old_name)
    else:
        print(f"Warning: Old concept file not found at {old_file_path}")

    # Refactor links in all markdown files
    # We want to replace [[Old]] with [[New]],
    # [[Old|alias]] with [[New|alias]],
    # and standard links like ../concepts/old.md) with ../concepts/new.md)
    pattern_strict = re.compile(r'\[\[' + re.escape(old_name) + r'\]\]', re.IGNORECASE)
    pattern_alias = re.compile(r'\[\[' + re.escape(old_name) + r'\|', re.IGNORECASE)
    pattern_md_link = re.compile(r'([/\\])' + re.escape(old_name) + r'\.md([)#\s])', re.IGNORECASE)
    
    modified_count = 0
    for root, dirs, files in os.walk(wiki_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = pattern_strict.sub(f"[[{new_name}]]", content)
                new_content = pattern_alias.sub(f"[[{new_name}|", new_content)
                new_content = pattern_md_link.sub(rf"\1{new_name}.md\2", new_content)
                
                if new_content != content:
                    atomic_write(filepath, new_content, encoding="utf-8")
                    print(f"Updated links in {filepath}")
                    modified_count += 1
                    
    # Delete old concept file
    if os.path.exists(old_file_path):
        os.remove(old_file_path)
        print(f"Deleted old concept file {old_file_path}")
        
    print(f"Refactoring complete. Modified {modified_count} files.")

    if not args.no_rebuild:
        # Update knowledge graph and indexes automatically
        import subprocess
        print("Triggering graph database and index updates...")
        agents_bin = os.path.dirname(os.path.abspath(__file__))
        try:
            subprocess.run([sys.executable, os.path.join(agents_bin, "llm-wiki.py"), "graph", args.topic_dir], check=True)
            subprocess.run([sys.executable, os.path.join(agents_bin, "index_builder.py"), args.topic_dir], check=True)
            print("Successfully updated graph.db and _index.md files.")
        except Exception as e:
            print(f"Warning: Failed to update graph database or indexes: {e}")

if __name__ == "__main__":
    main()
