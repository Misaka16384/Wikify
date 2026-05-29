import os
import sys
import json
import argparse
from pathlib import Path
from collections import Counter
from wiki_common import parse_frontmatter_text


# NOTE: This local splitter is intentionally kept (not delegated to
# wiki_common.split_frontmatter_text) because replace_yaml_list() rewrites the
# raw frontmatter text in place and depends on this exact byte layout to
# preserve formatting, comments, and key order. Only the parse-to-dict step is
# shared via wiki_common.parse_frontmatter_text.
def split_markdown_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            return parts[1], parts[2]
    return "", text

def replace_yaml_list(text: str, field: str, new_list: list) -> str:
    import re
    if not new_list:
        efield = re.escape(field)
        return re.sub(rf"(?m)^{efield}:\s*\[.*?\]\n|^{efield}:\s*\n(?:\s+-\s+.*?\n)*", f"{field}: []\n", text)
    
    # Format new list as inline JSON array if short, or block list if long. Block is safer for Markdown.
    formatted_list = f"{field}:\n" + "\n".join(f"  - {item}" for item in new_list) + "\n"
    
    efield = re.escape(field)
    pattern = rf"(?m)^{efield}:\s*\[.*?\]\n|^{efield}:\s*\n(?:\s+-\s+.*?\n)*"
    
    if re.search(pattern, text):
        return re.sub(pattern, formatted_list, text)
    else:
        # Append to the end of frontmatter if it doesn't exist
        return text.strip() + "\n" + formatted_list

def cmd_extract(topic_dir: Path):
    print(f"Extracting metadata from {topic_dir}...")
    wiki_dir = topic_dir / "wiki"
    
    all_tags = []
    all_aliases = []
    
    for filepath in wiki_dir.rglob("*.md"):
        if filepath.name.startswith("_"):
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
            fm_text, _ = split_markdown_frontmatter(content)
            if not fm_text:
                continue
                
            fm = parse_frontmatter_text(fm_text)
            
            tags = fm.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            all_tags.extend(tags)
            
            aliases = fm.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            all_aliases.extend(aliases)
            
        except Exception as e:
            print(f"Warning: Could not parse {filepath.name}: {e}")
            
    # Count frequencies
    tag_counts = dict(Counter(all_tags).most_common())
    alias_counts = dict(Counter(all_aliases).most_common())
    
    scratch_dir = topic_dir / "scratch"
    scratch_dir.mkdir(exist_ok=True)
    
    with open(scratch_dir / "raw_tags.json", "w", encoding="utf-8") as f:
        json.dump(tag_counts, f, indent=2, ensure_ascii=False)
        
    with open(scratch_dir / "raw_aliases.json", "w", encoding="utf-8") as f:
        json.dump(alias_counts, f, indent=2, ensure_ascii=False)
        
    print(f"Extracted {len(tag_counts)} unique tags to scratch/raw_tags.json")
    print(f"Extracted {len(alias_counts)} unique aliases to scratch/raw_aliases.json")

def cmd_apply(topic_dir: Path, tag_map_path: Path, alias_map_path: Path):
    if not tag_map_path.exists() or not alias_map_path.exists():
        print("Error: Mapping files not found. Run extract and create mappings first.")
        sys.exit(1)
        
    with open(tag_map_path, "r", encoding="utf-8") as f:
        tag_map = json.load(f).get("tags", {})
        
    with open(alias_map_path, "r", encoding="utf-8") as f:
        alias_map = json.load(f).get("aliases", {})
        
    wiki_dir = topic_dir / "wiki"
    modified_count = 0
    final_ontology = set()
    
    for filepath in wiki_dir.rglob("*.md"):
        if filepath.name.startswith("_"):
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
            fm_text, body = split_markdown_frontmatter(content)
            if not fm_text:
                continue
                
            fm = parse_frontmatter_text(fm_text)
            
            # Process Tags
            old_tags = fm.get("tags", [])
            if isinstance(old_tags, str): old_tags = [old_tags]
            
            new_tags = []
            for t in old_tags:
                mapped_t = tag_map.get(t, t)
                if mapped_t and mapped_t not in new_tags:
                    new_tags.append(mapped_t)
                    final_ontology.add(mapped_t)
            
            # Process Aliases
            old_aliases = fm.get("aliases", [])
            if isinstance(old_aliases, str): old_aliases = [old_aliases]
            
            new_aliases = []
            for a in old_aliases:
                mapped_a = alias_map.get(a, a)
                if mapped_a and mapped_a not in new_aliases:
                    new_aliases.append(mapped_a)
            
            # Check if modification is needed
            if old_tags != new_tags or old_aliases != new_aliases:
                # We need to rewrite the frontmatter text directly to preserve formatting/order
                updated_fm_text = replace_yaml_list(fm_text, "tags", new_tags)
                updated_fm_text = replace_yaml_list(updated_fm_text, "aliases", new_aliases)
                
                new_content = f"---\n{updated_fm_text}---\n{body}"
                filepath.write_text(new_content, encoding="utf-8")
                modified_count += 1
                
        except Exception as e:
            print(f"Warning: Could not process {filepath.name}: {e}")
            
    print(f"Successfully applied mappings to {modified_count} files.")
    
    # Save ontology
    ontology_list = sorted(list(final_ontology))
    output_dir = topic_dir / "output"
    output_dir.mkdir(exist_ok=True)
    ontology_path = output_dir / "ontology.txt"
    with open(ontology_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ontology_list))
    print(f"Saved {len(ontology_list)} canonical tags to output/ontology.txt")

def main():
    parser = argparse.ArgumentParser(description="Wiki Tag and Alias Reducer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_ext = subparsers.add_parser("extract")
    parser_ext.add_argument("topic_dir", help="Path to topic root")
    
    parser_app = subparsers.add_parser("apply")
    parser_app.add_argument("topic_dir", help="Path to topic root")
    parser_app.add_argument("tag_map", help="Path to tag_mapping.json")
    parser_app.add_argument("alias_map", help="Path to alias_mapping.json")
    
    args = parser.parse_args()
    
    topic_dir = Path(args.topic_dir).resolve()
    
    if args.command == "extract":
        cmd_extract(topic_dir)
    elif args.command == "apply":
        cmd_apply(topic_dir, Path(args.tag_map), Path(args.alias_map))

if __name__ == "__main__":
    main()
