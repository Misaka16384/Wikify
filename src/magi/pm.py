"""magi pm — Beads (bd) bridge: work/intent state (the Balthasar core).

MAGI does not implement task tracking. Beads owns the work graph; this
module only (1) provisions a hub-level beads database with research issue
types, (2) exposes a JSON status summary for `magi sync`, and (3) syncs
the deterministic compile backlog into bd issues. Agents interact with
`bd` directly (see `bd prime` / `bd --help`); skills teach when.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

from magi.core.workspace import find_workspace_root

RESEARCH_TYPES = ["question", "survey", "derivation", "computation", "experiment", "review"]

_TYPES_BLOCK = (
    "\n# MAGI research issue types (added by 'magi pm init')\n"
    "types:\n  custom:\n" + "".join(f"    - {t}\n" for t in RESEARCH_TYPES)
)


@lru_cache(maxsize=1)
def bd_available() -> bool:
    """Is the `bd` executable on PATH?

    Cached for the life of the process: `shutil.which` is a PATH walk (~7ms
    on Windows) and this is called on every status read, several times per
    HTTP request in the WebUI. Installing bd mid-session is rare enough to
    be worth a restart; `bd_cache_clear()` exists for the tests.
    """
    return shutil.which("bd") is not None


def _prefix_from_dirname(name: str) -> str:
    """ASCII-slugify a directory name into a valid bd issue prefix.

    bd derives its db name from the prefix, so CJK/spaced directory names
    (e.g. "知识 库 hub") must be slugged BEFORE bd init runs — otherwise bd
    fails after having already git-inited the directory. Pure-non-ASCII
    names fall back to "magi".
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "magi"


def _run_bd(args: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bd", *args], cwd=cwd, capture_output=True, text=True,
        timeout=timeout, encoding="utf-8", errors="replace",
    )


def find_beads_root(start: Path | None = None) -> Path | None:
    """Nearest ancestor (of start or cwd) containing a workspace .beads db.

    A workspace database has ``.beads/metadata.json`` (written by ``bd
    init``); this distinguishes it from bd's user-level data directory
    ``~/.beads`` (eventsData etc.), which must not match.
    """
    current = (start or Path.cwd()).resolve()
    for _ in range(30):
        if (current / ".beads" / "metadata.json").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


# `bd status --json` is a subprocess spawn — ~330ms on Windows, where process
# creation is expensive. That is fine once. It is not fine in a fan-out: the
# WebUI's /api/kb builds a sync report per registered knowledge base, and every
# topic under one hub resolves to the SAME beads root, so six KBs meant six
# identical spawns and a 2.5s request that froze the dashboard.
#
# The window is deliberately short. This cache exists to collapse duplicate
# calls inside one logical operation, not to serve stale counts across user
# actions: refresh a second later and you get fresh numbers.
_STATUS_TTL_SECONDS = 2.0
_status_cache: dict[str, tuple[float, dict | None]] = {}
_status_locks: dict[str, threading.Lock] = {}
_status_guard = threading.Lock()


def bd_cache_clear() -> None:
    """Drop the memoized bd lookups. For tests, and for code that has just
    changed the work graph and needs to read its own write."""
    bd_available.cache_clear()
    with _status_guard:
        _status_cache.clear()


def _fresh(key: str) -> tuple[bool, dict | None]:
    with _status_guard:
        hit = _status_cache.get(key)
    if hit is not None and (time.monotonic() - hit[0]) < _STATUS_TTL_SECONDS:
        return True, hit[1]
    return False, None


def bd_status_summary(cwd: Path) -> dict | None:
    """Parse `bd status --json` summary; None when bd/db unavailable.

    Memoized per beads root for `_STATUS_TTL_SECONDS`; see the note above.
    """
    if not bd_available():
        return None

    # Key on the beads root, not the directory asked about: `bd` walks up to
    # find its database, so every topic under one hub gets the same answer.
    # Keyed by directory, the dashboard's per-KB reports and the PM panel each
    # spawned their own `bd status` for one shared database.
    root = find_beads_root(Path(cwd))
    key = str((root or Path(cwd)).resolve())
    ok, cached = _fresh(key)
    if ok:
        return cached

    # One spawn per root, not one per caller. The WebUI fans out over KBs
    # concurrently, so without this the six callers would all miss the cache
    # together and spawn six times anyway — the exact cost being avoided.
    with _status_guard:
        gate = _status_locks.setdefault(key, threading.Lock())
    with gate:
        ok, cached = _fresh(key)      # someone may have filled it while we waited
        if ok:
            return cached

        summary: dict | None = None
        try:
            proc = _run_bd(["status", "--json"], cwd=cwd)
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc is not None and proc.returncode == 0:
            try:
                summary = json.loads(proc.stdout).get("summary")
            except json.JSONDecodeError:
                summary = None

        with _status_guard:
            _status_cache[key] = (time.monotonic(), summary)
        return summary


# --------------------------------------------------------------------------
# listing and acting on tasks
# --------------------------------------------------------------------------

# `magi pm backlog-sync` and the radar's "create reading task" both stamp the
# workspace onto every issue they open. That label is what made a hub-wide
# store answerable per workspace — without it the only honest thing the panel
# could say was "17, and some of them are not yours". It is still written and
# still read, because stores created before v2 sit at a hub root and their
# issues carry it.
TOPIC_LABEL = "topic:"

# What the label means in a v2 project, where the store is already scoped to
# one library: which research line the task belongs to. Beads holds mechanical
# work only — a compile backlog, a reading queue, a review to run. Research
# state lives in `threads/`, where it can carry a status and an argument.
LINE_LABEL = "line:"


def topic_label(workspace: Path) -> str:
    return f"{TOPIC_LABEL}{Path(workspace).name}"


def line_label(line: str) -> str:
    return f"{LINE_LABEL}{line}"


def list_tasks(workspace: Path, scope: str = "workspace",
               include_closed: bool = False, line: str | None = None) -> list[dict] | None:
    """Open issues in this workspace's store. None when there is no store.

    `scope="workspace"` filters to issues labelled for this topic; "hub"
    returns everything under the shared root. The default is the narrow one:
    a panel under a picker naming one library should answer for that library.
    `line` narrows further, to one research line.
    """
    root = find_beads_root(Path(workspace))
    if root is None or not bd_available():
        return None
    args = ["list", "--json"]
    if include_closed:
        args.append("--all")
    if scope == "workspace":
        args += ["--label", topic_label(workspace)]
    if line:
        args += ["--label", line_label(line)]
    try:
        proc = _run_bd(args, cwd=root)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None
    return [_task_row(r, workspace) for r in rows] if isinstance(rows, list) else []


def _task_row(raw: dict, workspace: Path) -> dict:
    """One issue, reduced to what a panel can render and act on.

    The title carries a `[Topic]` prefix because the store is shared and a
    terminal listing has no other way to say which library an issue belongs
    to. On a panel already filtered to that library it is noise, so it moves
    into its own field.
    """
    title = str(raw.get("title") or "")
    labels = [str(x) for x in (raw.get("labels") or [])]
    topic = next((l[len(TOPIC_LABEL):] for l in labels if l.startswith(TOPIC_LABEL)), None)
    line = next((l[len(LINE_LABEL):] for l in labels if l.startswith(LINE_LABEL)), None)
    if topic and title.startswith(f"[{topic}]"):
        title = title[len(topic) + 2:].strip()
    return {
        "id": str(raw.get("id") or ""),
        "title": title,
        "description": str(raw.get("description") or ""),
        "status": str(raw.get("status") or "open"),
        "priority": raw.get("priority"),
        "issue_type": str(raw.get("issue_type") or ""),
        "topic": topic,
        # Which research line asked for this task. Beads holds mechanical work
        # only, so this is how a line's chores stay attached to the line
        # without the line's *state* living in a task tracker.
        "line": line,
        # Whether this issue belongs to the workspace being viewed. A hub-scope
        # listing mixes libraries, and the rows have to say which is which.
        "is_here": topic == Path(workspace).name if topic else False,
        "labels": [l for l in labels
                   if not l.startswith(TOPIC_LABEL) and not l.startswith(LINE_LABEL)],
        "blocked_by": int(raw.get("dependency_count") or 0),
        "blocks": int(raw.get("dependent_count") or 0),
        "updated_at": str(raw.get("updated_at") or ""),
    }


#: What the WebUI may do to an issue. A closed set, for the same reason the
#: ops table is a closed set: the endpoint takes an action name off the wire.
TASK_ACTIONS = ("start", "close", "reopen")


def act_on_task(workspace: Path, task_id: str, action: str) -> tuple[bool, str]:
    """Run one whitelisted action. Returns (ok, message)."""
    if action not in TASK_ACTIONS:
        return False, f"unknown action: {action}"
    root = find_beads_root(Path(workspace))
    if root is None:
        return False, "no task store for this workspace"
    args = {
        # --claim is idempotent and sets assignee + in_progress in one step,
        # which is what "start" means to a person.
        "start": ["update", task_id, "--claim"],
        "close": ["close", task_id],
        "reopen": ["reopen", task_id],
    }[action]
    try:
        proc = _run_bd(args, cwd=root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}"
    bd_cache_clear()          # the counts above the list are now stale
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()[-300:]
    return True, (proc.stdout or "").strip()[-300:]


def _agreed_to_hand_over(root: Path, assumed_yes: bool) -> bool:
    """Say what `bd init` will do to this directory, and on a terminal, ask.

    It was said afterwards, under `bd`'s own output — by which point the git
    commit is in their history under their name and the hooks are installed,
    and the only decision left is whether to undo it.

    Only prompts on a tty. Agents run this command too, and a question nobody
    can answer is a hang; without a terminal the notice is printed and the run
    continues, which is the same information at the only moment it can still
    be acted on.
    """
    print(f"'magi pm init' hands {root} to bd (Beads), another program. It will:")
    print("  - create .beads/ and a task database")
    print("  - run 'git init' here if this is not a repository yet")
    print("  - commit the files it created, authored by your own git identity")
    print("  - install its own agent hook files (.claude/, AGENTS.md)")
    print("Task tracking is optional in MAGI — nothing else needs it.")
    # `isatty` is not "is there a person who can answer": a server started
    # from a terminal hands its own tty to every child it spawns, so a WebUI
    # job answered True here and then hung on `input()`. It is still the right
    # question for a bare pipe; the caller that knows better says so with
    # `--yes`, which is what the WebUI button does.
    if assumed_yes or not sys.stdin.isatty():
        return True
    try:
        answer = input("Go ahead? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        answer = ""
    if answer not in ("y", "yes"):
        # Naming `--yes` here rather than only in `--help`: this path is
        # reached most often by something running without a person attached,
        # and "nothing was handed over" with no way forward is where it stops.
        print("nothing was handed over. Pass --yes to go ahead without being "
              "asked.")
        return False
    return True


def cmd_init(args: argparse.Namespace) -> int:
    # The project root, not the hub above it. A store shared by every topic in
    # a hub could only answer "17 issues, and some of them are yours" — which
    # is why every issue had to carry a `topic:` label to be findable again.
    # One store per project makes the scoping structural instead.
    root = Path(args.path).resolve() if args.path else (find_workspace_root() or Path.cwd())
    if not bd_available():
        print("bd (Beads) is not installed. See https://github.com/gastownhall/beads — "
              "on Windows: irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex",
              file=sys.stderr)
        return 1

    beads_dir = root / ".beads"
    if (beads_dir / "metadata.json").is_file():
        print(f"beads already initialized at {root}")
    else:
        prefix = args.prefix or _prefix_from_dirname(root.name)
        if not _agreed_to_hand_over(root, getattr(args, "yes", False)):
            return 1
        proc = _run_bd(["init", "--prefix", prefix], cwd=root, timeout=300)
        lines = proc.stdout.splitlines()
        if lines:
            sys.stdout.write("\n".join(lines[-20:]) + "\n")
        print("note: bd init created .beads/ and may git-init the directory "
              "and install agent hook files (.claude/, AGENTS.md)")
        if proc.returncode != 0:
            err_lines = proc.stderr.splitlines()
            if err_lines:
                sys.stderr.write("\n".join(err_lines[-20:]) + "\n")
            return proc.returncode

    config = beads_dir / "config.yaml"
    text = config.read_text(encoding="utf-8") if config.is_file() else ""
    if "types:" in text:
        print("custom types already configured in .beads/config.yaml")
    else:
        with open(config, "a", encoding="utf-8") as f:
            f.write(_TYPES_BLOCK)
        print(f"research issue types configured: {', '.join(RESEARCH_TYPES)}")
    return 0


def cmd_backlog_sync(args: argparse.Namespace) -> int:
    """Create a bd issue (type: task, label: magi-compile) per uncompiled raw source."""
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    beads_root = find_beads_root(topic)
    if beads_root is None or not bd_available():
        print("bd/beads database not available (run 'magi pm init' first)", file=sys.stderr)
        return 1

    from magi.kb.detect_uncompiled import find_uncompiled

    uncompiled = find_uncompiled(topic)
    if not uncompiled:
        print("backlog clean: no uncompiled sources")
        return 0

    # Idempotence: skip sources whose issue title already exists. --all
    # includes CLOSED issues, so a wontfix'd compile task stays dead
    # instead of resurrecting on every backlog-sync. Titles are matched
    # exactly (not by substring): the legacy un-prefixed title is a
    # substring of every topic's new "[<topic>] ..." title, so substring
    # matching would wrongly skip other topics' sources.
    existing_titles: set[str] = set()
    proc = _run_bd(["list", "--json", "--all", "--label", "magi-compile", "--limit", "1000"], cwd=beads_root)
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            data = []
        if isinstance(data, dict):
            data = data.get("issues") or []
        existing_titles = {i.get("title", "") for i in data if isinstance(i, dict)}

    created = skipped = 0
    for rel in uncompiled:
        legacy_title = f"Compile raw source: {rel}"
        title = f"[{topic.name}] {legacy_title}"
        # Match both the current title form and the pre-topic-prefix legacy
        # form so old issues still count as tracked.
        if title in existing_titles or legacy_title in existing_titles:
            skipped += 1
            continue
        proc = _run_bd(
            ["create", "-t", "task", title,
             "--label", "magi-compile", "--label", f"topic:{topic.name}",
             "-d", f"Run the compile skill for {rel} in {topic}"],
            cwd=beads_root,
        )
        if proc.returncode == 0:
            created += 1
        else:
            print(f"warning: bd create failed for {rel}: {proc.stderr[-200:]}", file=sys.stderr)
    print(f"backlog sync: {created} created, {skipped} already tracked")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi pm", description=__doc__)
    sub = parser.add_subparsers(dest="pm_command", required=True)

    p_init = sub.add_parser(
        "init",
        help="Initialize beads (hub-level) with research issue types",
        description="Initialize beads (hub-level) with research issue types. "
                    "Note: bd init creates .beads/ and may git-init the directory "
                    "and install agent hook files (.claude/, AGENTS.md).",
    )
    p_init.add_argument("path", nargs="?", help="Directory for the beads db (default: hub root from cwd)")
    p_init.add_argument("--prefix", help="Issue id prefix (default: ASCII slug of the directory name, or 'magi')")
    p_init.add_argument("--yes", action="store_true",
                        help="Do not ask before handing the directory to bd.")
    p_init.set_defaults(func=cmd_init)

    p_backlog = sub.add_parser("backlog-sync",
                               help="Create bd issues for uncompiled raw sources")
    p_backlog.add_argument("--topic-dir",
                           help="Topic workspace (default: discovered from cwd)")
    p_backlog.set_defaults(func=cmd_backlog_sync)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
