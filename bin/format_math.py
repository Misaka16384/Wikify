import os
import re
import sys

def clean_math_delimiters(content):
    # Ensure standard LaTeX block environments have preceding and trailing newlines
    environments = ['align', 'equation', 'gather', 'multline', 'split']
    for env in environments:
        content = re.sub(rf'(?<!\n)(\\begin\{{{env}\}})', r'\n\1', content)
        content = re.sub(rf'(\\end\{{{env}\}})(?!\n)', r'\1\n', content)

    # Standardize single-line block math:
    # $$equation$$  -->  $$\nmath\n$$
    # $$equation \tag{1}$$  -->  $$\nmath \tag{1}\n$$
    content = re.sub(r'(?<!\\)\$\{(.+?)\}(?<!\\)\$\$(?=\s*($|\n))', r'$$\n\1\n$$', content) # safety for template var placeholders
    content = re.sub(r'(?<!\\)\$\$(.+?)(?<!\\)\$\$(?=\s*($|\n))', r'$$\n\1\n$$', content)
    
    # Process line-by-line
    lines = content.split('\n')
    new_lines = []
    
    in_block = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if line contains '$$'
        if '$$' in line:
            # If line is exactly '$$', it's a clean delimiter
            if stripped == '$$':
                new_lines.append(line)
                in_block = not in_block
                i += 1
                continue
            
            # If it starts with '$$' but has other characters (e.g. $$math or $$= math)
            if stripped.startswith('$$') and not stripped.endswith('$$'):
                indent = line[:line.find('$$')]
                math_part = stripped[2:].strip()
                new_lines.append(f"{indent}$$")
                new_lines.append(f"{indent}{math_part}")
                in_block = True
                i += 1
                continue
                
            # If it ends with '$$' but has other characters (e.g. math$$)
            if stripped.endswith('$$') and not stripped.startswith('$$'):
                indent = line[:len(line) - len(line.lstrip())]
                math_part = stripped[:-2].strip()
                new_lines.append(f"{indent}{math_part}")
                new_lines.append(f"{indent}$$")
                in_block = False
                i += 1
                continue
                
            # If it starts and ends with '$$' (and contains something in between)
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
            
    # Merge consecutive block math equations into \begin{aligned} blocks
    merged_lines = []
    idx = 0
    n = len(new_lines)
    
    while idx < n:
        line = new_lines[idx]
        stripped = line.strip()
        
        # Detect start of block math
        if stripped == '$$' and idx + 2 < n:
            block_lines = []
            j = idx + 1
            while j < n and new_lines[j].strip() != '$$':
                block_lines.append(new_lines[j])
                j += 1
                
            if j < n: # Found closing $$
                # Check if the next non-empty line starts another block math that begins with '=' or '+'
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
        
    return "\n".join(merged_lines)

def process_directory(directory):
    print(f"Formatting math formulas in markdown files under: {directory}")
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    content = content.replace('\r\n', '\n')
                    
                    formatted = clean_math_delimiters(content)
                    
                    if formatted != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(formatted)
                        print(f"  Formatted: {os.path.relpath(file_path, directory)}")
                except (IOError, UnicodeDecodeError) as e:
                    print(f"  Error processing {file_path}: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python format_math.py <TOPIC_DIR>")
        sys.exit(1)
    topic_dir = sys.argv[1]
    if not os.path.exists(topic_dir):
        print(f"Directory not found: {topic_dir}")
        sys.exit(1)
    process_directory(topic_dir)
