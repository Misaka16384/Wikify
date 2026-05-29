import argparse
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

# Add bin/ directory to path for config_loader
_bin_dir = os.path.dirname(os.path.abspath(__file__))
if _bin_dir not in sys.path:
    sys.path.insert(0, _bin_dir)
from config_loader import load_config, get as cfg_get

def extract_title(tex_content):
    match = re.search(r'\\title\{([^}]+)\}', tex_content)
    if match:
        return match.group(1).strip()
    return None

def find_main_tex(directory):
    # Find the main tex file by looking for \documentclass
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tex'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if r'\documentclass' in content:
                        return path
    # Fallback to any .tex if no documentclass is found
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tex'):
                return os.path.join(root, file)
    return None

def main():
    parser = argparse.ArgumentParser(description="Convert TeX/arXiv tar.gz to Markdown using Pandoc.")
    parser.add_argument("input_path", help="Path to the .tex or .tar.gz file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args()

    input_path = args.input_path
    output_dir = args.output_dir

    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' not found.")
        sys.exit(1)

    base_name = os.path.basename(input_path)
    if base_name.endswith('.tar.gz'):
        slug = base_name[:-7]
    elif base_name.endswith('.tex'):
        slug = base_name[:-4]
    else:
        slug = os.path.splitext(base_name)[0]

    temp_dir_obj = None
    if input_path.endswith('.tar.gz'):
        temp_dir_obj = tempfile.TemporaryDirectory()
        extract_dir = temp_dir_obj.name
        print(f"Extracting tar.gz to {extract_dir}...")
        with tarfile.open(input_path, "r:gz") as tar:
            # Safe extraction: prevent path traversal (CVE-2007-4559)
            for member in tar.getmembers():
                member_path = os.path.normpath(os.path.join(extract_dir, member.name))
                if not member_path.startswith(os.path.normpath(extract_dir)):
                    raise ValueError(f"Attempted path traversal in tar: {member.name}")
            try:
                tar.extractall(path=extract_dir, filter='data')
            except TypeError:
                # Python < 3.12 fallback
                tar.extractall(path=extract_dir)
        tex_path = find_main_tex(extract_dir)
        if not tex_path:
            print("Error: Could not find main .tex file in the archive.")
            sys.exit(1)
        tex_dir = os.path.dirname(tex_path)
    else:
        tex_path = input_path
        tex_dir = os.path.dirname(os.path.abspath(tex_path))

    print(f"Using main TeX file: {tex_path}")

    with open(tex_path, 'r', encoding='utf-8', errors='ignore') as f:
        tex_content = f.read()

    title = extract_title(tex_content)
    if not title:
        title = slug.replace('_', ' ').replace('-', ' ').title()

    # Look for a .bib file in the same directory
    bib_files = [f for f in os.listdir(tex_dir) if f.endswith('.bib')]
    bib_arg = ""
    bib_path = ""
    if bib_files:
        bib_path = os.path.join(tex_dir, bib_files[0])
        bib_arg = f"--bibliography=\"{bib_path}\""
        print(f"Found bibliography: {bib_path}")

    doc_type = os.path.basename(os.path.normpath(output_dir))
    if doc_type not in ['papers', 'articles', 'notes', 'repos']:
        doc_type = 'papers'

    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"{today}-{slug}.md"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    temp_md_path = output_path + ".tmp"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pandoc_crossref_path = os.path.join(script_dir, "pandoc-crossref.exe")

    import shutil

    # Load unified config for tool paths
    _cfg = load_config()

    # 查找 pandoc-crossref：环境变量 > 统一配置 > PATH > 脚本目录
    pandoc_crossref_exec = os.environ.get("PANDOC_CROSSREF_PATH")
    if not pandoc_crossref_exec or not os.path.exists(pandoc_crossref_exec):
        pandoc_crossref_exec = cfg_get(_cfg, "tools.pandoc_crossref_path", "") or None
    if not pandoc_crossref_exec or not os.path.exists(pandoc_crossref_exec):
        pandoc_crossref_exec = shutil.which("pandoc-crossref")
    if not pandoc_crossref_exec:
        if os.path.exists(pandoc_crossref_path):
            pandoc_crossref_exec = pandoc_crossref_path

    # 查找 pandoc：环境变量 > 统一配置 > PATH > LOCALAPPDATA
    pandoc_exec = os.environ.get("PANDOC_PATH")
    if not pandoc_exec or not os.path.exists(pandoc_exec):
        pandoc_exec = cfg_get(_cfg, "tools.pandoc_path", "") or None
    if not pandoc_exec or not os.path.exists(pandoc_exec):
        pandoc_exec = shutil.which("pandoc")
    if not pandoc_exec:
        # Fallback to standard local installation path
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        fallback = os.path.join(local_appdata, "Pandoc", "pandoc.exe")
        if os.path.exists(fallback):
            pandoc_exec = fallback
        else:
            pandoc_exec = "pandoc" # Will likely fail, but last resort

    cmd = [
        pandoc_exec,
        tex_path,
        "--citeproc",
        "-t", "markdown"
    ]
    if pandoc_crossref_exec:
        # Insert filter before citeproc
        cmd.insert(2, "--filter")
        cmd.insert(3, pandoc_crossref_exec)
    else:
        print("Warning: pandoc-crossref not found. Cross-references may not render correctly.")
    if bib_arg:
        cmd.extend(["--bibliography", bib_path])
    
    cmd.extend(["-o", temp_md_path])

    print(f"Running Pandoc: {' '.join(cmd)}")
    
    # Run from the tex directory to resolve image paths correctly
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=tex_dir)

    if result.returncode != 0:
        print("Pandoc conversion failed:")
        print(result.stderr)
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)
        if temp_dir_obj:
            temp_dir_obj.cleanup()
        sys.exit(1)

    with open(temp_md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    os.remove(temp_md_path)

    frontmatter = f"""---
title: "{title}"
source: "{input_path}"
type: {doc_type}
ingested: {today}
tags: []
summary: "Converted from LaTeX/arXiv source."
---
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + "\n" + md_content)

    print(f"Successfully converted and saved to {output_path}")

    if temp_dir_obj:
        temp_dir_obj.cleanup()

if __name__ == "__main__":
    main()
