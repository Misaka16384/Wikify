import os
import sys
import argparse
import shutil
import threading
import queue
from pathlib import Path

# Thread-safe lock for stats/logging and stats queue
_stats_lock = threading.Lock()
_stats_queue = queue.Queue()

def chunk_markdown(filepath, topic_dir, max_lines=500):
    if not os.path.exists(filepath):
        with _stats_lock:
            print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
        
    scratch_dir = os.path.join(topic_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    file_slug = Path(filepath).stem
    pid = os.getpid()
    
    # Clean up previous chunks for this specific file and PID to avoid concurrent interference
    for f in os.listdir(scratch_dir):
        if f.startswith(f"chunk_{file_slug}_{pid}_") and f.endswith(".md"):
            try:
                os.remove(os.path.join(scratch_dir, f))
            except OSError:
                pass
            
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
        chunk_file = os.path.join(scratch_dir, f"chunk_{file_slug}_{pid}_{i:02d}.md")
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk_data)
            
    # Push chunk generation statistics to the thread-safe queue
    _stats_queue.put({
        "filepath": filepath,
        "file_slug": file_slug,
        "pid": pid,
        "chunks_count": len(chunks)
    })
            
    with _stats_lock:
        print(f"Generated {len(chunks)} chunks in {scratch_dir} for {file_slug} (PID: {pid})")

def main():
    parser = argparse.ArgumentParser(description="Chunk large markdown files")
    parser.add_argument("filepath", help="Path to raw markdown file")
    parser.add_argument("--topic-dir", required=True, help="Topic directory")
    parser.add_argument("--max-lines", type=int, default=500, help="Max lines per chunk")
    args = parser.parse_args()
    
    chunk_markdown(args.filepath, args.topic_dir, args.max_lines)

if __name__ == "__main__":
    main()
