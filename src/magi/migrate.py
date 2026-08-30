"""magi migrate — upgrade a pre-magi (Wikify-era) workspace in place.

Nothing is rewritten: the bytes of raw/, wiki/, config.md and log.md are
left exactly as they are. The command ADDS what the magi era introduced —
CLAUDE.md / AGENTS.md (agent entry protocol), config.yaml (project
config), scratch/ — then rebuilds the graph and _index tables, and prints
the remaining manual steps (pm init, index, lint).

One thing does move. `wiki/theses/*.md` is relocated into `drafts/` and the
empty directory removed, because v2 splits what a thesis was into a draft
and the propositions it argues for. Files are moved, never merged or
renamed: a name already taken in `drafts/` is left where it is and
reported. Nothing is deleted.

Old installations copied skills/ + bin/ into agent directories
(~/.claude, .agents); those copies are obsolete and should be deleted —
see the README migration section.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from magi.core.wiki_common import parse_frontmatter
from magi.core.workspace import find_workspace_root, is_hub_root
from magi.init_workspace import CLAUDE_POINTER as POINTER, keep_a_copy


def _hub_topics(hub: Path) -> list:
    """The projects under a hub, in a stable order."""
    root = hub / "topics"
    if not root.is_dir():
        return []
    return sorted(
        d for d in root.iterdir()
        if d.is_dir() and d.name != ".archive"
        and ((d / "wiki").is_dir() or (d / "raw").is_dir())
    )


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
    topics = _hub_topics(hub)
    if not topics:
        print(f"Hub detected at {hub} but no projects found under topics/.")
        return 0
    print(f"Hub detected at {hub} — migrating {len(topics)} project(s):\n")
    failures = 0
    for t in topics:
        rc = _migrate_topic(t, hub=hub)
        failures += 1 if rc else 0
        print()
    print(f"Hub migration complete: {len(topics) - failures}/{len(topics)} projects migrated.")

    if follow_up:
        _finish(hub, topics)
    else:
        print("Next: 'magi sync --fix' in each project")

    print("\nEach one is now a project in its own right, registered in "
          "`magi kb list`;")
    print("`magi search` federates over all of them from anywhere.")
    inert = [name for name in ("wikis.json", "topics/_index.md", "log.md")
             if (hub / name).exists()]
    if inert:
        print(f"\nThe hub's own files are inert now ({', '.join(inert)}) — "
              "nothing reads or writes them.")
        print("Delete them when you are ready; MAGI will not, because they are "
              "yours and this command has no way to know what else is in here.")
    print("\nGive your agent CLI each project's skills when you are ready:")
    print("  cd <project> && magi install        # skills, protocol, stop gate")
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
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", input="")
        _echo_sync(proc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi migrate", description=__doc__)
    parser.add_argument("path", nargs="?", help="Project or hub to migrate (default: discovered from cwd)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Say what would change and write nothing. Worth doing first: "
                             "migration moves wiki/theses/*.md into drafts/, and those "
                             "files are the only copy you have.")
    parser.add_argument("--minimal", action="store_true",
                        help="Migrate only. Without this, migration also provisions the task "
                             "store and brings each project to a working state (magi sync --fix).")
    args = parser.parse_args(argv)
    follow_up = not args.minimal

    base = Path(args.path).resolve() if args.path else Path.cwd()
    if is_hub_root(base):
        if args.dry_run:
            for topic in _hub_topics(base):
                preview(topic, hub=base)
                print()
            return 0
        return _migrate_hub(base, follow_up=follow_up)

    root = find_workspace_root(args.path) if args.path else find_workspace_root()
    if root is None:
        # Legacy workspaces predate the marker-file requirement: accept a
        # bare wiki/ or raw/ dir at the given path (or cwd) directly.
        if (base / "wiki").is_dir() or (base / "raw").is_dir():
            root = base
        else:
            print("No project found here. Run inside a project directory "
                  "(a folder containing wiki/ or raw/), at a hub root, or pass a path.",
                  file=sys.stderr)
            return 1

    from magi.core.workspace import find_hub_root

    if args.dry_run:
        return preview(root, hub=find_hub_root(root))

    rc = _migrate_topic(root, hub=find_hub_root(root))
    if rc == 0 and follow_up:
        print("\nFinishing up (skip with --minimal):")
        print("  magi sync --fix")
        proc = subprocess.run([sys.executable, "-m", "magi", "sync", "--fix"], cwd=str(root),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", input="")
        _echo_sync(proc)
        print("\nGive your agent CLI this project's skills:")
        print("  magi skills install        # asks which CLI")
    elif rc == 0:
        print("\nRecommended next steps:")
        print("  magi lint           # v1 never had to pass v2's rules; see what it says")
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
    """The old config.yaml, looked for beside the topic and at the hub.

    The home-directory leg of this search is loose on purpose — Wikify was
    installed by copying a directory, so its config could be under any of
    these — and loose is safe only because `carry_legacy_config` carries just
    the keys this program has. A `config.yaml` under `~/.claude` is far more
    likely to belong to Claude Code than to Wikify.
    """
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
            # A setting MAGI has is one that appears in the scaffolded config
            # or in the defaults above. Anything else is a key from some other
            # program's file — the search looks in `~/.claude` and `~/.gemini`,
            # which belong to the agent CLIs and not to Wikify, and a section
            # the new config lacks used to sail straight through the guard
            # below on `current is None`.
            if not _is_ours(section, key, new, defaults):
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


def _is_ours(section: str, key: str, new: dict, defaults: dict) -> bool:
    """Is `section.key` a setting this program actually has?

    Either the freshly scaffolded config has a slot for it, or it is one of
    the few that are deliberately absent from the scaffold — `mineru_api_token`
    above all, which is left out rather than written empty so that an empty
    string here cannot shadow a token set once in the user-level config.
    """
    here = new.get(section)
    if isinstance(here, dict) and key in here:
        return True
    return key in defaults.get(section, {})


def retire_theses(root: Path, dry_run: bool = False) -> tuple[int, list[str]]:
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
    if not dry_run:
        drafts.mkdir(parents=True, exist_ok=True)

    moved, skipped = 0, []
    for note in sorted(theses.glob("*.md")):
        if note.name == "_index.md":
            continue
        target = drafts / note.name
        if target.exists():
            skipped.append(note.name)
            continue
        if not dry_run:
            shutil.move(str(note), str(target))
        moved += 1

    if not skipped:
        index = theses / "_index.md"
        if _index_is_all_generated(index):
            if not dry_run:
                if index.is_file():
                    index.unlink()
                try:
                    theses.rmdir()
                except OSError:
                    pass
        else:
            skipped.append("_index.md")
    return moved, skipped


#: The one line v1 put under `## Recent Changes` itself, on the day it created
#: the index — `bin/init_workspace.py:create_minimal_index` and the identical
#: block in `bin/llm-wiki.py:ensure_dir_index`, both at the last v1 commit.
#: v1's `index_builder` rebuilt only `wiki/references` and `wiki/concepts`, so
#: in `wiki/theses/_index.md` it was never cleared and is still sitting in
#: every workspace v1 ever made. Matched exactly, date apart: a person writing
#: their own dated bullet under this heading is precisely the case the check
#: around it exists for, and a looser pattern would retire their directory.
_V1_BOOTSTRAP_LINE = re.compile(
    r"^[ \t]*-[ \t]*\d{4}-\d{2}-\d{2}:[ \t]*Created missing index\.?[ \t]*$",
    re.MULTILINE)


def _echo_sync(proc) -> None:
    """Show what `magi sync --fix` did, and all of it when something failed.

    The two loops this replaced each kept an allow-list of line prefixes, and
    a failure's reason starts with none of them: the user was told "2 failed"
    and never told what or why, by the one command whose job is to leave a
    working project behind. Brevity is worth having while everything works and
    is the wrong instinct the moment it does not.
    """
    lines = (proc.stdout or "").strip().splitlines()
    failed = proc.returncode != 0 or any(
        re.search(r"ran \d+ step\(s\), [1-9]\d* failed", line) for line in lines)
    for line in lines:
        if failed or line.startswith(("ran ", "  magi", "still needs you")) \
                or "sync ratio" in line:
            print(f"      {line}")


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
    kept = _V1_BOOTSTRAP_LINE.sub("", kept)
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


def preview(root: Path, hub: Path | None = None) -> int:
    """What migration would do here, having done none of it.

    Honest about one limit: `carry_legacy_config` compares the old config
    against the scaffolded `config.yaml`, which does not exist yet in a dry
    run, so this names the file it would read rather than guessing which keys
    would move.
    """
    name, scope = root.name, "A research project."
    config_md = root / "config.md"
    if config_md.is_file():
        fm = parse_frontmatter(config_md.read_text(encoding="utf-8", errors="replace"))
        name = str(fm.get("title") or name)
        scope = str(fm.get("scope") or scope)

    print(f"Would migrate: {root}")
    print(f"  identity: {name!r} — {scope!r}")

    missing = [f for f in ("CLAUDE.md", "AGENTS.md", "config.yaml")
               if not (root / f).is_file()]
    if missing:
        print(f"  would add: {', '.join(missing)} (+ scratch/, missing _index.md files)")
    else:
        print("  scaffolding already present — would refresh indexes only")

    moved, skipped = retire_theses(root, dry_run=True)
    if moved:
        print(f"  would move {moved} file(s) from wiki/theses/ into drafts/ "
              "and remove the empty directory")
    for left in skipped:
        if left == "_index.md":
            print("  would leave wiki/theses/ in place: its _index.md has notes "
                  "under '## Recent Changes'")
        else:
            print(f"  would leave wiki/theses/{left} in place: drafts/{left} exists")

    claude = root / "CLAUDE.md"
    if claude.is_file():
        current = claude.read_text(encoding="utf-8", errors="replace")
        if current.strip() and current.strip() != POINTER.strip():
            print("  would replace CLAUDE.md with a pointer to AGENTS.md, "
                  "keeping the old text in .backup/")

    legacy_cfg = find_legacy_config(root, hub)
    if legacy_cfg is not None:
        print(f"  would carry still-default settings from {legacy_cfg}")

    for stale in _stale_skill_dirs(root, hub):
        print(f"  WARNING: legacy Wikify skills still at {stale}", file=sys.stderr)

    print("  would rebuild: magi graph build, magi wiki reindex")
    print("\nNothing was written. Re-run without --dry-run to do it.")
    return 0


def _migrate_topic(root: Path, hub: Path | None = None) -> int:
    # Carry the legacy identity into the new scaffolding.
    name, scope = root.name, "A research project."
    config_md = root / "config.md"
    if config_md.is_file():
        fm = parse_frontmatter(config_md.read_text(encoding="utf-8", errors="replace"))
        name = str(fm.get("title") or name)
        scope = str(fm.get("scope") or scope)

    missing = [f for f in ("CLAUDE.md", "AGENTS.md", "config.yaml") if not (root / f).is_file()]
    print(f"Migrating project: {root}")
    print(f"  identity: {name!r} — {scope!r}")
    if missing:
        print(f"  adding: {', '.join(missing)} (+ scratch/, missing _index.md files)")
    else:
        print("  scaffolding already present — refreshing indexes only")

    # init is non-destructive without --force: it only creates what is absent.
    from magi.init_workspace import main as init_main

    rc = init_main(["--topic-dir", str(root), "--name", name, "--scope", scope])
    scaffolded = rc in (0, None)
    if not scaffolded:
        # Everything below this point writes into a workspace that was supposed
        # to exist by now. Say so once here, and again in the return code —
        # which used to be 0 no matter what happened, so a hub whose six topics
        # all failed still printed "6/6 topics migrated".
        print("ERROR: scaffolding failed; this project is not migrated",
              file=sys.stderr)

    for stale in _stale_skill_dirs(root, hub):
        print(f"  WARNING: legacy Wikify skills still at {stale}", file=sys.stderr)
        print("           Codex, agy and opencode all read .agents/skills — they "
              "would follow the old instructions.", file=sys.stderr)
        print(f"           Rename it: mv {stale.parent} {stale.parent}.wikify-backup",
              file=sys.stderr)

    if not scaffolded:
        # Stop here. Everything below writes: `retire_theses` moves every file
        # out of `wiki/theses/` and `point_claude_at_agents` rewrites
        # `CLAUDE.md`. Running them into a workspace this has just told the
        # reader is *not* migrated leaves half a migration behind a message
        # saying none happened — and the half that ran is the destructive one.
        # The warnings above are read-only and worth having either way.
        return 1

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

    derived_failed = []
    for step in (["graph", "build", str(root)], ["wiki", "reindex", str(root)]):
        proc = subprocess.run([sys.executable, "-m", "magi", *step],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = "ok" if proc.returncode == 0 else f"FAILED ({proc.stderr.strip()[-200:]})"
        print(f"  magi {' '.join(step[:2])}: {status}")
        if proc.returncode != 0:
            derived_failed.append(" ".join(step[:2]))

    # A failed graph or index is not a failed migration: both are derived from
    # files that are now in place, and `magi sync --fix` rebuilds them. Saying
    # which one to re-run is more useful than a non-zero exit that stops a hub
    # loop over the topics that would have worked.
    if derived_failed:
        print(f"  note: {', '.join(derived_failed)} can be rebuilt later — "
              f"run 'magi sync --fix' in {root}")

    return 0 if scaffolded else 1


if __name__ == "__main__":
    sys.exit(main())
