"""magi skills — install MAGI's skills into whichever agent CLI you use.

MAGI's skills are host-agnostic prose: they teach *when and why* to run the
deterministic ``magi`` commands. What differs per host is only where the file
goes and what wrapper it needs to become a slash command. This module owns
that table, so every supported CLI gets the same skills instead of Claude
Code getting them through the plugin and everyone else copying directories by
hand.

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
from typing import Callable, Dict, List, Optional

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
# Host table — "where does a skill get installed?"
#
# One of three tables in this codebase that list hosts, and they answer three
# different questions:
#
#   `skills_cmd.HOSTS`      where a skill gets installed (this one)
#   `review.HOSTS`          what binary to run for a headless call
#   `reflect.transcripts`   whose session record we know how to read
#
# The keys here are products; `review`'s are commands. That is why one vendor
# appears as `antigravity` here and `gemini` there — the product is Antigravity,
# the command is `gemini`. A person types one word, so `gemini` is accepted as
# an alias for this table (see `resolve_host`) and is what `--help` names.
# --------------------------------------------------------------------------

def _home() -> Path:
    return Path.home()


#: The word a person types -> the key this table uses. One vendor, two names,
#: and nobody should have to learn which command wants which.
HOST_ALIASES = {"gemini": "antigravity"}


def resolve_host(name: str) -> str:
    """The key for a host somebody named, however they spelled it."""
    key = str(name or "").strip().lower()
    return HOST_ALIASES.get(key, key)


@dataclass
class Target:
    """One directory a host loads instructions from.

    Hosts differ in two ways that matter: the folder they scan, and whether
    what lands there becomes a slash command or something the model invokes
    on its own when the description matches. Both are worth installing — a
    slash command is discoverable, description-matching is automatic.
    """

    kind: str                       # "skill" | "command"
    global_dir: Callable[[], Path]
    project_dir: Optional[Callable[[Path], Path]]
    layout: str                     # "dir" -> <target>/<name>/SKILL.md ; "flat" -> <target>/<name>.md
    invoke: str                     # what the user types, or how it fires


@dataclass
class Host:
    key: str
    label: str
    binary: str
    targets: List[Target]
    marker: Callable[[], Path]      # config dir whose presence proves the host is installed
    note: str = ""

    def detected(self) -> bool:
        if shutil.which(self.binary):
            return True
        try:
            return self.marker().exists()
        except Exception:
            return False


def _config_home_opencode() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else _home() / ".config"
    return base / "opencode"


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


# Verified against each CLI on 2026-08-20 (their own docs + a live install).
# `.agents/skills/` is the cross-agent convention: Codex, Antigravity and
# opencode all scan it, which is why the project scope converges there.
HOSTS: Dict[str, Host] = {
    "claude": Host(
        key="claude", label="Claude Code", binary="claude",
        marker=lambda: _home() / ".claude",
        targets=[
            Target(kind="skill",
                   global_dir=lambda: _home() / ".claude" / "skills",
                   project_dir=lambda root: root / ".claude" / "skills",
                   layout="dir",
                   invoke="/{name}"),
        ],
        note="The magi plugin already serves these as /magi:<name>; a copy here also "
             "answers to a plain /<name>.",
    ),
    "codex": Host(
        key="codex", label="Codex CLI", binary="codex",
        marker=lambda: _home() / ".codex",
        targets=[
            Target(kind="skill",
                   global_dir=lambda: _home() / ".agents" / "skills",
                   project_dir=lambda root: workspace_anchor(root) / ".agents" / "skills",
                   layout="dir",
                   invoke="$" + "{name}  (or let Codex pick it by description)"),
            Target(kind="skill",
                   global_dir=lambda: _home() / ".codex" / "skills",
                   project_dir=None,     # Codex has no project-level .codex/skills
                   layout="dir",
                   invoke="$" + "{name}  (Codex-native location)"),
        ],
        note="Codex skills are not slash commands: type $<name> to force one, or let it "
             "choose by description.",
    ),
    "antigravity": Host(
        key="antigravity", label="Antigravity CLI (agy)", binary="agy",
        marker=lambda: _home() / ".gemini" / "config",
        targets=[
            Target(kind="skill",
                   global_dir=lambda: _home() / ".gemini" / "config" / "skills",
                   project_dir=lambda root: workspace_anchor(root) / ".agents" / "skills",
                   layout="dir",
                   invoke="named in your prompt, or auto by description (/skills lists them)"),
        ],
        note="agy has no per-skill slash command — /skills browses what is loaded.",
    ),
    "opencode": Host(
        key="opencode", label="opencode", binary="opencode",
        marker=lambda: _config_home_opencode(),
        targets=[
            Target(kind="command",
                   global_dir=lambda: _config_home_opencode() / "commands",
                   project_dir=lambda root: root / ".opencode" / "commands",
                   layout="flat",
                   invoke="/{name}"),
            Target(kind="skill",
                   global_dir=lambda: _config_home_opencode() / "skills",
                   project_dir=lambda root: root / ".opencode" / "skills",
                   layout="dir",
                   invoke="auto by description"),
        ],
        note="opencode separates the two: commands/ gives you /<name>, skills/ lets the model "
             "reach for it unprompted. Both get installed.",
    ),
}


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


def files_for(skill: Skill, target: "Target", dest: Path):
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

def target_dir(target: "Target", scope: str, project_root: Optional[Path] = None) -> Optional[Path]:
    if scope == "global":
        return target.global_dir()
    if target.project_dir is None:
        return None
    return target.project_dir(project_root or Path.cwd())


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

    for target in host.targets:
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


def uninstall_host(host: Host, skills: List[Skill], scope: str, dry_run: bool,
                   project_root: Optional[Path] = None,
                   override_dir: Optional[Path] = None) -> Dict:
    removed: List[str] = []
    for target in host.targets:
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


def detected_hosts() -> List[Host]:
    return [h for h in HOSTS.values() if h.detected()]


def installed_state(skills: List[Skill], project_root: Optional[Path] = None) -> List[Dict]:
    """Where the skills currently are, per host / scope / target."""
    rows = []
    for host in HOSTS.values():
        for scope in ("global", "project"):
            for target in host.targets:
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
                    "detected": host.detected(),
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


def _resolve_hosts(names: Optional[List[str]], interactive: bool = False) -> List[Host]:
    if names == ["all"]:
        return list(HOSTS.values())
    if names == ["auto"]:
        return detected_hosts()
    if names:
        out = []
        for n in names:
            h = HOSTS.get(resolve_host(n))
            if h is None:
                known = ", ".join(sorted(set(HOSTS) | set(HOST_ALIASES)))
                raise SystemExit(f"unknown host {n!r} — known: {known} (or auto/all)")
            out.append(h)
        return out

    found = detected_hosts()
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
        rows = installed_state(skills)
        if args.json:
            print(json.dumps({"hosts": rows, "detected": [h.key for h in detected_hosts()]},
                             ensure_ascii=False))
            return 0
        det = [h.key for h in detected_hosts()]
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
    hosts = _resolve_hosts(args.host, interactive=interactive)
    if not hosts:
        if interactive and args.host is None:
            print("nothing installed")
            return 0
        msg = ("no agent CLI detected. Pass --host explicitly "
               f"({', '.join(HOSTS)}) or --dir <path>.")
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

    reports = []
    for host in hosts:
        if cmd == "install":
            reports.append(install_host(host, skills, args.scope, getattr(args, "force", False),
                                        args.dry_run, override_dir=override))
        else:
            reports.append(uninstall_host(host, skills, args.scope, args.dry_run,
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
