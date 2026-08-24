import argparse
import bisect
import json
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

    # Line numbers computed once, instead of once per formula.
    #
    # `content.count('\n', 0, pos)` rescans the document from the beginning for
    # every match, so a file with N characters and M formulas cost O(N × M)
    # just to *number* the results — on a large wiki that dominated the
    # validation it was supporting. Building the newline offsets up front makes
    # the whole thing O(N + M log K); the offsets cost one full scan, which is
    # why it is not O(M log K) alone.
    #
    # `bisect_left`, not `bisect_right`: `str.count(x, 0, pos)` excludes
    # position `pos` itself, so a match starting exactly on a newline must not
    # count that newline. `bisect_right` puts it on the following line.
    # Verified equivalent to the old expression at every position of 400
    # random documents.
    newline_offsets = [m.start() for m in re.finditer(r'\n', content)]

    def line_of(pos):
        return bisect.bisect_left(newline_offsets, pos) + 1

    # Extract block math
    block_pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    for match in block_pattern.finditer(content):
        math_content = match.group(1)
        start_index = match.start()
        end_index = match.end()
        line_num = line_of(start_index)
        end_line = line_of(end_index)
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
        line_num = line_of(start_index)
        end_line = line_of(end_index)
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
    # Physics/math literature leans on more than the ams trio (\bm, \mathscr,
    # \ket, ...). Load the common packages when the TeX distro has them and
    # degrade to harmless fallbacks when it doesn't, so validation flags real
    # typos instead of every missing-package macro.
    tex_lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amssymb,amsfonts}",
        r"\IfFileExists{bm.sty}{\usepackage{bm}}{\providecommand{\bm}[1]{\boldsymbol{#1}}}",
        r"\IfFileExists{mathtools.sty}{\usepackage{mathtools}}{}",
        r"\IfFileExists{mathrsfs.sty}{\usepackage{mathrsfs}}{\providecommand{\mathscr}[1]{\mathcal{#1}}}",
        r"\IfFileExists{dsfont.sty}{\usepackage{dsfont}}{\providecommand{\mathds}[1]{\mathbb{#1}}}",
        r"\IfFileExists{slashed.sty}{\usepackage{slashed}}{\providecommand{\slashed}[1]{#1}}",
        r"\IfFileExists{cancel.sty}{\usepackage{cancel}}{\providecommand{\cancel}[1]{#1}}",
        r"\IfFileExists{physics.sty}{\usepackage{physics}}{}",
        r"\providecommand{\ket}[1]{\lvert #1\rangle}",
        r"\providecommand{\bra}[1]{\langle #1\rvert}",
        r"\providecommand{\braket}[1]{\langle #1\rangle}",
        r"\providecommand{\tr}{\operatorname{tr}}",
        r"\providecommand{\Tr}{\operatorname{Tr}}",
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

# --------------------------------------------------------------------------
# Prose that ended up inside a display block.
#
# The commonest ingest defect is not malformed LaTeX — it is a `$$` whose
# closing pair went missing, so a paragraph of the paper reads as one enormous
# formula. pylatexenc parses that happily (words are just letters) and
# pdflatex mostly does too, which is why it survives every existing check and
# then renders as a wall of italic single letters.
#
# Detected by the one thing formulas never have: a long run of ordinary words
# carrying no mathematics at all. Measured against 8 208 display blocks in a
# real library, 7 999 have no such run whatsoever and the tail is contamination
# — "Proof. We replace the ground field with its algebraic closure", "This
# appendix presents the pseudocode for the algorithm". Six is well clear of the
# 113 blocks whose longest run is a single connective like "where".
# --------------------------------------------------------------------------

PROSE_RUN_WORDS = 6

# Prose legitimately appears inside math through these, so it does not count.
_TEXTISH = re.compile(
    r"\\(?:text|mbox|textrm|textit|textbf|textsf|textnormal|operatorname|mathrm)\s*\{[^{}]*\}")
_MATHY = re.compile(r"\\[a-zA-Z]+|[_^{}=<>+\-*/&|]|\$|\d")


def longest_prose_run(body: str) -> int:
    """Longest run of consecutive plain words carrying no mathematics."""
    best = run = 0
    for token in _TEXTISH.sub(" ", body).split():
        if len(token) >= 2 and token.isalpha() and not _MATHY.search(token):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def detect_prose_blocks(content: str) -> list:
    """Display blocks that are a paragraph of the paper, not a formula."""
    content = re.sub(r'```.*?```', lambda m: "\n" * m.group(0).count("\n"),
                     content, flags=re.DOTALL)
    out = []
    for match in re.finditer(r'\$\$(.*?)\$\$', content, re.DOTALL):
        body = match.group(1)
        run = longest_prose_run(body)
        if run < PROSE_RUN_WORDS:
            continue
        excerpt = " ".join(body.split())[:110]
        out.append({
            "md_line": content.count('\n', 0, match.start()) + 1,
            "md_end_line": content.count('\n', 0, match.end()) + 1,
            "error": (f"{run} consecutive words of prose inside a display block — "
                      f"this is almost certainly a `$$` that was never closed, "
                      f"swallowing the paragraph after it"),
            "context": excerpt,
            "is_block": True,
        })
    return out


# --------------------------------------------------------------------------
# Worklist. `magi lint` prints math errors as prose in the middle of a
# structural report, which is fine for "is this card healthy" and useless for
# "work through every broken formula in the library". These functions turn the
# same two validators into an addressable list: one entry per formula, with
# the offending TeX verbatim, so an agent can triage the whole thing before
# touching a single file.
# --------------------------------------------------------------------------

# pdflatex reports a macro it has never heard of the same way whether the
# macro is a typo or comes from a package this validator does not load.
_MACRO_HINT = "undefined control sequence"


# A worklist entry has to stay scannable. The commonest ingest defect is a
# `$$` nobody closed, which "spans" a page of prose — quoting all of it would
# bury the other entries, and the line range says where to read the rest.
TEX_EXCERPT = 900


def _tex_at(lines: list[str], start, end) -> tuple[str, bool]:
    """The source of the formula an issue points at, delimiters included."""
    if not isinstance(start, int) or not isinstance(end, int):
        return "", False
    tex = "\n".join(lines[max(0, start - 1):end]).strip()
    if len(tex) <= TEX_EXCERPT:
        return tex, False
    half = TEX_EXCERPT // 2
    return f"{tex[:half]}\n…\n{tex[-half:]}", True


def _entry(root: Path, path: Path, issue: dict, detector: str, lines: list[str]) -> dict:
    rel = path.resolve().relative_to(root).as_posix()
    start, end = issue["md_line"], issue["md_end_line"]
    likely_macro = _MACRO_HINT in str(issue["error"]).lower()
    tex, clipped = _tex_at(lines, start, end)
    return {
        # Stable across runs so an agent can tick entries off a long list.
        "id": f"{rel}:{start}",
        "path": rel,
        "line": start,
        "end_line": end,
        "kind": "block" if issue["is_block"] else "inline",
        "detector": detector,
        "error": issue["error"],
        # A macro pdflatex does not know is usually a package it does not load,
        # not a typo — rewriting those on sight corrupts correct formulas.
        "confidence": "likely-macro" if likely_macro else "certain",
        "context": issue["context"],
        "tex": tex,
        "tex_clipped": clipped,
        # raw/ is ingest output; wiki/ is the compiled library and holds the
        # errors a reader will actually meet.
        "collection": rel.split("/")[0] if "/" in rel else "",
    }


def collect_issues(root, use_pdflatex=True, on_progress=None):
    """Every broken formula under *root*, as an addressable worklist."""
    from magi.core.wiki_common import corpus_files

    root = Path(root).resolve()
    files = corpus_files(root)
    out = []
    for i, path in enumerate(files, 1):
        if on_progress:
            on_progress(i, len(files), path)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.split("\n")
        issues, valid_blocks, valid_inlines = validate_math_pylatexenc(content)
        out.extend(_entry(root, path, it, "pylatexenc", lines) for it in issues)
        # Pure Python, so it runs whether or not a LaTeX toolchain exists —
        # and it is the only detector that sees the commonest defect.
        out.extend(_entry(root, path, it, "prose", lines)
                   for it in detect_prose_blocks(content))
        if use_pdflatex and (valid_blocks or valid_inlines):
            try:
                deep = validate_math_pdflatex(valid_blocks, valid_inlines)
            except Exception:
                deep = []
            out.extend(_entry(root, path, it, "pdflatex", lines) for it in deep)
    return out


def format_issue_for_cli(issue):
    line_range = f"{issue['md_line']}-{issue['md_end_line']}" if issue['md_line'] != issue['md_end_line'] else str(issue['md_line'])
    math_type = "Block Math" if issue['is_block'] else "Inline Math"
    error = issue['error']
    if "undefined control sequence" in error.lower():
        error += "  (note: may be a macro from a package this validator lacks, not a typo — compare with the source PDF before rewriting)"
    header = f"Line {line_range} [{math_type}]: {error}"
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
    return files_with_issues > 0

# A whole library's worth of ingest damage is hundreds of entries; printing
# every one buries the shape of the problem. --json is the complete list.
_MAX_PER_FILE = 6


def _summarize(entries, root):
    """Human view: what kind of damage, where, and what to run next."""
    if not entries:
        print(f"All formulas under {root} parse cleanly.")
        return

    by_file = {}
    for e in entries:
        by_file.setdefault(e["path"], []).append(e)
    wiki = [e for e in entries if e["collection"] == "wiki"]
    prose = [e for e in entries if e["detector"] == "prose"]
    macros = [e for e in entries if e["confidence"] == "likely-macro"]

    # Compiled cards first: those are the ones a reader actually opens.
    for path in sorted(by_file, key=lambda p: (not p.startswith("wiki/"), p)):
        items = by_file[path]
        print(f"\n{path}  ({len(items)})")
        for e in items[:_MAX_PER_FILE]:
            span = e["line"] if e["line"] == e["end_line"] else f"{e['line']}-{e['end_line']}"
            tag = "  [may be a package macro]" if e["confidence"] == "likely-macro" else ""
            print(f"  {span} [{e['kind']}] {e['error'].splitlines()[0]}{tag}")
            for line in str(e["context"]).split("\n")[:2]:
                print(f"      {line}")
        if len(items) > _MAX_PER_FILE:
            print(f"  … and {len(items) - _MAX_PER_FILE} more in this file")

    print(f"\n{len(entries)} formula(s) in {len(by_file)} file(s) need attention.")
    if prose:
        print(f"  {len(prose)} are prose swallowed by an unclosed $$ — the usual ingest damage")
    if wiki:
        print(f"  {len(wiki)} are in compiled cards under wiki/ — fix these first")
    else:
        print("  none are in wiki/ — your compiled cards are clean")
    if macros:
        print(f"  {len(macros)} may be package macros rather than typos; check the source PDF")
    print("\nDeterministic pass first:  magi math format")
    print("Then work the list:        magi math check --json")
    print("                           (the wiki_math_fix skill drives that list, one at a time)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magi math check",
        description="Detect LaTeX syntax errors in markdown math blocks. "
                    "Defaults to the surrounding workspace, like `magi lint`.")
    parser.add_argument("target", nargs="?", default=None,
                        help="Topic directory or markdown file (default: the workspace you are in)")
    parser.add_argument("--json", action="store_true",
                        help="Emit the worklist as JSON: one entry per broken formula")
    parser.add_argument("--fast", action="store_true",
                        help="Structural checks only — skip the per-file pdflatex pass")
    parser.add_argument("--wiki-only", action="store_true",
                        help="Only compiled cards under wiki/, not raw ingest output")
    args = parser.parse_args(argv)

    target = args.target
    if target is None:
        from magi.core.workspace import find_workspace_root

        root = find_workspace_root()
        if root is None:
            parser.error("no MAGI workspace here — pass a directory, or cd into one")
        target = str(root)

    if not os.path.exists(target):
        print(f"Path not found: {target}")
        return 1

    has_pdflatex = shutil.which("pdflatex") is not None and not args.fast
    if not HAS_PYLATEXENC and not has_pdflatex and not args.json:
        # The prose detector below is pure Python and still runs; only the
        # LaTeX-level checks are unavailable.
        print("Note: neither pdflatex nor pylatexenc found — checking for prose "
              "inside display blocks only.", file=sys.stderr)

    root = Path(target).resolve()
    if root.is_file():
        # One file still goes through the worklist so --json means one thing.
        entries = []
        content = root.read_text(encoding="utf-8", errors="replace")
        issues, blocks, inlines = validate_math_pylatexenc(content)
        lines = content.split("\n")
        entries.extend(_entry(root.parent, root, it, "pylatexenc", lines) for it in issues)
        entries.extend(_entry(root.parent, root, it, "prose", lines)
                       for it in detect_prose_blocks(content))
        if has_pdflatex and (blocks or inlines):
            entries.extend(_entry(root.parent, root, it, "pdflatex", lines)
                           for it in validate_math_pdflatex(blocks, inlines))
        root = root.parent
    else:
        # pdflatex runs once per file and a real library takes minutes, so say
        # where we are — but only to a terminal that can erase the line. Piped
        # or redirected, a carriage return just stacks 260 lines of noise.
        live = sys.stderr.isatty() and not args.json
        progress = None
        if live:
            def progress(i, total, path):
                print(f"\r  [{i}/{total}] {path.name[:60]:<60}",
                      end="", file=sys.stderr, flush=True)

        entries = collect_issues(root, use_pdflatex=has_pdflatex, on_progress=progress)
        if live:
            print("\r" + " " * 72 + "\r", end="", file=sys.stderr)

    if args.wiki_only:
        entries = [e for e in entries if e["collection"] == "wiki"]

    if args.json:
        print(json.dumps({
            "root": str(root),
            "detector": "pylatexenc+pdflatex" if has_pdflatex else "pylatexenc",
            "count": len(entries),
            "issues": entries,
        }, ensure_ascii=False, indent=2))
    else:
        _summarize(entries, root)
    return 1 if entries else 0

if __name__ == '__main__':
    sys.exit(main())
