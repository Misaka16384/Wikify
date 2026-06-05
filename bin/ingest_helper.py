#!/usr/bin/env python
"""Process inbox files by extracting their title/date, parsing existing frontmatter,
injecting standard YAML frontmatter, slugifying filenames, and copying/moving them to raw/<type>/YYYY-MM-DD-<slug>.md.
"""

import os
import sys
import re
import argparse
import shutil
import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    from wiki_common import split_frontmatter_text, parse_frontmatter_text, slugify, atomic_write
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wiki_common import split_frontmatter_text, parse_frontmatter_text, slugify, atomic_write

def clean_title(title_str: str) -> str:
    # Remove surrounding quotes and strip whitespace
    title_str = title_str.strip()
    if title_str.startswith('"') and title_str.endswith('"'):
        title_str = title_str[1:-1].strip()
    elif title_str.startswith("'") and title_str.endswith("'"):
        title_str = title_str[1:-1].strip()
    return title_str

def main():
    parser = argparse.ArgumentParser(description="Ingest source files into raw/ folder.")
    parser.add_argument("--file", required=True, help="Path to the source file to ingest")
    parser.add_argument("--type", required=True, help="Target raw subdirectory/type (e.g. papers, articles, notes)")
    parser.add_argument("--topic-dir", default=".", help="Topic directory path (default: current directory)")
    parser.add_argument("--move", action="store_true", help="Move the file instead of copying")
    args = parser.parse_args()

    input_file = Path(args.file).resolve()
    if not input_file.exists() or not input_file.is_file():
        print(f"Error: Input file {input_file} does not exist.", file=sys.stderr)
        sys.exit(1)

    topic_path = Path(args.topic_dir).resolve()
    dest_dir = topic_path / "raw" / args.type
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Read original content
    try:
        with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Failed to read {input_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse existing frontmatter and body
    parts = split_frontmatter_text(content)
    if parts:
        fm_text, body = parts
        fm_data = parse_frontmatter_text(fm_text)
    else:
        body = content
        fm_data = {}

    # Extract title
    title = fm_data.get("title")
    if title:
        title = clean_title(str(title))
    else:
        # Search for first # Heading in the body
        match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
        if match:
            title = clean_title(match.group(1))
        else:
            # Fallback to filename stem
            title = input_file.stem.replace('_', ' ').replace('-', ' ').title()

    # Extract or determine date (ingested / created)
    ingested_date = fm_data.get("ingested") or fm_data.get("created") or fm_data.get("date")
    if ingested_date:
        if isinstance(ingested_date, datetime.date):
            ingested_date = ingested_date.isoformat()
        else:
            ingested_date = str(ingested_date).strip()
    else:
        # Try to parse date from filename: YYYY-MM-DD
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', input_file.name)
        if date_match:
            ingested_date = date_match.group(1)
        else:
            ingested_date = datetime.date.today().isoformat()

    # Build final frontmatter
    final_fm = fm_data.copy()
    final_fm["title"] = title
    final_fm["type"] = args.type
    final_fm["ingested"] = ingested_date

    # Ensure other mandatory fields are set
    if "source" not in final_fm:
        final_fm["source"] = "Unknown"
    if "tags" not in final_fm:
        final_fm["tags"] = ["ingested"]
    elif isinstance(final_fm["tags"], str):
        final_fm["tags"] = [final_fm["tags"]]
    if "summary" not in final_fm:
        # If there's an existing summary, use it. Otherwise, default
        final_fm["summary"] = "Ingested source file."

    # Convert tags to a list of strings if they are not
    if not isinstance(final_fm["tags"], list):
        final_fm["tags"] = [str(final_fm["tags"])]

    # Regenerate YAML frontmatter
    if yaml is not None:
        new_fm_text = yaml.safe_dump(final_fm, allow_unicode=True, default_flow_style=False).strip()
    else:
        # Simple manual fallback if pyyaml is somehow not loading
        tags_str = ", ".join(f'"{t}"' for t in final_fm["tags"])
        new_fm_text = (
            f"title: \"{title}\"\n"
            f"source: \"{final_fm['source']}\"\n"
            f"type: \"{args.type}\"\n"
            f"ingested: {ingested_date}\n"
            f"tags: [{tags_str}]\n"
            f"summary: \"{final_fm['summary']}\""
        )
        for k, v in final_fm.items():
            if k not in ("title", "source", "type", "ingested", "tags", "summary"):
                new_fm_text += f"\n{k}: {v}"

    # Build new file content
    new_content = f"---\n{new_fm_text}\n---\n"
    if not body.startswith("\n"):
        new_content += "\n"
    new_content += body

    # Generate slugified destination filename
    slug = slugify(title)
    dest_filename = f"{ingested_date}-{slug}.md"
    dest_file = dest_dir / dest_filename

    # Write content atomically
    try:
        atomic_write(dest_file, new_content)
        print(f"Ingested file to: {dest_file}")
    except Exception as e:
        print(f"Error: Failed to write to {dest_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Move/delete original if requested
    if args.move:
        try:
            input_file.unlink()
            print(f"Removed original file: {input_file}")
        except Exception as e:
            print(f"Warning: Failed to delete original file {input_file}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
