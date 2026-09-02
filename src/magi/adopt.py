r"""Adopt an existing folder of research material into a MAGI project.

`magi init` already runs in a non-empty directory — it is purely additive. What
it cannot do is decide what the material already there *is*: which subtree is
someone else's papers and which is the human's own working out. That judgment
belongs to whoever can read the files. This module carries the mechanical work
around that judgment.

  survey  read-only inventory: what is here, how big, what it links to
  apply   move what a plan says to move, and record every move
  undo    put it back

What earns this module its place is `plan_rewrites`. Research folders are held
together by ordinary relative links — `plans/INDEX.md` points at
`../field-survey/` and `../mobility-barrier/WMIN.md`. Moving whole directories
happens to preserve them, but a folder messy enough to be worth adopting cannot
be fitted to MAGI's shape that way: sooner or later a file has to go somewhere
its neighbours do not. Refusing at that point hands the problem back to the
person, so `apply` repairs the links instead, in the same pass and by the same
arithmetic that found them — including the paths written in prose, which
nothing renders and nothing else would ever check.

Every repair is recorded next to the move that caused it, so `undo` puts the
words back as well as the files.

Nothing here deletes. `apply` refuses to overwrite, refuses to leave the
project, and writes a manifest `undo` can read back.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from magi.core.workspace import find_workspace_root, is_topic_root

# MAGI's own furniture. Adopting a folder must never propose moving the
# scaffold that was just written into it.
SCAFFOLD = {
    "raw", "wiki", "drafts", "threads", "inbox", "output", "scratch",
    "AGENTS.md", "CLAUDE.md", "config.md", "config.yaml", "log.md",
    "decisions.md", "_index.md", ".gitignore", ".claude", ".agents",
    ".opencode", ".backup",
}

# Not material, and not ours to move either.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", ".ipynb_checkpoints"}

# `[text](target)`.
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# A path written in a code span — `../plans/INDEX.md`. Not a link, so nothing
# renders it and nothing checks it, but it is how half of a research folder
# refers to the other half, and a move stops it matching just the same. The
# span must be *entirely* a path with no spaces, so `python tools/x.py` is not
# one of these.
_TEXT_PATH = re.compile(r"`([^`\s]+\.[A-Za-z0-9]{1,6})`")
_ARXIV = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})|(?<![\w.])(\d{4}\.\d{4,5})(?![\w.])")
_DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")


def _walk(d: Path):
    """Every file under `d`, skipping the directories nobody adopts."""
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            yield Path(root) / f


def _histogram(d: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in _walk(d):
        out[f.suffix.lower() or "(none)"] = out.get(f.suffix.lower() or "(none)", 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _links_in(path: Path) -> list[str]:
    """Relative link targets in one markdown file, exactly as written.

    The `#anchor` stays on: these strings are the keys the rewriter matches
    against the file's own text, so a target trimmed here is a link that never
    gets repaired. A link that is *only* an anchor points inside its own file
    and no move can disturb it.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for target in _MD_LINK.findall(text):
        t = target.strip().split()[0] if target.strip() else ""
        if not t or t.startswith(("http://", "https://", "mailto:", "#")):
            continue
        out.append(t)
    return out


def identities_in(root: Path) -> dict[str, list[str]]:
    """arXiv ids and DOIs written anywhere in the markdown.

    A literature table is the densest thing in a research folder — one file can
    carry thirty references — and pulling the ids out of it is a regex, not a
    reading task. What each one is *worth* is the reading task.
    """
    arxiv: set[str] = set()
    doi: set[str] = set()
    for f in _walk(root):
        if f.suffix.lower() not in (".md", ".markdown", ".txt", ".bib"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for a, b in _ARXIV.findall(text):
            arxiv.add(a or b)
        doi.update(_DOI.findall(text))
    return {"arxiv": sorted(arxiv), "doi": sorted(doi)}


def _material(root: Path) -> list[Path]:
    """Top-level entries that are somebody's research material.

    A folder that is already a project has real scaffold in it. A folder that
    is not has only names that happen to collide — `log.md` in a research repo
    is a person's work log, and calling it MAGI's would be how a person's file
    gets treated as furniture.
    """
    project = is_topic_root(root)
    out = []
    for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if p.name in SKIP_DIRS:
            continue
        if project and p.name in SCAFFOLD:
            continue
        out.append(p)
    return out


def _row(p: Path, root: Path, project: bool) -> dict:
    row: dict = {
        "path": p.relative_to(root).as_posix(),
        "name": p.name,
        "kind": "dir" if p.is_dir() else "file",
        # In a project, this name *is* the scaffold. Outside one, it only
        # collides with a name magi would later want.
        "scaffold": project and p.name in SCAFFOLD,
        "name_collision": (not project) and p.name in SCAFFOLD,
    }
    if p.is_dir():
        files = list(_walk(p))
        row["files"] = len(files)
        row["bytes"] = sum(f.stat().st_size for f in files if f.is_file())
        row["types"] = _histogram(p)
        row["depth"] = max((len(f.relative_to(p).parts) for f in files), default=0)
    else:
        row["bytes"] = p.stat().st_size
        row["types"] = {p.suffix.lower() or "(none)": 1}
        if p.suffix.lower() in (".md", ".markdown", ".txt"):
            head = p.read_text(encoding="utf-8", errors="replace")[:400]
            row["head"] = head.strip().splitlines()[0][:120] if head.strip() else ""
    return row


def survey(root: Path, depth: int = 1) -> dict:
    """What is in this folder, one row per entry, `depth` levels down.

    A repo whose whole content sits under one wrapper directory — `research/`
    holding everything — surveys as a single useless row at depth 1, so a lone
    wrapper is descended through automatically and said so.
    """
    project = is_topic_root(root)
    descended = []
    base = root
    while depth >= 1:
        mat = _material(base)
        if len(mat) == 1 and mat[0].is_dir():
            base = mat[0]
            descended.append(base.relative_to(root).as_posix())
            continue
        break

    def rows(d: Path, level: int) -> list[dict]:
        # An inventory lists everything, scaffold included and marked. Hiding
        # a row is how a survey reads clean while leaving something out; what
        # may be *moved* is `_validate`'s question, not this one.
        out = []
        for p in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if p.name in SKIP_DIRS:
                continue
            out.append(_row(p, root, project))
            if p.is_dir() and level < depth:
                out.extend(rows(p, level + 1))
        return out

    entries = rows(base, 1)

    md = [f for f in _walk(root) if f.suffix.lower() in (".md", ".markdown")]
    return {
        "root": str(root),
        "is_project": project,
        "descended_into": descended,
        "entries": entries,
        "markdown_files": len(md),
        "internal_links": sum(len(_links_in(f)) for f in md),
        "identities": identities_in(root),
    }


# --------------------------------------------------------------------------
# moving
# --------------------------------------------------------------------------

def _relocate(p: Path, moves: list[tuple[Path, Path]]) -> Path:
    """Where `p` ends up once `moves` have been applied."""
    for src, dst in moves:
        if p == src:
            return dst
        try:
            rel = p.relative_to(src)
        except ValueError:
            continue
        return dst / rel
    return p


def _retarget(f: Path, raw: str, moves: list[tuple[Path, Path]]) -> str | None:
    """Where `raw`, written inside `f`, has to point once the moves are done.

    None when nothing needs doing: it never resolved, or it still lands on the
    same file afterwards. An anchor rides along untouched.
    """
    path, _, anchor = raw.partition("#")
    if not path:
        return None
    try:
        target = (f.parent / path).resolve()
    except (OSError, ValueError):
        return None
    if not target.exists():
        return None                        # already dangling; not this plan's
    new_f, new_t = _relocate(f, moves), _relocate(target, moves)
    try:
        if (new_f.parent / path).resolve() == new_t:
            return None                    # the move kept it by itself
    except (OSError, ValueError):
        return None
    rel = os.path.relpath(new_t, new_f.parent).replace(os.sep, "/")
    return rel + ("#" + anchor if anchor else "")


def _rewrite_text(text: str, mapping: dict[str, str], prose: bool) -> str:
    """Substitute link targets only, never the words around them."""
    out = _MD_LINK.sub(
        lambda m: m.group(0).replace(m.group(1), mapping[m.group(1).strip()])
        if m.group(1).strip() in mapping else m.group(0), text)
    if prose:
        out = _TEXT_PATH.sub(
            lambda m: f"`{mapping[m.group(1)]}`" if m.group(1) in mapping
            else m.group(0), out)
    return out


def plan_rewrites(root: Path, moves: list[tuple[Path, Path]],
                  prose: bool = True) -> list[dict]:
    """Every link edit the moves make necessary, worked out before anything moves.

    A messy folder cannot be fitted to MAGI's shape by moving whole directories
    alone — sooner or later a file has to go somewhere its neighbours do not.
    Refusing at that point hands the problem back to the person. The arithmetic
    that proves a link is about to break is the same arithmetic that says where
    it should point instead, so this does the second half as well.

    Prose paths — a bare `../plans/INDEX.md` inside a code span — are repaired
    too. Nothing renders them, so nothing else would ever notice, and in a
    research folder they carry as much of the structure as the real links do.
    """
    out = []
    for f in _walk(root):
        if f.suffix.lower() not in (".md", ".markdown"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        edits: dict[str, str] = {}
        kind: dict[str, str] = {}
        for raw in _links_in(f):
            new = _retarget(f, raw, moves)
            if new and new != raw:
                edits[raw], kind[raw] = new, "link"
        if prose:
            for raw in _TEXT_PATH.findall(text):
                if raw in edits:
                    continue
                new = _retarget(f, raw, moves)
                if new and new != raw:
                    edits[raw], kind[raw] = new, "prose"
        if edits:
            out.append({
                "file": f.relative_to(root).as_posix(),
                "moves_to": _relocate(f, moves).relative_to(root).as_posix(),
                "edits": [{"old": k, "new": v, "kind": kind[k]}
                          for k, v in edits.items()],
            })
    return out


def apply_rewrites(root: Path, rewrites: list[dict], prose: bool = True,
                   reverse: bool = False) -> int:
    """Write the edits out.

    Both directions read the file at `moves_to`: going forward, the moves have
    already happened; undoing, they have not been reversed yet. Only the
    mapping flips.
    """
    n = 0
    for r in rewrites:
        f = root / r["moves_to"]
        if not f.is_file():
            continue
        pairs = [(e["new"], e["old"]) if reverse else (e["old"], e["new"])
                 for e in r["edits"]]
        mapping = dict(pairs)
        # newline="" in both directions: repointing one link is not a licence
        # to rewrite every line ending in someone's file, and the default
        # translation on Windows does exactly that.
        with open(f, encoding="utf-8", newline="") as fh:
            text = fh.read()
        new = _rewrite_text(text, mapping, prose)
        if new != text:
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            n += len(r["edits"])
    return n


def _read_plan(path: Path, root: Path) -> list[tuple[Path, Path]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    moves = []
    for m in data.get("moves", []):
        src = (root / m["from"]).resolve()
        dst = (root / m["to"]).resolve()
        moves.append((src, dst))
    return moves


def _validate(root: Path, moves: list[tuple[Path, Path]]) -> list[str]:
    errs = []
    seen_dst: set[Path] = set()
    for src, dst in moves:
        rel = src.name
        if not src.exists():
            errs.append(f"{rel}: nothing there to move")
            continue
        if not src.is_relative_to(root) or not dst.is_relative_to(root):
            errs.append(f"{rel}: a move must stay inside the project")
            continue
        if src == root:
            errs.append(f"{rel}: that is the project itself")
            continue
        if src.name in SCAFFOLD and src.parent == root:
            errs.append(f"{rel}: that is MAGI's own scaffold, not your material")
            continue
        if dst.exists():
            errs.append(f"{rel}: {dst.relative_to(root).as_posix()} already exists — "
                        "adopting never overwrites")
            continue
        if dst in seen_dst:
            errs.append(f"{rel}: two moves want the same destination")
            continue
        if dst.is_relative_to(src):
            errs.append(f"{rel}: cannot move a directory inside itself")
            continue
        seen_dst.add(dst)
    return errs


def cmd_survey(args) -> int:
    root = Path(args.path or ".").resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1
    data = survey(root, depth=args.depth)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print(f"{data['root']}")
    print(f"  {'a MAGI project already' if data['is_project'] else 'not a MAGI project yet'}"
          f" — {data['markdown_files']} markdown files, "
          f"{data['internal_links']} relative links between them")
    if data["descended_into"]:
        print(f"  everything sits under {data['descended_into'][-1]}/ — "
              "listing from there")
    for e in data["entries"]:
        indent = "  " * (len(Path(e["path"]).parts) - 1)
        mark = ("  (magi's own)" if e["scaffold"] else
                "  (name magi also wants)" if e["name_collision"] else "")
        label = indent + e["name"] + ("/" if e["kind"] == "dir" else "")
        if e["kind"] == "dir":
            types = " ".join(f"{k}:{v}" for k, v in list(e["types"].items())[:4])
            print(f"  {label:<34} {e['files']:>4} files  {types}{mark}")
        else:
            print(f"  {label:<34} {'':>4}         "
                  f"{e.get('head', '')[:48]}{mark}")
    ids = data["identities"]
    if ids["arxiv"] or ids["doi"]:
        print(f"\n  references written in the text: {len(ids['arxiv'])} arXiv, "
              f"{len(ids['doi'])} DOI")
        print("  queue them with: magi ingest url " +
              " ".join(ids["arxiv"][:3]) + (" ..." if len(ids["arxiv"]) > 3 else ""))
    return 0


def cmd_apply(args) -> int:
    root = Path(args.project_dir or find_workspace_root() or ".").resolve()
    plan_path = Path(args.plan).resolve()
    if not plan_path.is_file():
        print(f"error: no plan at {plan_path}", file=sys.stderr)
        return 1
    moves = _read_plan(plan_path, root)
    if not moves:
        print("the plan moves nothing")
        return 0

    errs = _validate(root, moves)
    if errs:
        for e in errs:
            print(f"error: {e}", file=sys.stderr)
        return 1

    rewrites = plan_rewrites(root, moves, prose=not args.no_prose)
    n_edits = sum(len(r["edits"]) for r in rewrites)
    if rewrites:
        kinds = [e["kind"] for r in rewrites for e in r["edits"]]
        print(f"{n_edits} reference(s) in {len(rewrites)} file(s) point at "
              f"something these moves relocate "
              f"({kinds.count('link')} link, {kinds.count('prose')} in prose)"
              f"{' — they will be repointed' if not args.no_rewrite else ''}:")
        for r in rewrites[:6]:
            for e in r["edits"][:2]:
                print(f"  {r['file']}:  {e['old']}  ->  {e['new']}")
        if len(rewrites) > 6:
            print(f"  ... and {len(rewrites) - 6} more file(s)")

    if rewrites and args.no_rewrite and not args.break_links:
        print("\nerror: --no-rewrite leaves those dangling. Move whole "
              "directories to keep them, or pass --break-links to accept it.",
              file=sys.stderr)
        return 1

    if args.dry_run:
        for src, dst in moves:
            print(f"  would move  {src.relative_to(root).as_posix()}"
                  f"  ->  {dst.relative_to(root).as_posix()}")
        print(f"\n{len(moves)} move(s), {n_edits} reference(s) "
              f"{'left to dangle' if args.no_rewrite else 'repointed'}")
        return 0

    # A move can fail halfway — a file open in an editor is enough on Windows.
    # `_validate` made the *plan* all-or-nothing, but carrying it out was not:
    # the manifest was written after the loop, so a failure on move three left
    # two moves done and nothing able to undo them. Whatever completed gets
    # recorded even when the loop dies, because the manifest is the only route
    # back.
    done = []
    failure: Exception | None = None
    try:
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            done.append({"from": src.relative_to(root).as_posix(),
                         "to": dst.relative_to(root).as_posix()})
            print(f"  moved  {done[-1]['from']}  ->  {done[-1]['to']}")
    except OSError as exc:
        failure = exc
        print(f"\nerror: stopped after {len(done)} of {len(moves)} move(s): {exc}",
              file=sys.stderr)

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    man_dir = root / "output" / "adopt"
    man_dir.mkdir(parents=True, exist_ok=True)
    man = man_dir / f"{stamp}.json"
    # Not after a partial move: the rewrites were computed for the whole plan,
    # so repointing links at files that never moved would break the ones that
    # still work. The manifest below still records what did move.
    edited = 0 if (args.no_rewrite or failure) else apply_rewrites(
        root, rewrites, prose=not args.no_prose)
    if edited:
        print(f"  repointed {edited} reference(s)")

    # Moving everything out of `research/` leaves `research/` sitting there.
    # Nothing in this module deletes, so it is named rather than removed —
    # an empty directory nobody mentions is one the person finds later and
    # wonders whether the adoption half-failed.
    emptied = sorted({src.parent for src, _ in moves
                      if src.parent != root and src.parent.is_dir()
                      and not any(src.parent.iterdir())})
    for d in emptied:
        print(f"  {d.relative_to(root).as_posix()}/ is empty now — "
              "left in place, yours to remove")

    man.write_text(json.dumps({"root": str(root), "moves": done,
                               "rewrites": [] if (args.no_rewrite or failure)
                                           else rewrites,
                               "prose": not args.no_prose}, indent=2,
                              ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(done)} moved. Undo with: magi adopt undo "
          f"{man.relative_to(root).as_posix()}")
    return 1 if failure else 0


def _latest_manifest(root: Path) -> Path | None:
    d = root / "output" / "adopt"
    got = sorted(d.glob("*.json")) if d.is_dir() else []
    return got[-1] if got else None


def cmd_undo(args) -> int:
    root = Path(args.project_dir or find_workspace_root() or ".").resolve()
    man = Path(args.manifest).resolve() if args.manifest else _latest_manifest(root)
    if not man or not man.is_file():
        print("error: no manifest to undo — nothing has been applied here",
              file=sys.stderr)
        return 1
    data = json.loads(man.read_text(encoding="utf-8"))
    moves = data.get("moves", [])
    problems = []
    for m in reversed(moves):
        src, dst = root / m["to"], root / m["from"]
        if not src.exists():
            problems.append(f"{m['to']} is not where the manifest left it")
        elif dst.exists():
            problems.append(f"{m['from']} is occupied again")
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        print("nothing was moved back", file=sys.stderr)
        return 1
    # Words first, while the files are still where the rewrite left them.
    undone = apply_rewrites(root, data.get("rewrites", []),
                            prose=data.get("prose", True), reverse=True)

    for m in reversed(moves):
        (root / m["from"]).parent.mkdir(parents=True, exist_ok=True)
        (root / m["to"]).rename(root / m["from"])
        print(f"  put back  {m['from']}")
    man.rename(man.with_suffix(".json.undone"))
    print(f"\n{len(moves)} move(s) undone" +
          (f", {undone} reference(s) put back" if undone else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi adopt", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="adopt_command", required=True)

    p_s = sub.add_parser("survey", help="Read-only inventory of a folder")
    p_s.add_argument("path", nargs="?", help="Folder to look at (default: .)")
    p_s.add_argument("--depth", type=int, default=1,
                     help="How many levels to list (default: 1; a lone wrapper "
                          "directory is always descended through)")
    p_s.add_argument("--json", action="store_true", help="Machine-readable output")
    p_s.set_defaults(func=cmd_survey)

    p_a = sub.add_parser("apply", help="Carry out the moves a plan describes")
    p_a.add_argument("plan", help="Plan file: {\"moves\": [{\"from\":..,\"to\":..}]}")
    p_a.add_argument("--project-dir", "--topic-dir", dest="project_dir",
                     help="Project root (default: discovered)")
    p_a.add_argument("--dry-run", action="store_true", help="Say what would move")
    p_a.add_argument("--no-rewrite", action="store_true",
                     help="Move without repointing the references")
    p_a.add_argument("--no-prose", action="store_true",
                     help="Repoint real links only, not paths written in prose")
    p_a.add_argument("--break-links", action="store_true",
                     help="With --no-rewrite: accept the dangling references")
    p_a.set_defaults(func=cmd_apply)

    p_u = sub.add_parser("undo", help="Put back what the last apply moved")
    p_u.add_argument("manifest", nargs="?", help="Manifest (default: the newest)")
    p_u.add_argument("--project-dir", "--topic-dir", dest="project_dir",
                     help="Project root (default: discovered)")
    p_u.set_defaults(func=cmd_undo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
