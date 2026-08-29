"""`magi install` — make a workspace usable from an agent CLI, in one command.

Three things have to be true before an agent can work in a MAGI workspace, and
until now each was a different command a person had to know about:

1. the **skills** are where the host looks for them;
2. **`AGENTS.md`** carries the current protocol in its managed block, and
   `CLAUDE.md` points at it rather than holding a second copy;
3. the host runs **`magi sync --close`** when a session ends, so bookkeeping
   that did not happen cannot quietly become tomorrow's wrong projection.

The third is the reason this command exists rather than staying `magi skills
install`. A stop gate that a person has to wire up by hand is a gate that is
wired up in one workspace out of five, and design-v2 §6 leans on it: the
nearest actor writes the status, and something has to notice when they didn't.

**Host enforcement is not symmetric, and this says so rather than pretending.**
Claude Code has a documented Stop hook and gets a real gate. The other hosts
have no equivalent, so there the same rule lives in the managed block as an
instruction — which an agent can ignore, and sometimes will. Writing that down
is more useful than a uniform-looking install that quietly does less on three
of four hosts.

Host config is read, merged and written back — never appended to. An agent
settings file belongs to the person; the only part MAGI owns is its own hook
entry, and it recognises that entry by the command it runs so a second install
updates it instead of adding another.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .core import managed
from .core.wiki_common import atomic_write, parse_frontmatter
from .core import hosts as _hosts
from .core.workspace import find_workspace_root

#: What the stop gate runs. Also the key this command recognises its own hook
#: by, so installing twice updates one entry instead of adding a second.
STOP_COMMAND = "magi sync --close --hook"

#: Hosts with a documented stop hook. Everything else gets the instruction in
#: the managed block and an honest line in the report. Derived from the one
#: host table: a record names its hook writer, the same way it names its
#: transcript reader, because a hook is an entry in that host own settings
#: schema and no template describes one.
HOOKABLE = tuple(host.key for host in _hosts.BUILTIN if host.hook == "claude")


def _settings_path(root: Path, host: str) -> Path | None:
    if host == "claude":
        return root / ".claude" / "settings.json"
    return None


def _load(path: Path) -> dict:
    """Existing settings, or `{}`. A broken file is not overwritten blind."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"{path} is not readable JSON ({exc}). Fix or move it — this command "
            "will not overwrite a settings file it cannot parse.")
    return data if isinstance(data, dict) else {}


def merge_stop_hook(settings: dict, command: str = STOP_COMMAND) -> tuple[dict, bool]:
    """Settings with our Stop hook present exactly once. Returns (settings, changed).

    Everything else in the file is left as it was found, including other Stop
    hooks: a person's own hook and ours are not in competition, and dropping
    theirs to install ours is the kind of helpfulness nobody asks for twice.
    """
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit("settings.json has a 'hooks' key that is not an object; "
                         "fix it by hand rather than let this command guess")
    stops = hooks.setdefault("Stop", [])
    if not isinstance(stops, list):
        raise SystemExit("settings.json has a 'hooks.Stop' that is not a list")

    for group in stops:
        if not isinstance(group, dict):
            continue
        for entry in group.get("hooks", []):
            if isinstance(entry, dict) and entry.get("command") == command:
                return settings, False

    stops.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
    return settings, True


def install_hook(root: Path, host: str, dry_run: bool = False) -> str:
    """Write the stop gate for one host. Returns a line for the report."""
    path = _settings_path(root, host)
    if path is None:
        return (f"{host}: no documented stop hook — the rule is in AGENTS.md, "
                "which the agent can ignore")

    settings, changed = merge_stop_hook(_load(path))
    if not changed:
        return f"{host}: stop gate already installed ({path})"
    if dry_run:
        return f"{host}: would install the stop gate ({path})"

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup = path.with_suffix(path.suffix + ".magi-backup")
        shutil.copy2(path, backup)
    atomic_write(path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    return f"{host}: stop gate installed ({path})"


def write_coaching(root: Path, coaching: str) -> None:
    """Record the coaching level where the *gate* reads it.

    `managed.body` puts the level in the protocol the agent reads; `state`
    reads `research.coaching` out of `config.yaml`. Writing only the first is
    how a workspace ends up telling the agent it is under `strict` while the
    gate that would enforce it computes `light`.
    """
    from .core.config_edit import ConfigEditError, set_config_value

    try:
        set_config_value(root / "config.yaml", "research.coaching", coaching)
    except (ConfigEditError, OSError):
        # A workspace with no readable config is a workspace running on
        # defaults, which is `light` — the same answer, so nothing is lost by
        # not being able to say it out loud.
        pass


def install_protocol(root: Path, coaching: str | None = None,
                    dry_run: bool = False) -> str:
    """Refresh the managed block and the `CLAUDE.md` pointer.

    `coaching=None` means "whatever this workspace already says" — and, in
    particular, do not write it. Re-rendering the block is something several
    commands do (accepting a rule, retiring one, closing a session); every one
    of them used to pass the default and quietly reset the level a person had
    chosen.
    """
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config
    config = root / "config.md"
    front = parse_frontmatter(config.read_text(encoding="utf-8", errors="replace")) \
        if config.is_file() else {}
    name = str(front.get("title") or root.name)
    scope = str(front.get("scope") or "A topic wiki.")

    # Template plus the rules a person accepted: the block's truth is those
    # two things, and whoever changes the ledger re-renders rather than waiting
    # for somebody to run `install` again.
    from .reflect import proposals

    asked = coaching
    if coaching is None:
        coaching = config_get(load_config(start=root), "research.coaching",
                              "light")

    body = managed.body(name, scope, coaching, rules=proposals.live_rules(root))
    if not dry_run and asked is not None:
        # Only when somebody asked for a level. A re-render is not a decision
        # about coaching, and writing it here is how one got made by accident.
        write_coaching(root, asked)
    agents = root / "AGENTS.md"
    if dry_run:
        from .migrate import POINTER

        current = managed.read(agents.read_text(encoding="utf-8")) if agents.is_file() else None
        parts = []
        if current != body.strip():
            parts.append("would rewrite the managed block in AGENTS.md")
        # The real run also collapses `CLAUDE.md` to a pointer, keeping a copy
        # of anything a person wrote there. A dry run that only looked at the
        # block announced "block is current" and then the real run moved that
        # file — a dry run writes nothing, but it still has to predict what a
        # real one does.
        pointer = root / "CLAUDE.md"
        held = pointer.read_text(encoding="utf-8", errors="replace") \
            if pointer.is_file() else ""
        if held.strip() != POINTER.strip():
            parts.append("would point CLAUDE.md at AGENTS.md"
                         + (" (keeping a copy of what is in it)" if held.strip() else ""))
        return "AGENTS.md: " + ("; ".join(parts) if parts
                                else "block is current, CLAUDE.md already a pointer")

    changed = managed.write(agents, body)

    # One protocol, not two: a `CLAUDE.md` holding its own copy is how "what
    # was the agent told" starts depending on which host read which. But this
    # command is the one people run again and again, and it must not eat text
    # somebody wrote — `migrate` already collapses this file the careful way,
    # keeping a copy and saying where it went, so install uses that rather
    # than a second, blunter version of the same idea.
    from .migrate import point_claude_at_agents

    pointer = root / "CLAUDE.md"
    before = pointer.read_text(encoding="utf-8", errors="replace") if pointer.is_file() else ""
    kept = point_claude_at_agents(root)
    after = pointer.read_text(encoding="utf-8", errors="replace") if pointer.is_file() else ""
    if before != after:
        changed = True

    note = "AGENTS.md: managed block rewritten" if changed \
        else "AGENTS.md: block already current"
    return f"{note} ({kept})" if kept else note


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi install",
        description="Install this workspace into your agent CLIs: skills, the "
                    "AGENTS.md protocol block, and the end-of-session gate.")
    parser.add_argument("--host", action="append", default=[],
                        help="Which agent CLI (claude, codex, gemini, opencode). "
                             "Repeatable. Default: every detected one.")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    # No default. `install_protocol` reads the workspace's own level when it
    # is not told one, and writes it only when it is — otherwise every install
    # (adding a host, refreshing skills) silently resets a library that chose
    # strict back to light.
    parser.add_argument("--coaching", choices=["off", "light", "strict"], default=None,
                        help="How hard the block asks its human for a prediction.")
    parser.add_argument("--no-skills", action="store_true",
                        help="Only the protocol block and the hooks.")
    parser.add_argument("--dry-run", action="store_true", help="Change nothing.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)",
              file=sys.stderr)
        return 1

    # Every CLI actually on this machine, not the one that happens to have a
    # stop hook. `HOOKABLE` answers "who can enforce the gate"; it was being
    # read as "who gets an install", so a machine with only Codex had skills
    # written into `.claude/skills`.
    from . import skills_cmd as _skills

    hosts = [_skills.resolve_host(name) for name in args.host] or \
        [host.key for host in _skills.detected_hosts()]
    if not hosts:
        print("no agent CLI detected — pass --host to install anyway "
              f"({', '.join(sorted(_skills.HOSTS))})", file=sys.stderr)
        return 1

    failed = False
    skills_payload = None
    report = [install_protocol(root, args.coaching, args.dry_run)]

    if not args.no_skills:
        from . import skills_cmd

        skills_argv = ["install", "--scope", "project",
                       "--project-root", str(root)]
        for host in hosts:
            skills_argv += ["--host", host]
        if args.dry_run:
            skills_argv.append("--dry-run")
        # Under `--json` the skills step gets `--json` too, and its output is
        # captured rather than printed. It used to write its human-readable
        # report to stdout ahead of the JSON object, so `magi install --json`
        # was not parseable JSON at all — which is the one failure a `--json`
        # flag exists to make impossible.
        if args.json:
            import contextlib
            import io

            skills_argv.append("--json")
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                rc = skills_cmd.main(skills_argv)
            raw = said.getvalue().strip()
            try:
                skills_payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                skills_payload = {"output": raw}
        else:
            rc = skills_cmd.main(skills_argv)
        # The exit code matters: skills failing to install while the protocol
        # block succeeded is a half-installed workspace, and reporting 0 for it
        # is how somebody finds out weeks later.
        if rc != 0:
            report.append("skills: not installed — see the lines above")
            failed = True

    for host in hosts:
        report.append(install_hook(root, host, args.dry_run))

    if args.json:
        payload = {"workspace": str(root), "hosts": hosts, "report": report,
                   "ok": not failed}
        if skills_payload is not None:
            payload["skills"] = skills_payload
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in report:
            print(f"  {line}")
    # Non-zero when any part did not land: a half-installed workspace that
    # reports success is one somebody finds out about weeks later.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
