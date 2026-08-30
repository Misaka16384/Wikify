import os
import sys
import argparse
import re
from magi.core.wiki_common import slugify, parse_frontmatter, split_frontmatter_text


def build_alias_pattern(aliases):
    """Build a search regex from aliases. ASCII terms get word boundaries to
    avoid matching inside larger words; non-ASCII terms (e.g. CJK) use plain
    matching because `\\b` never fires between two CJK characters."""
    parts = []
    for a in aliases:
        esc = re.escape(a)
        # Apply \b only when the alias edges are ASCII word characters.
        left = r"\b" if a[:1].isascii() and (a[:1].isalnum() or a[:1] == "_") else ""
        right = r"\b" if a[-1:].isascii() and (a[-1:].isalnum() or a[-1:] == "_") else ""
        parts.append(f"{left}(?:{esc}){right}")
    return re.compile("|".join(parts), re.IGNORECASE)

def extract_concept_context(concept_name, topic_dir):
    import json
    slug = slugify(concept_name)
    if not slug:
        print(json.dumps({"error": f"Concept name '{concept_name}' produces an empty slug"}))
        sys.exit(2)
    refs_dir = os.path.join(topic_dir, "wiki", "references")
    concept_file = os.path.join(topic_dir, "wiki", "concepts", f"{slug}.md")
    
    aliases = [concept_name]
    
    # Check if concept file exists to extract aliases
    if os.path.exists(concept_file):
        with open(concept_file, 'r', encoding='utf-8') as f:
            fm = parse_frontmatter(f.read())
            if fm and 'aliases' in fm and fm['aliases']:
                if isinstance(fm['aliases'], list):
                    aliases.extend(fm['aliases'])
                elif isinstance(fm['aliases'], str):
                    aliases.append(fm['aliases'])
                    
    # Clean up aliases and create regex pattern
    aliases = list(set([a.strip() for a in aliases if a.strip()]))
    if not aliases:
        print(json.dumps({"error": f"No usable search terms for concept '{concept_name}'"}))
        sys.exit(2)
    pattern = build_alias_pattern(aliases)
    
    results = []
    
    if not os.path.isdir(refs_dir):
        import json
        print(json.dumps({"error": f"References directory not found: {refs_dir}"}))
        sys.exit(2)
    for filename in os.listdir(refs_dir):
        if not filename.endswith(".md"): continue
        # Skip auto-generated index files: their tables would pollute RAG context.
        if filename == "_index.md": continue

        filepath = os.path.join(refs_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        fm = parse_frontmatter(content)
        summary = fm.get('summary', 'No summary provided.')
        title = fm.get('title', filename)
        
        # Strip frontmatter once up front; search only the body
        fm_parts = split_frontmatter_text(content)
        body = fm_parts[1] if fm_parts is not None else content
        paragraphs = re.split(r'\n\s*\n', body)

        matched_paragraphs = []
        for i, para in enumerate(paragraphs):
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

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki context", description="Extract surrounding context for a concept from all papers")
    parser.add_argument("--name", required=True, help="Concept Name")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir",
                        help="Project directory (default: project root discovered from cwd)")
    args = parser.parse_args(argv)

    topic_dir = args.topic_dir
    if not topic_dir:
        import json
        from magi.core.workspace import find_workspace_root
        root = find_workspace_root()
        if root is None:
            print(json.dumps({"error": "No project found from cwd. "
                                       "Run inside a project directory or pass --topic-dir <path>."}))
            return 2
        topic_dir = str(root)

    extract_concept_context(args.name, topic_dir)

if __name__ == "__main__":
    sys.exit(main())
