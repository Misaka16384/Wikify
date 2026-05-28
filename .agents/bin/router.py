import sys
import json
from pathlib import Path

def expand_leading_tilde(value: str) -> Path:
    if value == "~":
        return Path.home()
    if value.startswith("~/"):
        return Path.home() / value[2:]
    return Path(value)


def resolve_registry_path(raw_path: str, hub: Path) -> Path:
    if raw_path in {".", "<HUB>", "HUB"}:
        return hub
    if raw_path.startswith("<HUB>/"):
        return hub / raw_path[len("<HUB>/"):]
    if raw_path.startswith("HUB/"):
        return hub / raw_path[len("HUB/"):]
    path = expand_leading_tilde(raw_path)
    if path.is_absolute():
        return path
    return hub / path

def main():
    if len(sys.argv) != 3:
        print("Usage: python router.py <path_to_hub> <slug>", file=sys.stderr)
        sys.exit(1)
        
    hub_path = Path(sys.argv[1]).resolve()
    slug = sys.argv[2]
    
    registry_path = hub_path / "wikis.json"
    if not registry_path.exists():
        print(f"Error: Registry not found at {registry_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except Exception as e:
        print(f"Error reading registry: {e}", file=sys.stderr)
        sys.exit(1)
        
    wikis = registry.get("wikis", {})
    entry = wikis.get(slug)
    
    if not entry:
        print(f"Error: Topic '{slug}' not found in registry.", file=sys.stderr)
        sys.exit(1)
        
    is_archived = entry.get("status") == "archived"
    
    if entry.get("path"):
        topic_path = resolve_registry_path(entry["path"], hub_path)
    else:
        if is_archived:
            topic_path = hub_path / "topics" / ".archive" / slug
        else:
            topic_path = hub_path / "topics" / slug
            
    # Output only the path to stdout for easy parsing by scripts/agents
    print(str(topic_path))

if __name__ == "__main__":
    main()
