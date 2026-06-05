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

    has_pdflatex = shutil.which("pdflatex") is not None
    if not HAS_PYLATEXENC and not has_pdflatex:
        return issues, valid_blocks, valid_inlines

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
        end_index = match.end()
        line_num = content.count('\n', 0, start_index) + 1
        end_line = content.count('\n', 0, end_index) + 1
        if HAS_PYLATEXENC:
            try:
                walker = LatexWalker(math_content, tolerant_parsing=False)
                walker.get_latex_nodes()
                valid_blocks.append((math_content, line_num, end_line))
            except Exception as e:
                lineno = getattr(e, 'lineno', 1)
                colno = getattr(e, 'colno', 1)
                math_lines = math_content.split('\n')
                if 0 <= lineno - 1 < len(math_lines):
                    line_str = math_lines[lineno - 1]
                    pointer = " " * (colno - 1) + "^"
                    context = f"{line_str}\n{pointer}"
                else:
                    pos = getattr(e, 'pos', 0)
                    start_context = max(0, pos - 40)
                    end_context = min(len(math_content), pos + 40)
                    line_str = math_content[start_context:end_context]
                    pointer = " " * (pos - start_context) + "^"
                    context = f"{line_str}\n{pointer}"
                issues.append({
                    "md_line": line_num,
                    "md_end_line": end_line,
                    "error": str(e),
                    "context": context,
                    "is_block": True
                })
        else:
            valid_blocks.append((math_content, line_num, end_line))

    # Extract inline math
    inline_pattern = re.compile(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', re.DOTALL)
    for match in inline_pattern.finditer(content):
        math_content = match.group(1)
        start_index = match.start()
        end_index = match.end()
        line_num = content.count('\n', 0, start_index) + 1
        end_line = content.count('\n', 0, end_index) + 1
        if HAS_PYLATEXENC:
            try:
                walker = LatexWalker(math_content, tolerant_parsing=False)
                walker.get_latex_nodes()
                valid_inlines.append((math_content, line_num, end_line))
            except Exception as e:
                lineno = getattr(e, 'lineno', 1)
                colno = getattr(e, 'colno', 1)
                math_lines = math_content.split('\n')
                if 0 <= lineno - 1 < len(math_lines):
                    line_str = math_lines[lineno - 1]
                    pointer = " " * (colno - 1) + "^"
                    context = f"{line_str}\n{pointer}"
                else:
                    pos = getattr(e, 'pos', 0)
                    start_context = max(0, pos - 40)
                    end_context = min(len(math_content), pos + 40)
                    line_str = math_content[start_context:end_context]
                    pointer = " " * (pos - start_context) + "^"
                    context = f"{line_str}\n{pointer}"
                issues.append({
                    "md_line": line_num,
                    "md_end_line": end_line,
                    "error": str(e),
                    "context": context,
                    "is_block": False
                })
        else:
            valid_inlines.append((math_content, line_num, end_line))

    return issues, valid_blocks, valid_inlines

def parse_latex_log(log_lines):
    issues = []
    current_error = None
    i = 0
    while i < len(log_lines):
        line = log_lines[i]
        if line.startswith("! "):
            current_error = line[2:].strip()
            j = i + 1
            while j < len(log_lines) and not log_lines[j].startswith("! ") and not log_lines[j].startswith("l."):
                j += 1
            if j < len(log_lines) and log_lines[j].startswith("l."):
                l_line = log_lines[j]
                match = re.search(r'^l\.(\d+)\s*(.*)', l_line)
                if match:
                    tex_line = int(match.group(1))
                    part1 = match.group(2)
                    part2 = ""
                    if j + 1 < len(log_lines):
                        next_line = log_lines[j + 1]
                        if not next_line.startswith("!") and not next_line.startswith("l."):
                            part2 = next_line
                    
                    issues.append({
                        "error": current_error,
                        "tex_line": tex_line,
                        "part1": part1,
                        "part2": part2
                    })
                i = j
        i += 1
    return issues

def validate_math_pdflatex(valid_blocks, valid_inlines):
    issues = []
    tex_lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amssymb,amsfonts}",
        r"\begin{document}"
    ]
    
    tex_to_md_map = {}
    current_tex_line = len(tex_lines) + 1

    def add_snippet(math_content, is_block, md_line, md_end_line):
        nonlocal current_tex_line
        lines = math_content.split('\n')
        
        if is_block:
            top_level_envs = [
                'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
                'equation', 'equation*', 'alignat', 'alignat*', 'flalign', 'flalign*',
                'eqnarray', 'eqnarray*',
            ]
            stripped = math_content.strip()
            is_top_level = any(stripped.startswith(rf"\begin{{{env}}}") for env in top_level_envs)
            if not is_top_level:
                tex_lines.append(r"\begin{equation*}")
                current_tex_line += 1
            
            for idx, line in enumerate(lines):
                if line.strip() == "":
                    tex_lines.append("%")
                else:
                    tex_lines.append(line)
                tex_to_md_map[current_tex_line] = (md_line, md_end_line, is_block)
                current_tex_line += 1
                
            if not is_top_level:
                tex_lines.append(r"\end{equation*}")
                current_tex_line += 1
        else:
            tex_lines.append(r"$")
            current_tex_line += 1
            
            for idx, line in enumerate(lines):
                if line.strip() == "":
                    tex_lines.append("%")
                else:
                    tex_lines.append(line)
                tex_to_md_map[current_tex_line] = (md_line, md_end_line, is_block)
                current_tex_line += 1
                
            tex_lines.append(r"$")
            current_tex_line += 1
            
        tex_lines.append("")
        current_tex_line += 1

    # Extract block math
    for item in valid_blocks:
        if len(item) == 3:
            math_content, md_line, md_end_line = item
        else:
            math_content, md_line = item
            md_end_line = md_line + math_content.count('\n')
        add_snippet(math_content, True, md_line, md_end_line)

    # Extract inline math
    for item in valid_inlines:
        if len(item) == 3:
            math_content, md_line, md_end_line = item
        else:
            math_content, md_line = item
            md_end_line = md_line + math_content.count('\n')
        add_snippet(math_content, False, md_line, md_end_line)

    tex_lines.append(r"\end{document}")
    
    if len(tex_to_md_map) == 0:
        return []

    tex_source = "\n".join(tex_lines)
    
    with tempfile.TemporaryDirectory() as tempdir:
        tex_file = os.path.join(tempdir, "temp.tex")
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_source)
            
        cmd = ["pdflatex", "-interaction=nonstopmode", "temp.tex"]
        subprocess.run(cmd, cwd=tempdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        log_file = os.path.join(tempdir, "temp.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read().splitlines()
                
            parsed_errors = parse_latex_log(log_content)
            for parsed in parsed_errors:
                tex_line = parsed["tex_line"]
                error = parsed["error"]
                part1 = parsed["part1"]
                part2 = parsed["part2"]
                
                # Filter out cascading parser recovery errors
                err_lower = error.lower()
                cascade_indicators = [
                    "missing $ inserted",
                    "display math should end with $$",
                    "bad math environment delimiter",
                    "extra }, or forgotten $",
                    "missing } inserted",
                    "allowed only in math mode"
                ]
                if any(ind in err_lower for ind in cascade_indicators):
                    continue
                
                info = tex_to_md_map.get(tex_line)
                if info is None:
                    for offset in range(1, 10):
                        if (tex_line - offset) in tex_to_md_map:
                            info = tex_to_md_map[tex_line - offset]
                            break
                
                if info:
                    md_line, md_end_line, is_block = info
                else:
                    md_line, md_end_line, is_block = "Unknown", "Unknown", True
                
                part2_stripped = part2.lstrip()
                combined = part1 + part2_stripped
                pointer = " " * len(part1) + "^"
                context = f"{combined}\n{pointer}"
                
                issues.append({
                    "md_line": md_line,
                    "md_end_line": md_end_line,
                    "error": error,
                    "context": context,
                    "is_block": is_block
                })
                    
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["md_line"], issue["md_end_line"], issue["error"], issue["context"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)
            
    return unique_issues[:15]

def format_issue_for_cli(issue):
    line_range = f"{issue['md_line']}-{issue['md_end_line']}" if issue['md_line'] != issue['md_end_line'] else str(issue['md_line'])
    math_type = "Block Math" if issue['is_block'] else "Inline Math"
    header = f"Line {line_range} [{math_type}]: {issue['error']}"
    indented_context = "\n".join("      " + line for line in issue['context'].split('\n'))
    return f"{header}\n{indented_context}"

def process_file(file_path, use_pdflatex=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        issues, valid_blocks, valid_inlines = validate_math_pylatexenc(content)
        if use_pdflatex and (valid_blocks or valid_inlines):
            try:
                pdflatex_issues = validate_math_pdflatex(valid_blocks, valid_inlines)
                issues.extend(pdflatex_issues)
            except Exception as e:
                print(f"[\033[93mWARNING\033[0m] pdflatex validation failed for {file_path}: {e}")

        if issues:
            print(f"[\033[93mWARNING\033[0m] Math syntax errors in {os.path.basename(file_path)}:")
            for issue in issues:
                print(f"    - {format_issue_for_cli(issue)}")
            return True
    except Exception as e:
        print(f"[\033[93mWARNING\033[0m] Failed to process math validation for {file_path}: {e}")
        return False
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
