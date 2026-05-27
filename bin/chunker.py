import os
import sys
import argparse
import shutil

def chunk_markdown(filepath, topic_dir, max_lines=500):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)
        
    scratch_dir = os.path.join(topic_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    # clean up previous chunks
    for f in os.listdir(scratch_dir):
        if f.startswith("chunk_") and f.endswith(".md"):
            os.remove(os.path.join(scratch_dir, f))
            
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    chunks = []
    current_chunk = []
    current_lines = 0
    
    in_code_block = False
    
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            
        current_chunk.append(line)
        current_lines += 1
        
        # Break chunk if it exceeds max_lines, but only on empty lines, not in code blocks
        if current_lines >= max_lines and not in_code_block and line.strip() == "":
            chunks.append("".join(current_chunk))
            current_chunk = []
            current_lines = 0
            
    if current_chunk:
        chunks.append("".join(current_chunk))
        
    for i, chunk_data in enumerate(chunks, 1):
        chunk_file = os.path.join(scratch_dir, f"chunk_{i:02d}.md")
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk_data)
            
    print(f"Generated {len(chunks)} chunks in {scratch_dir}")

def main():
    parser = argparse.ArgumentParser(description="Chunk large markdown files")
    parser.add_argument("filepath", help="Path to raw markdown file")
    parser.add_argument("--topic-dir", required=True, help="Topic directory")
    parser.add_argument("--max-lines", type=int, default=500, help="Max lines per chunk")
    args = parser.parse_args()
    
    chunk_markdown(args.filepath, args.topic_dir, args.max_lines)

if __name__ == "__main__":
    main()
