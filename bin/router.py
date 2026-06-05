import sys
import json
import os
import re
from pathlib import Path

def wash_windows_path(path_str: str) -> str:
    if os.name != "nt":
        return path_str
    if not path_str:
        return path_str

    # Handle /tmp
    if path_str.startswith("/tmp"):
        import tempfile
        temp_dir = tempfile.gettempdir()
        rest = path_str[4:]
        rest = rest.replace("/", "\\")
        if rest.startswith("\\"):
            return temp_dir + rest
        return temp_dir + "\\" + rest

    # Handle drive letters /c/... or /C/... or /c
    match = re.match(r"^/([a-zA-Z])(/.*)?$", path_str)
    if match:
        drive = match.group(1).upper()
        rest = match.group(2) or ""
        rest = rest.replace("/", "\\")
        return f"{drive}:{rest}"

    # General absolute unix-like path starting with /
    if path_str.startswith("/") and not path_str.startswith("//"):
        try:
            current_drive = Path.cwd().drive or "C:"
        except Exception:
            current_drive = "C:"
        rest = path_str.replace("/", "\\")
        return f"{current_drive}{rest}"

    return path_str


def get_home_directory() -> Path:
    home_env = os.environ.get("HOME")
    if home_env:
        return Path(wash_windows_path(home_env))

    userprofile_env = os.environ.get("USERPROFILE")
    if userprofile_env:
        return Path(wash_windows_path(userprofile_env))

    return Path.home()


def expand_leading_tilde(value: str) -> Path:
    if value == "~":
        return get_home_directory()
    if value.startswith("~/"):
        return get_home_directory() / value[2:]
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
        
    raw_hub_path = sys.argv[1]
    if os.name == "nt":
        raw_hub_path = wash_windows_path(raw_hub_path)
    hub_path = Path(raw_hub_path).resolve()
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
