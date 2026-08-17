#!/usr/bin/env python
"""Scan raw/ for markdown files that do not have corresponding compiled reference files.

Outputs a newline-separated list of relative paths of uncompiled source files.
"""

import sys
import argparse
from pathlib import Path

from magi.core.wiki_common import parse_frontmatter, slugify

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki uncompiled", description="Detect uncompiled source files.")
    parser.add_argument("--topic-dir", default=".", help="Topic directory path (default: current directory)")
    args = parser.parse_args(argv)

    topic_path = Path(args.topic_dir).resolve()
    raw_dir = topic_path / "raw"
    refs_dir = topic_path / "wiki" / "references"

    if not raw_dir.exists():
        # If raw/ does not exist, there are no uncompiled source files
        return

    # Find all raw files recursively (excluding _index.md)
    raw_files = []
    for p in raw_dir.rglob("*"):
        if p.is_file() and p.suffix in (".md", ".markdown") and p.name != "_index.md":
            raw_files.append(p)

    compiled_paths = set()
    compiled_slugs = set()

    if refs_dir.exists():
        for p in refs_dir.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".markdown") and p.name != "_index.md":
                # Read compiled file frontmatter
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        content = f.read()
                    fm = parse_frontmatter(content)
                except Exception as e:
                    print(f"Warning: Failed to read/parse {p}: {e}", file=sys.stderr)
                    continue

                sources = fm.get("sources", [])
                if isinstance(sources, str):
                    sources = [sources]
                elif not isinstance(sources, list):
                    sources = []

                for source in sources:
                    if not isinstance(source, str):
                        continue
                    # 1. Try to resolve as relative path
                    # Check relative to topic dir
                    resolved_topic = (topic_path / source).resolve()
                    if resolved_topic.is_file():
                        compiled_paths.add(resolved_topic)
                        continue
                    # Check relative to the compiled file itself
                    resolved_local = (p.parent / source).resolve()
                    if resolved_local.is_file():
                        compiled_paths.add(resolved_local)
                        continue

                    # 2. Fallback: Slugified names of the files in sources list
                    source_stem = Path(source).stem
                    source_slug = slugify(source_stem)
                    compiled_slugs.add(source_slug)

                # 3. Fallback: Slugified name of the compiled file itself
                compiled_file_slug = slugify(p.stem)
                compiled_slugs.add(compiled_file_slug)

    # Determine uncompiled files
    uncompiled = []
    for raw_file in raw_files:
        # Check if the path is matched
        if raw_file.resolve() in compiled_paths:
            continue
        # Check if the slug is matched
        raw_slug = slugify(raw_file.stem)
        if raw_slug in compiled_slugs:
            continue
        
        # Keep relative path to topic_path (using POSIX separator)
        rel_path = raw_file.relative_to(topic_path).as_posix()
        uncompiled.append(rel_path)

    for path in sorted(uncompiled):
        print(path)

if __name__ == "__main__":
    sys.exit(main())
