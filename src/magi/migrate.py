"""magi migrate — upgrade a pre-magi (Wikify-era) workspace in place.

Non-destructive: existing content (raw/, wiki/, config.md, log.md) is
never touched. The command only ADDS what the magi era introduced —
CLAUDE.md / AGENTS.md (agent entry protocol), config.yaml (workspace
config), scratch/ — then rebuilds the graph and _index tables, and
prints the remaining manual steps (pm init, index).

Old installations copied skills/ + bin/ into agent directories
(~/.claude, .agents); those copies are obsolete and should be deleted —
see the README migration section.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from magi.core.wiki_common import parse_frontmatter
from magi.core.workspace import find_workspace_root, is_hub_root
from magi.init_workspace import CLAUDE_POINTER as POINTER, keep_a_copy


def _migrate_hub(hub: Path, follow_up: bool = True) -> int:
    """Turn a pre-v2 hub into what it always really was: separate libraries.

    Nothing moves on disk. A hub was a parent directory plus a `wikis.json`
    naming the topics under it, and v2 keeps the second half in a better
    place: `magi init` — which each topic goes through here — registers the
    library in the user-level list, so `magi search` federates over all of
    them from anywhere, not only from inside that one parent.

    Moving the directories would be the destructive half of a change whose
    useful half costs nothing, so this does not. The hub's own scaffolding
    stops being read; the command says so and leaves the deletion to a person.
    """
    topics = sorted(
        d for d in (hub / "topics").iterdir()
        if d.is_dir() and d.name != ".archive" and ((d / "wiki").is_dir() or (d / "raw").is_dir())
    )
    if not topics:
        print(f"Hub detected at {hub} but no topics found under topics/.")
        return 0
    print(f"Hub detected at {hub} — migrating {len(topics)} topic(s):\n")
    failures = 0
    for t in topics:
        rc = _migrate_topic(t, hub=hub)
        failures += 1 if rc else 0
        print()
    print(f"Hub migration complete: {len(topics) - failures}/{len(topics)} topics migrated.")

    if follow_up:
        _finish(hub, topics)
    else:
        print("Next: 'magi sync --fix' in each topic")

    print("\nEach topic is now a library in its own right, registered in "
          "`magi kb list`;")
    print("`magi search` federates over all of them from anywhere.")
    inert = [name for name in ("wikis.json", "topics/_index.md", "log.md")
             if (hub / name).exists()]
    if inert:
        print(f"\nThe hub's own files are inert now ({', '.join(inert)}) — "
              "nothing reads or writes them.")
        print("Delete them when you are ready; MAGI will not, because they are "
              "yours and this command has no way to know what else is in here.")
    print("\nGive your agent CLI each topic's skills when you are ready:")
    print("  cd <topic> && magi install        # skills, protocol, stop gate")
    return 1 if failures else 0


def _finish(hub: Path, topics: list[Path]) -> None:
    """Do what the user would otherwise type next.

    Migration ends with a workspace that still needs a task store and an
    index; those are deterministic, idempotent, and exactly what
    `magi sync --fix` already knows how to do.
    """
    # No `pm init` here any more: the task store belongs to a project, not to
    # the parent directory a set of projects happened to share (design-v2 §2).
    # `magi sync` tells each topic when it wants one.
    print("\nFinishing up (skip with --minimal):")
    for topic in topics:
        print(f"  magi sync --fix   ({topic.name})")
        proc = subprocess.run([sys.executable, "-m", "magi", "sync", "--fix"], cwd=str(topic),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (proc.stdout or "").strip().splitlines():
            if line.startswith("ran "):
                print(f"      {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi migrate", description=__doc__)
    parser.add_argument("path", nargs="?", help="Workspace or hub to migrate (default: discovered from cwd)")
    parser.add_argument("--minimal", action="store_true",
                        help="Migrate only. Without this, migration also provisions the task "
                             "store and brings each topic to a working state (magi sync --fix).")
    args = parser.parse_args(argv)
    follow_up = not args.minimal

    base = Path(args.path).resolve() if args.path else Path.cwd()
    if is_hub_root(base):
        return _migrate_hub(base, follow_up=follow_up)

    root = find_workspace_root(args.path) if args.path else find_workspace_root()
    if root is None:
        # Legacy workspaces predate the marker-file requirement: accept a
        # bare wiki/ or raw/ dir at the given path (or cwd) directly.
        if (base / "wiki").is_dir() or (base / "raw").is_dir():
            root = base
        else:
            print("No workspace found here. Run inside a topic directory "
                  "(a folder containing wiki/ or raw/), at a hub root, or pass a path.",
                  file=sys.stderr)
            return 1

    from magi.core.workspace import find_hub_root

    rc = _migrate_topic(root, hub=find_hub_root(root))
    if rc == 0 and follow_up:
        print("\nFinishing up (skip with --minimal):")
        print("  magi sync --fix")
        proc = subprocess.run([sys.executable, "-m", "magi", "sync", "--fix"], cwd=str(root),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (proc.stdout or "").strip().splitlines():
            if line.startswith(("ran ", "  magi", "still needs you")) or "sync ratio" in line:
                print(f"      {line}")
        print("\nGive your agent CLI this workspace's skills:")
        print("  magi skills install        # asks which CLI")
    elif rc == 0:
        print("\nRecommended next steps:")
        print("  magi pm init        # provision beads in this project (work-state tracking)")
        print("  magi index          # build the hybrid retrieval index (needs Ollama for vectors)")
        print("  magi sync           # check the sync ratio")
        print("\nIf you installed the old Wikify skills by copying skills/+bin/ into "
              "~/.claude or .agents/, remove them: magi setup --remove-legacy")
    return rc


# Wikify kept one config.yaml next to its copied scripts. Migration is only
# lossless if those values land in the new per-workspace config — a token the
# user pasted a year ago should not have to be found and pasted again.
_LEGACY_CONFIG_DIRS = (".agents", ".claude", ".gemini")


def find_legacy_config(topic: Path, hub: Path | None = None) -> Path | None:
    """The old config.yaml, looked for beside the topic and at the hub."""
    roots = [topic]
    if hub is not None:
        roots.append(hub)
    roots.append(Path.home())
    for base in roots:
        for d in _LEGACY_CONFIG_DIRS:
            for cfg in (base / d / "config.yaml", base / d / "bin" / "config.yaml"):
                if cfg.is_file():
                    return cfg
    return None


def _stale_skill_dirs(topic: Path, hub: Path | None = None) -> list[Path]:
    """Project-local Wikify skill copies, which `magi setup --remove-legacy`
    does not look for — it only scans the agent CLIs' own home directories."""
    found = []
    for base in ([topic, hub] if hub is not None else [topic]):
        skills = base / ".agents" / "skills"
        if not skills.is_dir():
            continue
        for skill_md in skills.glob("*/SKILL.md"):
            try:
                text = skill_md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "<BIN>" in text or "llm-wiki.py" in text:
                found.append(skills)
                break
    return found


def carry_legacy_config(topic: Path, legacy: Path) -> list[str]:
    """Copy still-default settings across. Returns the keys that changed.

    Only fills values the new config has not been given: an edit the user
    made after migrating always wins, and re-running is a no-op.
    """
    try:
        import yaml

        from magi.core.config_edit import ConfigEditError, set_config_value
    except Exception:
        return []

    target = topic / "config.yaml"
    if not target.is_file():
        return []
    try:
        old = yaml.safe_load(legacy.read_text(encoding="utf-8", errors="replace")) or {}
        new = yaml.safe_load(target.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return []
    if not isinstance(old, dict) or not isinstance(new, dict):
        return []

    # Values a freshly scaffolded config carries; anything still equal to one
    # of these is untouched and safe to overwrite.
    defaults = {
        "ollama": {"base_url": "http://127.0.0.1:11434", "autostart": True},
        "models": {"ocr": "glm-ocr", "embedding": "qwen3-embedding:0.6b"},
        "ocr": {"mineru_api_token": "", "use_mineru": False, "timeout": 180, "dpi": 130},
        "semantic_link": {"threshold": 0.75, "merge_threshold": 0.85,
                          "auto_merge_threshold": 0.95},
    }

    carried: list[str] = []
    for section, values in old.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if value is None or value == "" or isinstance(value, (dict, list)):
                continue
            current = (new.get(section) or {}).get(key)
            if current == value:
                continue
            # Never clobber a deliberate post-migration edit.
            if current is not None and current != defaults.get(section, {}).get(key):
                continue
            try:
                set_config_value(target, f"{section}.{key}", value)
            except ConfigEditError:
                continue
            carried.append(f"{section}.{key}")
    return carried


def retire_theses(root: Path) -> tuple[int, list[str]]:
    """Move `wiki/theses/*` into `drafts/`. Returns (moved, names left behind).

    v2 splits what a thesis was into two things that behave differently: the
    working out, which is a draft and gets edited, and the claims it makes,
    which are propositions with a status somebody has to keep current. Only the
    first half can move mechanically — turning prose into propositions is a
    judgement, so the migration says so and leaves the work to a person and an
    agent reading it together.

    A name already taken in `drafts/` is left where it is rather than merged or
    renamed: two files with one name are somebody's mistake to look at, not a
    migration's to guess about. Re-running is a no-op once the directory is
    gone, which is what makes `magi migrate` safe to repeat.

    The directory's own `_index.md` goes with it, but only when there is
    nothing in it a person wrote. Everything above `## Recent Changes` is
    generated and regenerable; everything below it is carried through by every
    rebuild precisely because somebody typed it there. An index with notes in
    it keeps the directory alive and gets reported, the same as a name that
    was already taken.
    """
    theses = root / "wiki" / "theses"
    if not theses.is_dir():
        return 0, []

    drafts = root / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)

    moved, skipped = 0, []
    for note in sorted(theses.glob("*.md")):
        if note.name == "_index.md":
            continue
        target = drafts / note.name
        if target.exists():
            skipped.append(note.name)
            continue
        shutil.move(str(note), str(target))
        moved += 1

    if not skipped:
        index = theses / "_index.md"
        if _index_is_all_generated(index):
            if index.is_file():
                index.unlink()
            try:
                theses.rmdir()
            except OSError:
                pass
        else:
            skipped.append("_index.md")
    return moved, skipped


def _index_is_all_generated(index: Path) -> bool:
    """Is there anything in this `_index.md` that a rebuild would not restore?

    `## Recent Changes` is the section every index rebuild copies forward
    untouched — which is to say, the section a person writes in. A file with
    words under it is not ours to delete just because the directory around it
    is being retired.
    """
    from .core.wiki_common import INDEX_KEPT_HEADING

    if not index.is_file():
        return True
    try:
        text = index.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False        # unreadable is not "empty"; leave it alone
    if INDEX_KEPT_HEADING not in text:
        return True
    kept = text.split(INDEX_KEPT_HEADING, 1)[1]
    return not kept.strip()


def point_claude_at_agents(root: Path) -> str | None:
    """Reduce `CLAUDE.md` to `@AGENTS.md`. Returns a note for the operator.

    Two files holding the same protocol drift, and once they have, the answer
    to "what was the agent told" depends on which host read which copy. The
    generated protocol is identical in both, so collapsing it loses nothing —
    but a person may have written their own text into `CLAUDE.md`, and that is
    kept where they can find it rather than deleted or silently merged into a
    file the CLI rewrites.
    """
    claude = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    if not claude.is_file():
        claude.write_text(POINTER, encoding="utf-8")
        return None

    current = claude.read_text(encoding="utf-8", errors="replace")
    if current.strip() == POINTER.strip():
        return None

    agents_text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    if current.strip() and current.strip() not in agents_text:
        kept = keep_a_copy(claude)
        claude.write_text(POINTER, encoding="utf-8")
        return (f"CLAUDE.md held text that is not in AGENTS.md; the old copy is at "
                f"{kept.name} — move anything you still want into AGENTS.md, outside "
                f"the magi:begin/end block")

    claude.write_text(POINTER, encoding="utf-8")
    return None


def _migrate_topic(root: Path, hub: Path | None = None) -> int:
    # Carry the legacy identity into the new scaffolding.
    name, scope = root.name, "A topic wiki."
    config_md = root / "config.md"
    if config_md.is_file():
        fm = parse_frontmatter(config_md.read_text(encoding="utf-8", errors="replace"))
        name = str(fm.get("title") or name)
        scope = str(fm.get("scope") or scope)

    missing = [f for f in ("CLAUDE.md", "AGENTS.md", "config.yaml") if not (root / f).is_file()]
    print(f"Migrating workspace: {root}")
    print(f"  identity: {name!r} — {scope!r}")
    if missing:
        print(f"  adding: {', '.join(missing)} (+ scratch/, missing _index.md files)")
    else:
        print("  scaffolding already present — refreshing indexes only")

    # init is non-destructive without --force: it only creates what is absent.
    from magi.init_workspace import main as init_main

    rc = init_main(["--topic-dir", str(root), "--name", name, "--scope", scope])
    if rc not in (0, None):
        print("warning: scaffolding step reported an error; continuing", file=sys.stderr)

    for stale in _stale_skill_dirs(root, hub):
        print(f"  WARNING: legacy Wikify skills still at {stale}", file=sys.stderr)
        print("           Codex, agy and opencode all read .agents/skills — they "
              "would follow the old instructions.", file=sys.stderr)
        print(f"           Rename it: mv {stale.parent} {stale.parent}.wikify-backup",
              file=sys.stderr)

    moved, skipped = retire_theses(root)
    if moved:
        print(f"  wiki/theses/ -> drafts/: {moved} file(s) moved")
        print("           the claims inside them are propositions now — open one with "
              "`magi thread new --kind proposition` and link the draft as its derivation")
    for name in skipped:
        if name == "_index.md":
            print("  WARNING: wiki/theses/_index.md has notes under '## Recent "
                  "Changes'; left the directory in place so you can read them",
                  file=sys.stderr)
        else:
            print(f"  WARNING: drafts/{name} already exists; left "
                  f"wiki/theses/{name} in place", file=sys.stderr)

    note = point_claude_at_agents(root)
    if note:
        print(f"  WARNING: {note}", file=sys.stderr)

    legacy_cfg = find_legacy_config(root, hub)
    if legacy_cfg is not None:
        carried = carry_legacy_config(root, legacy_cfg)
        if carried:
            # Key names only — one of these is usually an API token.
            print(f"  config carried from {legacy_cfg}: {', '.join(carried)}")
        else:
            print(f"  config: nothing to carry from {legacy_cfg}")

    for step in (["graph", "build", str(root)], ["wiki", "reindex", str(root)]):
        proc = subprocess.run([sys.executable, "-m", "magi", *step],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = "ok" if proc.returncode == 0 else f"FAILED ({proc.stderr.strip()[-200:]})"
        print(f"  magi {' '.join(step[:2])}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
