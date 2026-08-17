import os
import re
import sys

try:
    from wiki_common import atomic_write
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from wiki_common import atomic_write


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


def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('\r\n', '\n')
        
        # Check path for raw scope
        is_raw = "raw/" in file_path.replace("\\", "/")
        
        # Check for orphaned $$ (Pattern 5)
        lines = content.split('\n')
        for idx, line in enumerate(lines):
            count = line.count('$$')
            if count % 2 == 1:
                if line.strip() != '$$':
                    print(f"[\033[93mWARNING\033[0m] Orphaned $$ found on line {idx + 1} of {os.path.basename(file_path)}: {line.strip()}")
        
        formatted = clean_math_delimiters(content, is_raw=is_raw)
        
        if formatted != content:
            atomic_write(file_path, formatted, encoding='utf-8', newline='\n')
            print(f"  Formatted: {file_path}")
    except (IOError, UnicodeDecodeError) as e:
        print(f"  Error processing {file_path}: {e}")

def process_directory(directory):
    print(f"Formatting math formulas in markdown files under: {directory}")
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                process_file(file_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python format_math.py <TOPIC_DIR_OR_FILE>")
        sys.exit(1)
    target = sys.argv[1]
    if not os.path.exists(target):
        print(f"Path not found: {target}")
        sys.exit(1)
    if os.path.isdir(target):
        process_directory(target)
    else:
        process_file(target)
