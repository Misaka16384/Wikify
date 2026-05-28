import argparse
import os
import re
import shutil
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Refactor and merge concept links across the wiki")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    parser.add_argument("--old", required=True, help="Old concept name")
    parser.add_argument("--new", required=True, help="New concept name")
    
    args = parser.parse_args()
    wiki_dir = os.path.join(args.topic_dir, "wiki")
    concepts_dir = os.path.join(wiki_dir, "concepts")
    
    old_name = args.old
    new_name = args.new
    
    # Backup old concept file
    old_file_path = os.path.join(concepts_dir, f"{old_name}.md")
    if os.path.exists(old_file_path):
        backup_dir = os.path.join(concepts_dir, ".backup")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_file_path = os.path.join(backup_dir, f"{old_name}_{timestamp}.md")
        shutil.copy2(old_file_path, backup_file_path)
        print(f"Backed up {old_file_path} to {backup_file_path}")
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
    for root, _, files in os.walk(wiki_dir):
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = pattern_strict.sub(f"[[{new_name}]]", content)
                new_content = pattern_alias.sub(f"[[{new_name}|", new_content)
                new_content = pattern_md_link.sub(rf"\1{new_name}.md\2", new_content)
                
                if new_content != content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Updated links in {filepath}")
                    modified_count += 1
                    
    # Delete old concept file
    if os.path.exists(old_file_path):
        os.remove(old_file_path)
        print(f"Deleted old concept file {old_file_path}")
        
    print(f"Refactoring complete. Modified {modified_count} files.")

if __name__ == "__main__":
    main()
