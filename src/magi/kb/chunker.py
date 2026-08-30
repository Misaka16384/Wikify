import os
import sys
import argparse
import shutil
import threading
from pathlib import Path

# Thread-safe lock for stats/logging.
#
# There was a `_stats_queue = queue.Queue()` here that every call to
# `chunk_markdown` pushed a dict onto and that nothing in the repository ever
# read — no consumer, no drain, no reporting. In a short CLI run it cost
# nothing; called in a loop or from a resident process it grew without bound.
# Removed rather than capped: data with no consumer does not need a smaller
# bucket, and the counts it held are already printed below.
_stats_lock = threading.Lock()

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
            
    with _stats_lock:
        print(f"Generated {len(chunks)} chunks in {scratch_dir} for {file_slug} (PID: {pid})")

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki chunk", description="Chunk large markdown files")
    parser.add_argument("filepath", help="Path to raw markdown file")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", required=True, help="Project directory")
    parser.add_argument("--max-lines", type=int, default=500, help="Max lines per chunk")
    args = parser.parse_args(argv)

    chunk_markdown(args.filepath, args.topic_dir, args.max_lines)

if __name__ == "__main__":
    sys.exit(main())
