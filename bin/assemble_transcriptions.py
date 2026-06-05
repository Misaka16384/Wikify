#!/usr/bin/env python
"""Stitch page-by-page OCR transcription txt/md files under a directory into a single markdown file.
"""

import os
import sys
import re
import argparse
import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    from wiki_common import atomic_write
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wiki_common import atomic_write

def extract_page_number(file_path: Path) -> int:
    filename = file_path.name
    # Search for any digits in the filename
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return 999999  # Place files without numbers at the end

def main():
    parser = argparse.ArgumentParser(description="Assemble page-by-page transcriptions into a single markdown file.")
    parser.add_argument("--dir", required=True, help="Directory containing page transcription files")
    parser.add_argument("--out", required=True, help="Output markdown file path")
    parser.add_argument("--title", help="Title of the document (default: folder name)")
    parser.add_argument("--source", default="Unknown", help="Source of the document")
    parser.add_argument("--type", default="papers", help="Type of document (e.g. papers, articles)")
    parser.add_argument("--tags", default="assembled", help="Comma-separated list of tags")
    parser.add_argument("--summary", default="Assembled transcriptions.", help="Summary of the document")
    args = parser.parse_args()

    input_dir = Path(args.dir).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input directory {input_dir} does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Gather txt and md files (excluding _index.md and subdirectories)
    page_files = []
    for p in input_dir.iterdir():
        if p.is_file() and p.suffix in (".txt", ".md") and p.name != "_index.md":
            page_files.append(p)

    # Sort files numerically by page number, then alphabetically by name
    page_files.sort(key=lambda x: (extract_page_number(x), x.name.lower()))

    # Build document title
    title = args.title if args.title else input_dir.name.replace('-', ' ').replace('_', ' ').title()

    # Build tags list
    tag_list = [t.strip() for t in args.tags.split(',') if t.strip()]

    # Frontmatter structure
    frontmatter_dict = {
        "title": title,
        "source": args.source,
        "type": args.type,
        "ingested": datetime.date.today().isoformat(),
        "tags": tag_list,
        "summary": args.summary
    }

    # Construct YAML frontmatter
    if yaml is not None:
        # Use yaml dump but format tags compactly if possible, or just standard safe_dump
        fm_text = yaml.safe_dump(frontmatter_dict, allow_unicode=True, default_flow_style=False).strip()
    else:
        # Fallback manual formatting in case yaml is absent
        tags_str = ", ".join(f'"{t}"' for t in tag_list)
        fm_text = (
            f"title: \"{title}\"\n"
            f"source: \"{args.source}\"\n"
            f"type: \"{args.type}\"\n"
            f"ingested: {frontmatter_dict['ingested']}\n"
            f"tags: [{tags_str}]\n"
            f"summary: \"{args.summary}\""
        )

    # Assemble document content
    content_parts = []
    content_parts.append(f"---\n{fm_text}\n---")
    content_parts.append(f"\n# {title}\n")

    for file_path in page_files:
        page_num = extract_page_number(file_path)
        # Fallback if page_num is 999999
        page_label = str(page_num) if page_num != 999999 else "unknown"
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                page_content = f.read().strip()
            content_parts.append(f"\n<!-- Page {page_label} -->\n\n{page_content}\n")
        except Exception as e:
            print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)

    full_content = "".join(content_parts)

    output_path = Path(args.out).resolve()
    # Create parent directories if they don't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        atomic_write(output_path, full_content)
        print(f"Successfully assembled {len(page_files)} pages into: {output_path}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
