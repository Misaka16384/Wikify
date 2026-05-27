import argparse
import os
import re
import subprocess
from datetime import datetime

def extract_title(tex_content):
    match = re.search(r'\\title\{([^}]+)\}', tex_content)
    if match:
        return match.group(1).strip()
    return None

def main():
    parser = argparse.ArgumentParser(description="Convert TeX to Markdown using Pandoc.")
    parser.add_argument("tex_path", help="Path to the .tex file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args()

    tex_path = args.tex_path
    output_dir = args.output_dir

    if not os.path.isfile(tex_path):
        print(f"Error: File '{tex_path}' not found.")
        exit(1)

    with open(tex_path, 'r', encoding='utf-8', errors='ignore') as f:
        tex_content = f.read()

    base_name = os.path.basename(tex_path)
    slug = os.path.splitext(base_name)[0]
    
    title = extract_title(tex_content)
    if not title:
        title = slug.replace('_', ' ').replace('-', ' ').title()

    # Look for a .bib file in the same directory
    tex_dir = os.path.dirname(os.path.abspath(tex_path))
    bib_files = [f for f in os.listdir(tex_dir) if f.endswith('.bib')]
    bib_arg = ""
    if bib_files:
        bib_path = os.path.join(tex_dir, bib_files[0])
        bib_arg = f"--bibliography=\"{bib_path}\""

    # Determine type (papers or articles) based on output_dir
    # e.g., output_dir might be `<TOPIC_DIR>/raw/papers`
    doc_type = os.path.basename(os.path.normpath(output_dir))
    if doc_type not in ['papers', 'articles', 'notes', 'repos']:
        doc_type = 'papers'

    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"{today}-{slug}.md"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    # We will generate a temporary markdown file with pandoc, then prepend frontmatter
    temp_md_path = output_path + ".tmp"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pandoc_crossref_path = os.path.join(script_dir, "pandoc-crossref.exe")
    if not os.path.exists(pandoc_crossref_path):
        pandoc_crossref_path = "pandoc-crossref" # Fallback to PATH

    cmd = [
        "pandoc",
        tex_path,
        "--filter", pandoc_crossref_path,
        "--citeproc",
        "-t", "markdown"
    ]
    if bib_arg:
        cmd.extend(["--bibliography", bib_path])
    
    cmd.extend(["-o", temp_md_path])

    print(f"Running Pandoc: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Pandoc conversion failed:")
        print(result.stderr)
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)
        exit(1)

    with open(temp_md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    os.remove(temp_md_path)

    frontmatter = f"""---
title: "{title}"
source: "{tex_path}"
type: {doc_type}
ingested: {today}
tags: []
summary: "Converted from LaTeX."
---
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + "\n" + md_content)

    print(f"Successfully converted and saved to {output_path}")

if __name__ == "__main__":
    main()
