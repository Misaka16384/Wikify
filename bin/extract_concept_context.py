import os
import sys
import argparse
import re
import yaml

def extract_frontmatter(content):
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
                return fm if fm else {}
            except Exception:
                pass
    return {}

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]+', '-', text.lower()).strip('-')

def extract_concept_context(concept_name, topic_dir):
    slug = slugify(concept_name)
    refs_dir = os.path.join(topic_dir, "wiki", "references")
    concept_file = os.path.join(topic_dir, "wiki", "concepts", f"{slug}.md")
    
    aliases = [concept_name]
    
    # Check if concept file exists to extract aliases
    if os.path.exists(concept_file):
        with open(concept_file, 'r', encoding='utf-8') as f:
            fm = extract_frontmatter(f.read())
            if fm and 'aliases' in fm and fm['aliases']:
                if isinstance(fm['aliases'], list):
                    aliases.extend(fm['aliases'])
                elif isinstance(fm['aliases'], str):
                    aliases.append(fm['aliases'])
                    
    # Clean up aliases and create regex pattern
    aliases = list(set([a.strip() for a in aliases if a.strip()]))
    # Escape regex chars in aliases
    escaped_aliases = [re.escape(a) for a in aliases]
    # Match either [[Alias]] or just the raw word. Actually, let's just match the raw word to be broad.
    pattern_str = r'\b(' + '|'.join(escaped_aliases) + r')\b'
    pattern = re.compile(pattern_str, re.IGNORECASE)
    
    results = []
    
    for filename in os.listdir(refs_dir):
        if not filename.endswith(".md"): continue
        
        filepath = os.path.join(refs_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        fm = extract_frontmatter(content)
        summary = fm.get('summary', 'No summary provided.')
        title = fm.get('title', filename)
        
        # Split by paragraphs
        paragraphs = re.split(r'\n\s*\n', content)
        
        matched_paragraphs = []
        for i, para in enumerate(paragraphs):
            # Skip yaml frontmatter blocks
            if para.startswith('---') and 'title:' in para:
                continue
                
            if pattern.search(para):
                # get +/- 1 paragraph context
                start = max(0, i - 1)
                end = min(len(paragraphs), i + 2)
                context_block = "\n\n".join(paragraphs[start:end])
                
                # avoid adding duplicate overlapping blocks
                if not matched_paragraphs or context_block not in matched_paragraphs[-1]:
                    matched_paragraphs.append(context_block)
                    
        if matched_paragraphs:
            res = f"### Source: [[{title}]] ({filename})\n"
            res += f"**Summary**: {summary}\n\n"
            for idx, block in enumerate(matched_paragraphs, 1):
                res += f"**Context Block {idx}:**\n{block.strip()}\n\n---\n"
            results.append(res)
            
    scratch_dir = os.path.join(topic_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    output_file = os.path.join(scratch_dir, f"concept_context_{slug}.md")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# RAG Context: {concept_name}\n\n")
        f.write(f"**Aliases Search terms**: {', '.join(aliases)}\n\n")
        if not results:
            f.write("*No references found in the knowledge base.*")
        else:
            f.write("\n".join(results))
            
    print(f"Extracted context saved to {output_file}")
    print(f"Total referencing sources found: {len(results)}")

def main():
    parser = argparse.ArgumentParser(description="Extract surrounding context for a concept from all papers")
    parser.add_argument("--name", required=True, help="Concept Name")
    parser.add_argument("--topic-dir", required=True, help="Topic directory")
    args = parser.parse_args()
    
    extract_concept_context(args.name, args.topic_dir)

if __name__ == "__main__":
    main()
