import sys
import json
from pathlib import Path
import datetime

def main():
    if len(sys.argv) != 2:
        print("Usage: python hub-init.py <path_to_hub>")
        sys.exit(1)
    
    hub_path = Path(sys.argv[1]).resolve()
    
    # Create directories
    topics_dir = hub_path / "topics"
    archive_dir = topics_dir / ".archive"
    
    topics_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize wikis.json
    registry_path = hub_path / "wikis.json"
    if not registry_path.exists():
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump({"wikis": {}}, f, indent=2)
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
        
    print(f"Hub successfully initialized at {hub_path}")

if __name__ == "__main__":
    main()
