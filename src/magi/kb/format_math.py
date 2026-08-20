import argparse
import os
import re
import sys

from magi.core.wiki_common import atomic_write


def fix_ocr_math_artifacts(math_content):
    # 1 & 2. Double subscripts/superscripts merge
    sub_pattern = re.compile(r'(?<!\\)_(?:\{([^{}]+)\}|([a-zA-Z0-9]))\s*(?<!\\)_(?:\{([^{}]+)\}|([a-zA-Z0-9]))')
    super_pattern = re.compile(r'(?<!\\)\^(?:\{([^{}]+)\}|([a-zA-Z0-9]))\s*(?<!\\)\^(?:\{([^{}]+)\}|([a-zA-Z0-9]))')
    
    def merge_subscripts(m):
        val1 = m.group(1) or m.group(2)
        val2 = m.group(3) or m.group(4)
        return f"_{{{val1},{val2}}}"

    def merge_superscripts(m):
        val1 = m.group(1) or m.group(2)
        val2 = m.group(3) or m.group(4)
        return f"^{{{val1},{val2}}}"

    while True:
        new_math = re.sub(sub_pattern, merge_subscripts, math_content)
        if new_math == math_content:
            break
        math_content = new_math

    while True:
        new_math = re.sub(super_pattern, merge_superscripts, math_content)
        if new_math == math_content:
            break
        math_content = new_math

    # 3. Unescaped #
    math_content = re.sub(r'(?<!\\)#', r'\#', math_content)

    # 4. Stray delimiters
    math_content = math_content.replace(r'\(', '(').replace(r'\)', ')').replace(r'\[', '[').replace(r'\]', ']')

    return math_content

def safe_auto_fixes(content, is_raw=False):
    # 1. Redundant nesting (equation inside $$)
    content = re.sub(
        r'\$\$[\s\n]*\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}[\s\n]*\$\$',
        r'$$\n\1\n$$',
        content,
        flags=re.DOTALL
    )
    
    # Redundant nesting (\[ \] inside $$)
    content = re.sub(
        r'\$\$[\s\n]*\\\[(.*?)\\\][\s\n]*\$\$',
        r'$$\n\1\n$$',
        content,
        flags=re.DOTALL
    )

    # 2. Handle \tag in unsupported environments
    container_envs = ('array', 'matrix', 'pmatrix', 'vmatrix', 'Vmatrix', 'Bmatrix', 'bmatrix', 'cases')

    def _inside_container(prefix):
        # True if `prefix` ends inside an unclosed array/matrix/cases-style env.
        # A nested `aligned` here must NOT be promoted to a top-level `align`,
        # which cannot be nested inside another math environment.
        depth = 0
        for m in re.finditer(r'\\(begin|end)\{([a-zA-Z]+\*?)\}', prefix):
            if m.group(2) in container_envs:
                depth += 1 if m.group(1) == 'begin' else -1
        return depth > 0

    environments_to_check = ['aligned', 'array', 'matrix', 'pmatrix', 'vmatrix', 'Vmatrix', 'Bmatrix', 'bmatrix', 'cases']
    for env in environments_to_check:
        def make_fixer(env_name):
            def fix_tag_env(match):
                inner_content = match.group(1)
                # Allow one level of nested braces so \tag{\text{Eq. 1}} is captured whole.
                tag_match = re.search(r'\\tag\s*\{((?:[^{}]+|\{[^{}]*\})*)\}', inner_content)
                if tag_match:
                    if env_name == 'aligned' and not _inside_container(match.string[:match.start()]):
                        # Top-level aligned: convert to align so multiple \tag and
                        # alignment are preserved (align carries tags; aligned can't).
                        return f"\\begin{{align}}{inner_content}\\end{{align}}"
                    else:
                        # For array/matrices/cases (and any nested aligned), keep the
                        # environment and column spec intact and move the tag outside so
                        # brackets are preserved and no invalid nesting is introduced.
                        tag_text = tag_match.group(0)
                        inner_content = inner_content.replace(tag_text, '')
                        return f"\\begin{{{env_name}}}{inner_content}\\end{{{env_name}}} {tag_text}"
                return match.group(0)
            return fix_tag_env
        content = re.sub(rf'\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}', make_fixer(env), content, flags=re.DOTALL)

    # Convert eqnarray to align (KaTeX compatibility). eqnarray is a 3-column
    # environment (lhs & rel & rhs); align is 2-column (lhs &rel rhs), so the
    # relation-wrapping ampersand pair on each row must be collapsed or the extra
    # alignment tab renders with broken spacing. Preserve the * (unnumbered).
    def fix_eqnarray(match):
        star = match.group(1)  # '' or '*'
        body = re.sub(r'&([^&\n]*)&', r'&\1', match.group(2))
        return f"\\begin{{align{star}}}{body}\\end{{align{star}}}"
    content = re.sub(r'\\begin\{eqnarray(\*?)\}(.*?)\\end\{eqnarray\1\}', fix_eqnarray, content, flags=re.DOTALL)

    # Remove trailing \\ right before $$ or end of math environments where it causes parse errors
    content = re.sub(r'\\\\\s*\$\$', r'\n$$', content)

    # 3. & 4. Process math blocks for escaped parentheses and inline newlines
    def process_block(match):
        math_content = match.group(1)
        if is_raw:
            math_content = fix_ocr_math_artifacts(math_content)
        return f"$${math_content}$$"

    _MATH_TOKEN_RE = re.compile(r'\\[a-zA-Z]|[_^]')

    def process_inline(match):
        math_content = match.group(1)
        if not _MATH_TOKEN_RE.search(math_content):
            return match.group(0)
        if is_raw:
            math_content = fix_ocr_math_artifacts(math_content)
        return f"${math_content}$"

    content = re.sub(r'\$\$(.*?)\$\$', process_block, content, flags=re.DOTALL)
    # Be careful not to match $$ for inline
    content = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', process_inline, content)

    return content

def clean_math_delimiters(content, is_raw=False):
    lines = content.split('\n')
    segments = []
    current_segment = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith('```'):
            if in_code_block:
                current_segment.append(line)
                segments.append((True, current_segment))
                current_segment = []
                in_code_block = False
            else:
                if current_segment:
                    segments.append((False, current_segment))
                current_segment = [line]
                in_code_block = True
        else:
            current_segment.append(line)

    if current_segment:
        segments.append((in_code_block, current_segment))

    final_lines = []
    for is_code, seg_lines in segments:
        if is_code:
            final_lines.extend(seg_lines)
        else:
            segment_content = '\n'.join(seg_lines)
            segment_content = safe_auto_fixes(segment_content, is_raw=is_raw)

            environments = ['align', 'equation', 'gather', 'multline', 'split']
            for env in environments:
                segment_content = re.sub(rf'(?<!\n)(\\begin\{{{env}\}})', r'\n\1', segment_content)
                segment_content = re.sub(rf'(\\end\{{{env}\}})(?!\n)', r'\1\n', segment_content)

            segment_content = re.sub(r'(?<!\\)\$\{(.+?)\}(?<!\\)\$\$(?=\s*($|\n))', r'$$\n\1\n$$', segment_content)
            segment_content = re.sub(r'(?<!\\)\$\$(.+?)(?<!\\)\$\$(?=\s*($|\n))', r'$$\n\1\n$$', segment_content)

            seg_lines = segment_content.split('\n')
            new_lines = []
            in_block = False
            i = 0
            while i < len(seg_lines):
                line = seg_lines[i]
                stripped = line.strip()
                if '$$' in line:
                    if stripped == '$$':
                        new_lines.append(line)
                        in_block = not in_block
                        i += 1
                        continue
                    if stripped.startswith('$$') and not stripped.endswith('$$'):
                        indent = line[:line.find('$$')]
                        math_part = stripped[2:].strip()
                        new_lines.append(f"{indent}$$")
                        new_lines.append(f"{indent}{math_part}")
                        in_block = True
                        i += 1
                        continue
                    if stripped.endswith('$$') and not stripped.startswith('$$'):
                        indent = line[:len(line) - len(line.lstrip())]
                        math_part = stripped[:-2].strip()
                        new_lines.append(f"{indent}{math_part}")
                        new_lines.append(f"{indent}$$")
                        in_block = False
                        i += 1
                        continue
                    if stripped.startswith('$$') and stripped.endswith('$$') and len(stripped) > 4:
                        indent = line[:line.find('$$')]
                        math_part = stripped[2:-2].strip()
                        new_lines.append(f"{indent}$$")
                        new_lines.append(f"{indent}{math_part}")
                        new_lines.append(f"{indent}$$")
                        i += 1
                        continue
                    new_lines.append(line)
                    i += 1
                else:
                    new_lines.append(line)
                    i += 1

            merged_lines = []
            idx = 0
            n = len(new_lines)
            while idx < n:
                line = new_lines[idx]
                stripped = line.strip()
                if stripped == '$$' and idx + 2 < n:
                    block_lines = []
                    j = idx + 1
                    while j < n and new_lines[j].strip() != '$$':
                        block_lines.append(new_lines[j])
                        j += 1
                    if j < n:
                        next_block_start = j + 1
                        while next_block_start < n and new_lines[next_block_start].strip() == '':
                            next_block_start += 1
                        if next_block_start < n and new_lines[next_block_start].strip() == '$$':
                            all_blocks = [block_lines]
                            current_j = j
                            while True:
                                k_start = current_j + 1
                                while k_start < n and new_lines[k_start].strip() == '':
                                    k_start += 1
                                if k_start < n and new_lines[k_start].strip() == '$$':
                                    next_block_lines = []
                                    k = k_start + 1
                                    while k < n and new_lines[k].strip() != '$$':
                                        next_block_lines.append(new_lines[k])
                                        k += 1
                                    if k < n:
                                        first_line_stripped = "".join(next_block_lines).strip()
                                        if first_line_stripped.startswith('=') or first_line_stripped.startswith('+') or first_line_stripped.startswith('-') or first_line_stripped.startswith('\\rightarrow'):
                                            all_blocks.append(next_block_lines)
                                            current_j = k
                                            continue
                                break
                            if len(all_blocks) > 1:
                                merged_math = ["$$", "\\begin{aligned}"]
                                for b_idx, block in enumerate(all_blocks):
                                    block_content = "\n".join(block).strip()
                                    if block_content.startswith('='):
                                        block_content = '&' + block_content
                                    elif block_content.startswith('+'):
                                        block_content = '&+' + block_content[1:]
                                    elif block_content.startswith('-'):
                                        block_content = '&-' + block_content[1:]
                                    elif block_content.startswith('\\rightarrow'):
                                        block_content = '&' + block_content
                                    if b_idx < len(all_blocks) - 1:
                                        if not block_content.endswith('\\\\'):
                                            block_content += ' \\\\'
                                    merged_math.append(block_content)
                                merged_math.append("\\end{aligned}")
                                merged_math.append("$$")
                                merged_lines.extend(merged_math)
                                idx = current_j + 1
                                continue
                merged_lines.append(line)
                idx += 1
            final_lines.extend(merged_lines)

    return "\n".join(final_lines)


def _orphan_dollar_lines(text):
    """Lines with an odd number of $$ that are not a bare $$ delimiter."""
    hits = []
    for idx, line in enumerate(text.split('\n')):
        if line.count('$$') % 2 == 1 and line.strip() != '$$':
            hits.append((idx + 1, line.strip()))
    return hits


def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('\r\n', '\n')

        # Check path for raw scope
        is_raw = "raw/" in file_path.replace("\\", "/")

        pre_orphans = _orphan_dollar_lines(content)
        formatted = clean_math_delimiters(content, is_raw=is_raw)
        # Only warn about what the cleaner could NOT fix — warning about
        # every line it is about to normalize just buries the real issues.
        post_orphans = _orphan_dollar_lines(formatted)
        n_fixed = max(0, len(pre_orphans) - len(post_orphans))

        if formatted != content:
            atomic_write(file_path, formatted, encoding='utf-8', newline='\n')
            summary = f"  Formatted: {file_path}"
            if n_fixed:
                summary += f" (normalized {n_fixed} $$ delimiter issue(s))"
            print(summary)
        for line_no, snippet in post_orphans:
            print(f"[\033[93mWARNING\033[0m] Orphaned $$ remains on line {line_no} of {os.path.basename(file_path)} (needs manual fix): {snippet}")
    except (IOError, UnicodeDecodeError) as e:
        print(f"  Error processing {file_path}: {e}")

def process_directory(directory):
    """Format every card in the library.

    Scoped to wiki/ raw/ drafts/ rather than the whole tree: this rewrites
    files in place and has no dry-run, and scratch/ is where the concept
    backups live — the copies you would want if a formatting pass went wrong.
    """
    from magi.core.wiki_common import corpus_files

    files = corpus_files(directory)
    print(f"Formatting math formulas in {len(files)} markdown file(s) under: {directory}")
    for file_path in files:
        process_file(str(file_path))

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi math format", description="Auto-fix LaTeX delimiter/escaping issues in markdown files.")
    parser.add_argument("target", nargs="?", default=None,
                        help="Topic directory or markdown file (default: the workspace you are in)")
    args = parser.parse_args(argv)
    target = args.target
    if target is None:
        # Same default as `magi lint` and `magi math check`: the maintenance
        # commands operate on a workspace, not on whatever file you name.
        from magi.core.workspace import find_workspace_root

        root = find_workspace_root()
        if root is None:
            parser.error("no MAGI workspace here — pass a directory, or cd into one")
        target = str(root)
    if not os.path.exists(target):
        print(f"Path not found: {target}")
        return 1
    if os.path.isdir(target):
        process_directory(target)
    else:
        process_file(target)
    return 0

if __name__ == '__main__':
    sys.exit(main())
