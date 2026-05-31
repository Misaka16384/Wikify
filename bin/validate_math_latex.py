import os
import re
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

# Try to import pylatexenc as fallback
try:
    from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError
    HAS_PYLATEXENC = True
except ImportError:
    HAS_PYLATEXENC = False

def validate_math_pylatexenc(content):
    issues = []
    valid_blocks = []
    valid_inlines = []

    # Blank out fenced code blocks (preserving line count for accurate error
    # line numbers) so math-looking snippets inside ``` fences aren't extracted
    # and validated as if they were real equations.
    content = re.sub(
        r'```.*?```',
        lambda m: "\n" * m.group(0).count("\n"),
        content,
        flags=re.DOTALL,
    )

    # Extract block math
    block_pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    for match in block_pattern.finditer(content):
        math_content = match.group(1)
        start_index = match.start()
        line_num = content.count('\n', 0, start_index) + 1
        try:
            walker = LatexWalker(math_content, tolerant_parsing=False)
            walker.get_latex_nodes()
            valid_blocks.append((math_content, line_num))
        except Exception as e:
            issues.append(f"Line {line_num} [Block Math]: {e}")

    # Extract inline math
    inline_pattern = re.compile(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', re.DOTALL)
    for match in inline_pattern.finditer(content):
        math_content = match.group(1)
        start_index = match.start()
        line_num = content.count('\n', 0, start_index) + 1
        try:
            walker = LatexWalker(math_content, tolerant_parsing=False)
            walker.get_latex_nodes()
            valid_inlines.append((math_content, line_num))
        except Exception as e:
            issues.append(f"Line {line_num} [Inline Math]: {e}")

    return issues, valid_blocks, valid_inlines

def validate_math_pdflatex(valid_blocks, valid_inlines):
    issues = []
    tex_lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amssymb,amsfonts}",
        r"\begin{document}"
    ]
    
    tex_to_md_map = {}
    current_tex_line = len(tex_lines) + 1

    def add_snippet(math_content, is_block, md_line):
        nonlocal current_tex_line
        # To isolate errors, we wrap each snippet in a new paragraph/math mode
        # and record mapping for all lines of this snippet
        lines = math_content.strip().split('\n')
        
        if is_block:
            # Snippets that are already a top-level display-math environment must
            # not be wrapped in equation*, or pdflatex errors with
            # "Bad math environment delimiter" (a false positive).
            top_level_envs = [
                'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
                'equation', 'equation*', 'alignat', 'alignat*', 'flalign', 'flalign*',
                'eqnarray', 'eqnarray*',
            ]
            is_top_level = any(rf"\begin{{{env}}}" in math_content for env in top_level_envs)
            if not is_top_level:
                tex_lines.append(r"\begin{equation*}")
            current_tex_line += 1
            
            for line in lines:
                tex_lines.append(line)
                tex_to_md_map[current_tex_line] = md_line
                current_tex_line += 1
                
            if not is_top_level:
                tex_lines.append(r"\end{equation*}")
            current_tex_line += 1
        else:
            tex_lines.append(r"$")
            current_tex_line += 1
            
            for line in lines:
                tex_lines.append(line)
                tex_to_md_map[current_tex_line] = md_line
                current_tex_line += 1
                
            tex_lines.append(r"$")
            current_tex_line += 1
            
        tex_lines.append("") # empty line
        current_tex_line += 1

    # Extract block math
    for math_content, md_line in valid_blocks:
        add_snippet(math_content, is_block=True, md_line=md_line)

    # Extract inline math
    for math_content, md_line in valid_inlines:
        add_snippet(math_content, is_block=False, md_line=md_line)

    tex_lines.append(r"\end{document}")
    
    if len(tex_to_md_map) == 0:
        return [] # no math found

    tex_source = "\n".join(tex_lines)
    
    with tempfile.TemporaryDirectory() as tempdir:
        tex_file = os.path.join(tempdir, "temp.tex")
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_source)
            
        # Run pdflatex
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "temp.tex"]
        # we don't strictly need halt-on-error. We want to catch ALL errors.
        cmd = ["pdflatex", "-interaction=nonstopmode", "temp.tex"]
        
        # It's fine if it fails (it will if there are syntax errors)
        subprocess.run(cmd, cwd=tempdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        log_file = os.path.join(tempdir, "temp.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read().splitlines()
                
            current_error = None
            for i, line in enumerate(log_content):
                if line.startswith("! "):
                    current_error = line[2:].strip()
                elif current_error and line.startswith("l."):
                    match = re.search(r'^l\.(\d+)', line)
                    if match:
                        tex_line = int(match.group(1))
                        # Find the closest mapped line if exact match not found
                        md_line = tex_to_md_map.get(tex_line)
                        if md_line is None:
                            # search backwards for nearest valid mapping
                            for offset in range(1, 10):
                                if (tex_line - offset) in tex_to_md_map:
                                    md_line = tex_to_md_map[tex_line - offset]
                                    break
                        if md_line is None:
                            md_line = "Unknown"
                        
                        issues.append(f"Line {md_line}: {current_error}")
                    current_error = None
                    
    # Deduplicate issues maintaining order
    seen = set()
    unique_issues = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique_issues.append(issue)
            
    return unique_issues

def process_file(file_path, use_pdflatex=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    issues, valid_blocks, valid_inlines = validate_math_pylatexenc(content)
    if use_pdflatex and (valid_blocks or valid_inlines):
        pdflatex_issues = validate_math_pdflatex(valid_blocks, valid_inlines)
        issues.extend(pdflatex_issues)
    
    if issues:
        print(f"[\033[93mWARNING\033[0m] Math syntax errors in {os.path.basename(file_path)}:")
        for issue in issues:
            print(f"    - {issue}")
        return True
    return False

def process_directory(directory):
    print(f"Validating math formulas in markdown files under: {directory}")
    
    has_pdflatex = shutil.which("pdflatex") is not None
    if has_pdflatex:
        print("Using native pdflatex for deep semantic validation (detects double subscripts, missing braces, etc.)")
    elif HAS_PYLATEXENC:
        print("pdflatex not found. Falling back to pylatexenc for structural validation (detects missing braces).")
    else:
        print("Neither pdflatex nor pylatexenc found. Skipping math validation.")
        return

    files_with_issues = 0
    total_files = 0
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.endswith('.md'):
                total_files += 1
                file_path = os.path.join(root, file)
                if process_file(file_path, use_pdflatex=has_pdflatex):
                    files_with_issues += 1
                    
    if files_with_issues > 0:
        print(f"\nCompleted: Found math errors in {files_with_issues} out of {total_files} files.")
    else:
        print(f"\nCompleted: All {total_files} files passed math validation cleanly.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_math_latex.py <TOPIC_DIR_OR_FILE>")
        sys.exit(1)
        
    target = sys.argv[1]
    if not os.path.exists(target):
        print(f"Path not found: {target}")
        sys.exit(1)
        
    if os.path.isdir(target):
        process_directory(target)
    else:
        has_pdflatex = shutil.which("pdflatex") is not None
        if has_pdflatex:
            print(f"Validating {os.path.basename(target)} using native pdflatex...")
        elif HAS_PYLATEXENC:
            print(f"Validating {os.path.basename(target)} using pylatexenc (structural only)...")
        else:
            print("Validation skipped (missing dependencies).")
            sys.exit(0)
        process_file(target, use_pdflatex=has_pdflatex)
