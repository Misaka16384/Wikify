"""magi skills — install MAGI's skills into whichever agent CLI you use.

MAGI's skills are host-agnostic prose: they teach *when and why* to run the
deterministic ``magi`` commands. What differs per host is only where the file
goes and what wrapper it needs to become a slash command. This module owns
that table, so every supported CLI gets the same skills instead of Claude
Code getting them through the plugin and everyone else copying directories by
hand. The table of hosts itself lives in `core.hosts` -- one record per CLI,
shared with the reviewer and the transcript readers.

Scopes:
- ``project`` (default) — into the MAGI workspace you are standing in, so the
  skills exist where they are useful and nowhere else.
- ``global`` — user level, every project on the machine. Opt-in only: these
  skills are about *this* research workspace (ingest into raw/, compile into
  wiki/, query the graph), so loading them into every unrelated repo just
  spends the agent's attention for nothing.

The skill files ship inside the wheel (``magi/skills/*/SKILL.md``), so this
works from a plain ``pipx``/``uv tool`` install with no repo checkout and no
network.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .core import hosts

# --------------------------------------------------------------------------
# Packaged skills
# --------------------------------------------------------------------------

def skills_dir() -> Path:
    try:
        import importlib.resources

        res = importlib.resources.files("magi").joinpath("skills")
        path = Path(str(res))
        if path.is_dir():
            return path
    except Exception:
        pass
    return Path(__file__).parent / "skills"


#: The mark on a skill MAGI ships. Install replaces a file that carries it and
#: nothing else — a fork of an official skill necessarily mentions "magi", so
#: the old "does the text say magi" test ate people's edits every install.
ORIGIN_MARK = "origin: magi"


def user_skills_dir() -> Path:
    """Where somebody keeps a skill they made.

    User-level, beside `registry.json`: a skill somebody trained is about how
    *they* work, not about one library, and copying it into every workspace is
    how it starts drifting.
    """
    from magi.core.workspace import config_home

    return config_home() / "skills"


@dataclass
class Skill:
    name: str
    path: Path          # the SKILL.md itself
    description: str
    extras: List[Path] = field(default_factory=list)   # templates/ etc.
    official: bool = True

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")


def _frontmatter_description(text: str) -> str:
    """Pull `description:` out of the YAML header without a yaml dependency."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    head = text[3:end if end > 0 else len(text)]
    for line in head.split("\n"):
        if line.strip().startswith("description:"):
            val = line.split(":", 1)[1].strip()
            return val.strip('"').strip("'")
    return ""


def _skills_under(root: Path, official: bool) -> List[Skill]:
    out: List[Skill] = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        extras = sorted((d / "templates").glob("*.md")) if (d / "templates").is_dir() else []
        out.append(Skill(name=d.name, path=md,
                         description=_frontmatter_description(
                             md.read_text(encoding="utf-8", errors="replace")),
                         extras=extras, official=official))
    return out


def load_skills() -> List[Skill]:
    """The eight MAGI ships, plus whatever the person made.

    A name in both places is the person's: they went and wrote one, and the
    packaged copy losing to it is the whole point of the directory existing.
    """
    packaged = {skill.name: skill for skill in _skills_under(skills_dir(), True)}
    for skill in _skills_under(user_skills_dir(), False):
        packaged[skill.name] = skill
    return [packaged[name] for name in sorted(packaged)]


# --------------------------------------------------------------------------
# Hosts — "where does a skill get installed?"
#
# There is no host table here any more. There is one, in `core.hosts`, and it
# answers this question alongside the two that used to have tables of their
# own: what to run for a headless call, and whose session record we can read.
# Three tables edited separately is how the same vendor ended up under two
# names, and how one probe came to look for a binary that another table spelled
# differently.
#
# What is left here is the part that is actually about *installing*: turning a
# record's path templates into real directories, and writing files into them.
# --------------------------------------------------------------------------

Host = hosts.Host
Drop = hosts.Drop
HOST_ALIASES = hosts.ALIASES


def _home() -> Path:
    return Path.home()


def resolve_host(name: str) -> str:
    """The key for a host somebody named, however they spelled it."""
    return hosts.resolve(name)


def catalog(config: Optional[dict] = None) -> Dict[str, Host]:
    """Every host: the built-in records, plus whatever `research.hosts` adds."""
    return hosts.catalog(config)


HOSTS: Dict[str, Host] = hosts.catalog()


def detected(host: Host) -> bool:
    """Is this CLI on the machine? Its binary on PATH, or its config dir."""
    if shutil.which(host.command):
        return True
    marker = hosts.expand(host.marker)
    try:
        return bool(marker and marker.exists())
    except OSError:
        return False


def _is_workspace(path: Path) -> bool:
    try:
        from magi.core.workspace import is_hub_root, is_topic_root

        return bool(is_topic_root(path) or is_hub_root(path))
    except Exception:
        return False


def workspace_anchor(start: Optional[Path] = None) -> Path:
    """Where a project-scope install belongs.

    The MAGI workspace root (topic first, then hub) rather than the cwd: you
    might be three directories deep in raw/ when you run this, and the agent
    CLI is launched from the workspace root.
    """
    cur = (start or Path.cwd()).resolve()
    try:
        from magi.core.workspace import find_workspace_root

        root = find_workspace_root(cur)
        if root is not None:
            return Path(root)
    except Exception:
        pass
    return cur


# --------------------------------------------------------------------------
# Rendering: one skill, in the shape a given target expects
# --------------------------------------------------------------------------

def _split_frontmatter(text: str):
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[: end + 4], text[end + 4:].lstrip("\n")


def render_command(skill: Skill) -> str:
    """A slash-command file whose body is the skill itself.

    Command files are opaque prompt templates — they cannot point at a skill,
    so the instructions are inlined. `$ARGUMENTS` carries whatever the user
    typed after the slash command.
    """
    _, body = _split_frontmatter(skill.text)
    desc = skill.description.replace("\n", " ").strip()
    return (
        "---\n"
        f"description: {desc}\n"
        "---\n\n"
        f"{body.rstrip()}\n\n"
        "---\n\n"
        "Apply the workflow above to this request (empty means: ask what to work on, "
        "or pick the obvious next step from `magi sync`):\n\n"
        "$ARGUMENTS\n"
    )


def files_for(skill: Skill, target: Drop, dest: Path):
    """(path, text) pairs this skill contributes to one target directory."""
    if target.layout == "dir":
        out = [(dest / skill.name / "SKILL.md", skill.text)]
        for extra in skill.extras:
            out.append((dest / skill.name / "templates" / extra.name,
                        extra.read_text(encoding="utf-8", errors="replace")))
        return out
    text = render_command(skill) if target.kind == "command" else skill.text
    return [(dest / f"{skill.name}.md", text)]


# --------------------------------------------------------------------------
# Install / uninstall
# --------------------------------------------------------------------------

def target_dir(target: Drop, scope: str, project_root: Optional[Path] = None) -> Optional[Path]:
    """Where one host's skills go.

    A project-scope install is anchored on the *workspace*, not the cwd. You
    may be three directories deep in `raw/` when you run this; the agent CLI is
    launched from the workspace root and looks there. Anchoring here rather
    than in each record is what stopped one host (Claude Code, whose template
    did not anchor) putting skills in a directory nothing reads.

    `None` means "nowhere": the host declares no directory at this scope, which
    Codex does — it has no project-level `~/.codex/skills`.
    """
    if scope == "global":
        return hosts.expand(target.global_dir)
    return hosts.expand(target.project_dir, root=workspace_anchor(project_root))


def _write(path: Path, text: str, force: bool) -> str:
    """Returns one of: created | updated | unchanged | skipped."""
    if path.exists():
        try:
            current = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            current = None
        if current == text:
            return "unchanged"
        if not force and current is not None and ORIGIN_MARK not in current:
            # Not a file MAGI wrote — somebody else's, or a fork of ours they
            # have since made their own. A fork necessarily still mentions
            # "magi", which is why the mark and not the word decides.
            return "skipped"
        path.write_text(text, encoding="utf-8", newline="\n")
        return "updated"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return "created"


def install_host(host: Host, skills: List[Skill], scope: str, force: bool,
                 dry_run: bool, project_root: Optional[Path] = None,
                 override_dir: Optional[Path] = None) -> Dict:
    placements = []
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    written: List[str] = []

    for target in host.drops:
        dest = override_dir if override_dir is not None else target_dir(target, scope, project_root)
        if dest is None:
            # A host can have several directories and only some of them exist
            # at this scope (Codex has no project-level ~/.codex/skills). That
            # is not an error as long as another target covers the scope.
            continue
        sub = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        for sk in skills:
            for path, text in files_for(sk, target, dest):
                if dry_run:
                    key = "updated" if path.exists() else "created"
                else:
                    key = _write(path, text, force)
                sub[key] += 1
                counts[key] += 1
                if key in ("created", "updated"):
                    written.append(str(path))
        placements.append({
            "kind": target.kind,
            "dir": str(dest),
            "invoke": target.invoke.format(name="<skill>") if "{name}" in target.invoke else target.invoke,
            "counts": sub,
        })
        if override_dir is not None:
            break  # an explicit --dir means "put it here", once

    if not placements:
        placements.append({"kind": "skill", "dir": None,
                           "error": f"{host.label} has no {scope} scope"})

    return {
        "host": host.key,
        "label": host.label,
        "scope": scope,
        "placements": placements,
        "counts": counts,
        "files": written,
        "note": host.note,
    }


def _ours(path: Path) -> bool:
    """Did MAGI write this? Only what carries the mark is ours to remove.

    A directory-layout skill used to be deleted whole, so somebody's own
    `~/.claude/skills/research/` — their prompt, their reference files — went
    with one `magi skills uninstall`. Install already refuses to overwrite a
    file without the mark; removing has to ask the same question.
    """
    md = path / "SKILL.md" if path.is_dir() else path
    try:
        return ORIGIN_MARK in md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def uninstall_host(host: Host, skills: List[Skill], scope: str, dry_run: bool,
                   project_root: Optional[Path] = None,
                   override_dir: Optional[Path] = None) -> Dict:
    removed: List[str] = []
    for target in host.drops:
        dest = override_dir if override_dir is not None else target_dir(target, scope, project_root)
        if dest is None:
            continue
        for sk in skills:
            path = (dest / sk.name) if target.layout == "dir" else (dest / f"{sk.name}.md")
            if not path.exists():
                continue
            removed.append(str(path))
            if dry_run:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except OSError:
                    pass
        if override_dir is not None:
            break
    return {"host": host.key, "label": host.label, "scope": scope, "removed": removed}


def detected_hosts(config: Optional[dict] = None) -> List[Host]:
    return [host for host in catalog(config).values() if detected(host)]


def installed_state(skills: List[Skill], project_root: Optional[Path] = None,
                    config: Optional[dict] = None) -> List[Dict]:
    """Where the skills currently are, per host / scope / target."""
    rows = []
    for host in catalog(config).values():
        for scope in ("global", "project"):
            for target in host.drops:
                dest = target_dir(target, scope, project_root)
                if dest is None:
                    continue
                present, stale = 0, 0
                for sk in skills:
                    path, text = files_for(sk, target, dest)[0]
                    if not path.exists():
                        continue
                    present += 1
                    try:
                        if path.read_text(encoding="utf-8", errors="replace") != text:
                            stale += 1
                    except OSError:
                        stale += 1
                rows.append({
                    "host": host.key, "label": host.label, "scope": scope,
                    "kind": target.kind, "dir": str(dest), "exists": dest.exists(),
                    "detected": detected(host),
                    "installed": present, "outdated": stale, "total": len(skills),
                    "invoke": target.invoke.format(name="<skill>") if "{name}" in target.invoke else target.invoke,
                })
    return rows


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _prompt_for_hosts(found: List[Host]) -> List[Host]:
    """Ask which CLIs to install into.

    Installing into every agent CLI on the machine is rarely what someone
    wants — most people drive a workspace from one. Asking costs a keystroke
    and avoids littering three other tools.
    """
    print("Which agent CLI should get these skills?\n")
    for i, h in enumerate(found, 1):
        print(f"  {i}. {h.label}")
    print(f"  a. all {len(found)} of them")
    print("  q. cancel\n")
    try:
        answer = input("choice [1]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return []
    if answer in ("q", "quit", "n", "no"):
        return []
    if answer in ("a", "all"):
        return found
    if not answer:
        return found[:1]
    picked = []
    for part in answer.replace(",", " ").split():
        if not part.isdigit() or not (1 <= int(part) <= len(found)):
            raise SystemExit(f"not one of the options: {part!r}")
        picked.append(found[int(part) - 1])
    return picked


def _resolve_hosts(names: Optional[List[str]], interactive: bool = False,
                   config: Optional[dict] = None) -> List[Host]:
    table = catalog(config)
    if names == ["all"]:
        return list(table.values())
    if names == ["auto"]:
        return detected_hosts(config)
    if names:
        out = []
        for n in names:
            h = table.get(resolve_host(n))
            if h is None:
                known = ", ".join(sorted(set(table) | set(HOST_ALIASES)))
                raise SystemExit(f"unknown host {n!r} — known: {known} (or auto/all)")
            out.append(h)
        return out

    found = detected_hosts(config)
    if len(found) <= 1:
        return found
    if interactive:
        return _prompt_for_hosts(found)
    names_ = " ".join(f"--host {h.key}" for h in found)
    raise SystemExit(
        "several agent CLIs are installed — say which one:\n"
        + "\n".join(f"  magi skills install --host {h.key:<12} # {h.label}" for h in found)
        + "\n  magi skills install --host auto       # all of them"
        + f"\n(or pass them together: {names_})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi skills",
        description="Install MAGI's agent skills into your CLI agent(s) so they are "
                    "available as slash commands.")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="List the skills that ship with this installation.")
    p_list.add_argument("--json", action="store_true")

    p_where = sub.add_parser("where", help="Show every host, its skills directory, and what is installed there.")
    p_where.add_argument("--json", action="store_true")

    for name, helptext in (("install", "Copy the skills into a host's skills directory."),
                           ("uninstall", "Remove MAGI's skills from a host's skills directory.")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--host", action="append", default=None,
                       help=f"Which agent CLI ({', '.join(HOSTS)}). Repeatable. Omit and you "
                            f"are asked; 'auto' = every detected CLI, 'all' = every known one.")
        p.add_argument("--scope", choices=["project", "global"], default="project",
                       help="project (default): into the MAGI workspace you are in. "
                            "global: every project on this machine — rarely what you want, "
                            "since these skills only do anything inside a workspace.")
        p.add_argument("--project-root", default=None,
                       help="Workspace a project-scope install belongs to "
                            "(default: discovered from cwd)")
        p.add_argument("--dir", default=None,
                       help="Write to this directory instead of the host's standard location.")
        p.add_argument("--only", action="append", default=None,
                       help="Limit to one skill name. Repeatable.")
        p.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")
        p.add_argument("--json", action="store_true")
        if name == "install":
            p.add_argument("--force", action="store_true",
                           help="Overwrite files that do not look like ours.")

    args = parser.parse_args(argv)
    cmd = args.cmd or "where"

    # A host somebody declared in `research.hosts` is a host. Read from the
    # workspace we are standing in, and never fatal: a config that will not
    # parse costs you your own host records, not the built-in ones.
    try:
        from .core.config_loader import load_config

        config = load_config(start=str(workspace_anchor()))
    except Exception:
        config = {}

    skills = load_skills()
    if not skills:
        msg = {"error": "no skills found in this installation",
               "hint": "reinstall: pipx upgrade --install magi-research "
                       "(or uv tool install --force magi-research)"}
        print(json.dumps(msg, ensure_ascii=False) if getattr(args, "json", False)
              else f"error: {msg['error']} — {msg['hint']}")
        return 1

    if getattr(args, "only", None):
        wanted = set(args.only)
        unknown = wanted - {s.name for s in skills}
        if unknown:
            print(f"unknown skill(s): {', '.join(sorted(unknown))}")
            return 1
        skills = [s for s in skills if s.name in wanted]

    if cmd == "list":
        if args.json:
            print(json.dumps({"count": len(skills),
                              "skills": [{"name": s.name, "description": s.description} for s in skills]},
                             ensure_ascii=False))
            return 0
        print(f"{len(skills)} skills ship with magi:\n")
        for s in skills:
            print(f"  {s.name}")
            if s.description:
                print(f"      {s.description[:110]}")
        print("\nInstall them:  magi skills install            # every detected agent CLI")
        print("               magi skills install --scope project   # just this directory")
        return 0

    if cmd == "where":
        rows = installed_state(skills, config=config)
        if args.json:
            print(json.dumps({"hosts": rows,
                              "detected": [h.key for h in detected_hosts(config)]},
                             ensure_ascii=False))
            return 0
        det = [h.key for h in detected_hosts(config)]
        print(f"detected agent CLIs: {', '.join(det) if det else '(none)'}\n")
        for r in rows:
            mark = "+" if r["installed"] else " "
            stale = f", {r['outdated']} outdated" if r["outdated"] else ""
            kind = f"{r['scope']}/{r['kind']}"
            print(f"  [{mark}] {r['label']:<22} {kind:<17} {r['installed']}/{r['total']}{stale}")
            print(f"      {r['dir']}")
            print(f"      {r['invoke']}")
        print("\n  magi skills install                 # into this workspace (recommended)")
        print("  magi skills install --scope global  # every project on this machine")
        return 0

    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not args.json
    chosen = _resolve_hosts(args.host, interactive=interactive, config=config)
    if not chosen:
        if interactive and args.host is None:
            print("nothing installed")
            return 0
        msg = ("no agent CLI detected. Pass --host explicitly "
               f"({', '.join(catalog(config))}) or --dir <path>.")
        print(json.dumps({"error": msg}, ensure_ascii=False) if args.json else f"error: {msg}")
        return 1

    override = Path(args.dir).expanduser().resolve() if args.dir else None

    if not args.json and override is None:
        if args.scope == "global":
            print("note: installing globally — these skills only do anything inside a MAGI\n"
                  "      workspace, so every unrelated project will carry them for nothing.\n"
                  "      'magi skills install' (project scope) is usually what you want.\n")
        else:
            anchor = workspace_anchor()
            if not _is_workspace(anchor):
                print(f"note: {anchor} is not a MAGI workspace — installing here anyway.\n"
                      f"      Run this inside a topic workspace (magi init) or its hub for\n"
                      f"      the skills to have something to work on.\n")

    # Which workspace this install belongs to. `--project-root` so a caller
    # that already knows (`magi install --topic-dir X`) does not have to hope
    # the cwd agrees with it.
    project_root = (Path(args.project_root).expanduser().resolve()
                    if getattr(args, "project_root", None) else None)

    reports = []
    for host in chosen:
        if cmd == "install":
            reports.append(install_host(host, skills, args.scope,
                                        getattr(args, "force", False), args.dry_run,
                                        project_root=project_root,
                                        override_dir=override))
        else:
            reports.append(uninstall_host(host, skills, args.scope, args.dry_run,
                                          project_root=project_root,
                                          override_dir=override))

    if args.json:
        print(json.dumps({"action": cmd, "scope": args.scope, "dry_run": args.dry_run,
                          "results": reports}, ensure_ascii=False))
        return 0

    verb = "would " if args.dry_run else ""
    for r in reports:
        if cmd == "install":
            c = r["counts"]
            print(f"  {r['label']} ({r['scope']}): {verb}write {c['created']} new, "
                  f"{c['updated']} updated, {c['unchanged']} already current"
                  + (f", {c['skipped']} skipped (use --force)" if c["skipped"] else ""))
            for pl in r["placements"]:
                if pl.get("error"):
                    print(f"      - {pl['error']}")
                    continue
                print(f"      {pl['kind']:<8} {pl['dir']}")
                trigger = pl["invoke"].replace("<skill>", "ask")
                print(f"               -> {trigger}")
            if r["note"]:
                print(f"      note: {r['note']}")
        else:
            print(f"  {r['label']} ({r['scope']}): {verb}remove {len(r['removed'])} item(s)")
    if not args.dry_run and cmd == "install":
        print("\nRestart the agent CLI (or start a new session) for it to pick them up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
