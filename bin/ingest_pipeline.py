import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_cmd(cmd_list):
    """Run a command as a list (no shell=True). Returns True on success."""
    print(f"Running: {' '.join(cmd_list)}")
    result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error (exit {result.returncode}):\n{result.stderr}", file=sys.stderr)
        return False
    if result.stdout.strip():
        print(result.stdout.strip())
    return True

def main():
    parser = argparse.ArgumentParser(description="Wiki Ingest Post-Processing Pipeline")
    parser.add_argument("original_file", help="Path to the original file (e.g. PDF in inbox/). Pass 'none' if not applicable.")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    parser.add_argument("--log-msg", required=False, help="Message to append to log.md")
    parser.add_argument("--md-file", required=False, help="Path to the specific generated Markdown file")
    parser.add_argument("--skip-lint", action="store_true", help="Skip the global lint and index operations")
    parser.add_argument("--lint-only", action="store_true", help="Only run the global lint and index operations")
    
    args = parser.parse_args()
    
    topic_dir = args.topic_dir
    original_file = args.original_file
    
    # 1. Move original file to inbox/.processed/ only if it genuinely lives
    #    under THIS topic's inbox/ (not merely any path component named "inbox").
    if not args.lint_only and original_file and original_file.lower() != "none":
        orig_resolved = Path(original_file).resolve()
        inbox_dir = Path(topic_dir, "inbox").resolve()
        try:
            is_in_inbox = orig_resolved.is_relative_to(inbox_dir)
        except AttributeError:  # Python < 3.9 fallback
            is_in_inbox = str(orig_resolved).startswith(str(inbox_dir) + os.sep)
        if is_in_inbox:
            processed_dir = os.path.join(topic_dir, "inbox", ".processed")
            os.makedirs(processed_dir, exist_ok=True)
            try:
                filename = os.path.basename(original_file)
                dest_file = os.path.join(processed_dir, filename)
                shutil.move(original_file, dest_file)
                print(f"Moved {filename} to .processed/")
            except Exception as e:
                print(f"Failed to move file to .processed: {e}")
                
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    
    if not args.lint_only:
        # 2. Format math formulas
        target_path = args.md_file if args.md_file else topic_dir
        format_math_script = os.path.join(bin_dir, "format_math.py")
        if not run_cmd([sys.executable, format_math_script, target_path]):
            print("Warning: format_math.py failed, continuing...", file=sys.stderr)
            
        validate_math_script = os.path.join(bin_dir, "validate_math_latex.py")
        if not run_cmd([sys.executable, validate_math_script, target_path]):
            print("Warning: validate_math_latex.py failed or found errors, continuing...", file=sys.stderr)
    
    if not args.skip_lint:
        # 3. Lint / Index update
        lint_script = os.path.join(bin_dir, "llm-wiki.py")
        if not run_cmd([sys.executable, lint_script, "lint", "--fix", topic_dir]):
            print("Warning: llm-wiki.py lint failed", file=sys.stderr)
            
        if not run_cmd([sys.executable, lint_script, "graph", topic_dir]):
            print("Warning: llm-wiki.py graph failed", file=sys.stderr)
            
        index_script = os.path.join(bin_dir, "index_builder.py")
        if not run_cmd([sys.executable, index_script, topic_dir]):
            print("Warning: index_builder.py failed", file=sys.stderr)
    
    # 4. Log to log.md
    if args.log_msg:
        log_file = os.path.join(topic_dir, "log.md")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"- [{timestamp}] INGEST: {args.log_msg}\n")
            print("Updated log.md")
        except Exception as e:
            print(f"Failed to update log.md: {e}")

if __name__ == "__main__":
    main()
