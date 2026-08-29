import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_cmd(cmd_list):
    """Run a command as a list (no shell=True). Returns True on success."""
    print(f"Running: {' '.join(cmd_list)}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env)
    # Tools like `magi math check` report their findings on stdout and use a
    # non-zero exit as a business result — always relay stdout so the user
    # can see WHAT failed, then stderr for the actual error channel.
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        if result.stderr.strip():
            print(f"Error (exit {result.returncode}):\n{result.stderr.strip()}", file=sys.stderr)
        return False
    return True

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi ingest finalize", description="Wiki Ingest Post-Processing Pipeline")
    parser.add_argument("original_file", help="Path to the original file (e.g. PDF in inbox/). Pass 'none' if not applicable.")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    parser.add_argument("--log-msg", required=False, help="Message to append to log.md")
    parser.add_argument("--md-file", required=False, help="Path to the specific generated Markdown file")
    parser.add_argument("--skip-lint", action="store_true", help="Skip the global lint and index operations")
    parser.add_argument("--lint-only", action="store_true", help="Only run the global lint and index operations")
    
    args = parser.parse_args(argv)

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
        if is_in_inbox and not orig_resolved.exists():
            # e.g. `magi ingest add --move` already relocated the inbox file.
            print("source already processed/moved - skipping inbox archival")
        elif is_in_inbox:
            processed_dir = os.path.join(topic_dir, "inbox", ".processed")
            os.makedirs(processed_dir, exist_ok=True)
            try:
                filename = os.path.basename(original_file)
                dest_file = os.path.join(processed_dir, filename)
                shutil.move(original_file, dest_file)
                print(f"Moved {filename} to .processed/")
            except Exception as e:
                print(f"Failed to move file to .processed: {e}")
                
    if not args.lint_only:
        # Fix YAML frontmatter syntax (unescaped backslashes in source, and empty tags)
        if args.md_file and os.path.isfile(args.md_file):
            try:
                with open(args.md_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                # Only treat the file as having YAML frontmatter if its first
                # non-empty line is exactly '---'. Otherwise a body horizontal
                # rule ('---') would be misread as a frontmatter fence and we'd
                # mangle 'source:' lines in the document body.
                first_nonempty = next((ln.strip() for ln in lines if ln.strip()), "")
                in_fm = False
                fm_count = 0
                if first_nonempty == "---":
                    for i, line in enumerate(lines):
                        if line.strip() == "---":
                            fm_count += 1
                            if fm_count == 1:
                                in_fm = True
                            elif fm_count == 2:
                                in_fm = False
                                break  # frontmatter closed; leave the body untouched
                        if in_fm and line.startswith("source:"):
                            lines[i] = line.replace("\\", "/")
                
                content = "".join(lines)
                
                # Convert standard Markdown image links to Obsidian Wikilinks,
                # skipping fenced code blocks so documented example syntax isn't rewritten.
                def repl_img(m):
                    alt, path = m.group(1), m.group(2)
                    if path.startswith("http"):
                        return m.group(0) # Keep external links as is
                    path = path.replace("%20", " ") # Decode already encoded spaces for Obsidian
                    alt = (alt or "").strip()
                    # Obsidian reads a purely numeric segment after '|' as a pixel
                    # width/height (e.g. ![[img.png|100]]), so drop a numeric alt to
                    # avoid silently resizing the image.
                    if alt and not re.fullmatch(r'\d+(x\d+)?', alt):
                        return f"![[{path}|{alt}]]"
                    return f"![[{path}]]"

                # Path group tolerates one level of balanced parens, e.g. "figure (1).png".
                img_pattern = re.compile(r'!\[(.*?)\]\(([^()\n]*(?:\([^()\n]*\)[^()\n]*)*)\)')
                # Split on fenced code blocks; transform only the segments outside them.
                segments = re.split(r'(```.*?```)', content, flags=re.DOTALL)
                for idx in range(0, len(segments), 2):  # even indices lie outside code fences
                    segments[idx] = img_pattern.sub(repl_img, segments[idx])
                content = "".join(segments)

                with open(args.md_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print("Cleaned YAML frontmatter and image links successfully.")
            except Exception as e:
                print(f"Warning: failed to clean file: {e}", file=sys.stderr)

        # 2. Format math formulas
        target_path = args.md_file if args.md_file else topic_dir
        if not run_cmd([sys.executable, "-m", "magi", "math", "format", target_path]):
            print("Warning: 'magi math format' failed, continuing...", file=sys.stderr)

        if not run_cmd([sys.executable, "-m", "magi", "math", "check", target_path]):
            print("Warning: 'magi math check' failed or found errors, continuing...", file=sys.stderr)

    if not args.skip_lint:
        # 3. Lint / Index update
        if not run_cmd([sys.executable, "-m", "magi", "lint", "--fix", topic_dir]):
            print("Warning: 'magi lint' failed", file=sys.stderr)

        if not run_cmd([sys.executable, "-m", "magi", "graph", "build", topic_dir]):
            print("Warning: 'magi graph build' failed", file=sys.stderr)

        if not run_cmd([sys.executable, "-m", "magi", "wiki", "reindex", topic_dir]):
            print("Warning: 'magi wiki reindex' failed", file=sys.stderr)
    
    # 4. No log. `log.md` is retired (design-v2 §2): the record is the posts in
    #    `threads/`, read in time order with `magi feed`. Writing the same
    #    events to a second place is how the two start disagreeing. `--log-msg`
    #    is still accepted so existing callers do not break; it goes nowhere.

if __name__ == "__main__":
    sys.exit(main())
