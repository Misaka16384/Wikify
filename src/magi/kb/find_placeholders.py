import sys
import re
import argparse
from pathlib import Path
import json

def find_placeholders(filepath):
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        sys.exit(1)

    # Patterns
    patterns = [
        (r'\[STUB: Awaiting synthesis\]', 'stub_tag'),
        (r'No explicit.*', 'no_explicit_text'),
        (r'^\s*\*\s+\*\*(.*?)\*\*\s*:\s*$', 'empty_bullet')
    ]
    compiled_patterns = [(re.compile(p), name) for p, name in patterns]

    results = []

    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line_stripped = line.rstrip('\n')
            for regex, name in compiled_patterns:
                match = regex.search(line_stripped)
                if match:
                    # For empty bullets, it's nice to extract the bold text as context
                    context = match.group(1) if name == 'empty_bullet' else match.group(0)
                    results.append({
                        "line": line_num,
                        "type": name,
                        "text": line_stripped.strip(),
                        "context_hint": context.strip()
                    })
                    break  # Avoid matching multiple patterns on the same line

    return results

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki placeholders", description="Find placeholders in a markdown file.")
    parser.add_argument("file", help="Path to the markdown file")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args(argv)

    results = find_placeholders(args.file)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not results:
            print("No placeholders found.")
            sys.exit(0)
        
        print(f"Found {len(results)} placeholders in {args.file}:\n")
        for res in results:
            print(f"Line {res['line']} ({res['type']}): {res['text']}")

if __name__ == "__main__":
    sys.exit(main())
