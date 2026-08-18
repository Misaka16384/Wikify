import sys
import json
import argparse
from pathlib import Path
import datetime

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi hub init", description="Initialize a central wiki hub")
    parser.add_argument("hub_path", metavar="path_to_hub", nargs="?", default=".", help="Path to the hub directory (default: current directory)")
    args = parser.parse_args(argv)

    hub_path = Path(args.hub_path).resolve()
    
    # Create directories
    topics_dir = hub_path / "topics"
    archive_dir = topics_dir / ".archive"
    
    topics_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize wikis.json
    registry_path = hub_path / "wikis.json"
    if not registry_path.exists():
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump({"wikis": {}}, f, indent=2, ensure_ascii=False)
        print(f"Initialized registry at {registry_path}")
    else:
        print(f"Registry already exists at {registry_path}")
        
    # Scaffold root _index.md
    index_path = hub_path / "_index.md"
    if not index_path.exists():
        with open(index_path, "w", encoding="utf-8") as f:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            f.write(f"---\ntitle: \"Wiki Hub\"\ntype: hub\ncreated: {date_str}\nupdated: {date_str}\nsummary: \"Central Knowledge Hub\"\n---\n\n# Wiki Hub\n\nWelcome to your central knowledge hub.\n\n## Active Topics\n\n")
        print(f"Initialized index at {index_path}")
    else:
        print(f"Index already exists at {index_path}")

    # Scaffold log.md (required by `llm-wiki lint` for hubs; archive/restore
    # operations append audit entries here and silently no-op if it is missing).
    log_path = hub_path / "log.md"
    if not log_path.exists():
        with open(log_path, "w", encoding="utf-8") as f:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            f.write(f"# Wiki Hub Log\n\n> Operation history for the central hub.\n\n## [{date_str}] hub-init | hub initialized\n")
        print(f"Initialized log at {log_path}")
    else:
        print(f"Log already exists at {log_path}")

    print(f"Hub successfully initialized at {hub_path}")

if __name__ == "__main__":
    sys.exit(main())
