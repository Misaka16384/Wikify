"""magi guide — the built-in operating manual, readable by humans and agents.

One markdown source (``magi/docs/guide.{zh,en}.md``) serves three surfaces:
the WebUI's Docs tab and this command. The parser
here is the single implementation — ``magi.ui.api`` imports it instead of
re-reading the files, so chapter/anchor semantics can never diverge between
what a person reads and what an agent queries.

Design notes:
- Headings carry stable ``{#anchor}`` ids. Those ids are the addressing
  scheme for every surface: a deep link in the WebUI, ``magi guide install``
  in a terminal, and a chapter reference in an agent's answer all name the
  same thing.
- ``--json`` shapes are a contract (same rule as the rest of the CLI): they
  are what the skill and any future ``magi mcp`` tool consume.
- The troubleshooting index is derived from the prose at runtime, never
  maintained separately, so it cannot drift from the manual.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .core import hosts as _hosts

LANGS = ("zh", "en")

_ANCHOR_RE = re.compile(r"\s*\{#([A-Za-z0-9_-]+)\}\s*$")
_FENCE_RE = re.compile(r"^\s*```")
_CALLOUT_RE = re.compile(r"^>\s*\[!([A-Z]+)\]\s*(.*)$")
# Command names the extractor will pick out of a code block, as "the thing to
# run next". Every agent CLI the project knows about is in here by
# construction: a hand-kept list silently drops the examples written for
# whichever host somebody forgot to add to it.
_CMD_TOOLS = ("magi", "bd", "ollama", "uv", "pipx", "curl", "powershell",
              "schtasks", "launchctl") + tuple(
                  host.command for host in _hosts.BUILTIN)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# First cell of a table header that marks the table as a symptom index.
_SYMPTOM_HEADERS = ("症状", "你看到的", "symptom", "what you see")


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def docs_dir() -> Path:
    try:
        import importlib.resources

        res = importlib.resources.files("magi").joinpath("docs")
        path = Path(str(res))
        if path.is_dir():
            return path
    except Exception:
        pass
    return Path(__file__).parent / "docs"


def available_langs() -> List[str]:
    d = docs_dir()
    if not d.is_dir():
        return []
    return sorted(p.name.split(".")[1] for p in d.glob("guide.*.md") if p.is_file())


def normalize_lang(lang: Optional[str]) -> str:
    return "en" if (lang and lang.strip().lower().startswith("en")) else "zh"


def load_guide(lang: Optional[str] = None) -> Tuple[str, str]:
    """Return (markdown, lang_actually_served). Falls back to the other language."""
    want = normalize_lang(lang)
    d = docs_dir()
    for code in (want, "en" if want == "zh" else "zh"):
        path = d / f"guide.{code}.md"
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace"), code
            except OSError:
                continue
    return "", want


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def _strip_anchor(heading: str) -> Tuple[str, Optional[str]]:
    m = _ANCHOR_RE.search(heading)
    if not m:
        return heading.strip(), None
    return heading[: m.start()].strip(), m.group(1)


def parse_chapters(text: str) -> List[Dict[str, Any]]:
    """Split the manual into chapters (h2) and sections (h3).

    Headings inside fenced blocks are ignored — a sample radar digest in the
    manual contains a literal ``## title`` line and must not become a chapter.
    """
    lines = text.split("\n")
    chapters: List[Dict[str, Any]] = []
    in_fence = False

    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        if line.startswith("## ") and not line.startswith("### "):
            title, anchor = _strip_anchor(line[3:])
            n = len(chapters) + 1
            chapters.append({
                "n": n,
                "anchor": anchor or f"ch-{n}",
                "title": title,
                "start": i,
                "sections": [],
            })
        elif line.startswith("### ") and chapters:
            title, anchor = _strip_anchor(line[4:])
            ch = chapters[-1]
            m = len(ch["sections"]) + 1
            ch["sections"].append({
                "n": f"{ch['n']}.{m}",
                "anchor": anchor or f"{ch['anchor']}-{m}",
                "title": title,
                "start": i,
            })

    # Close every range, then attach the raw text.
    for idx, ch in enumerate(chapters):
        ch["end"] = chapters[idx + 1]["start"] - 1 if idx + 1 < len(chapters) else len(lines) - 1
        for sidx, sec in enumerate(ch["sections"]):
            sec["end"] = (ch["sections"][sidx + 1]["start"] - 1
                          if sidx + 1 < len(ch["sections"]) else ch["end"])
            sec["lines"] = lines[sec["start"]:sec["end"] + 1]
        ch["lines"] = lines[ch["start"]:ch["end"] + 1]
        ch["summary"] = _first_prose(ch["lines"][1:])

    return chapters


def _first_prose(lines: List[str], limit: int = 140) -> str:
    """The chapter's own one-line pitch: first real sentence, not a table or callout."""
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        s = line.strip()
        if in_fence or not s:
            continue
        if s.startswith(("#", ">", "|", "-", "*", "---")):
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        return s if len(s) <= limit else s[: limit - 1] + "…"
    return ""


def chapter_text(ch: Dict[str, Any]) -> str:
    return "\n".join(ch["lines"]).strip() + "\n"


def find_chapter(chapters: List[Dict[str, Any]], ref: str) -> Optional[Dict[str, Any]]:
    """Resolve a chapter by number, anchor, section anchor, or fuzzy title."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.isdigit():
        n = int(ref)
        return next((c for c in chapters if c["n"] == n), None)
    low = ref.casefold()
    for c in chapters:
        if c["anchor"].casefold() == low:
            return c
    for c in chapters:  # a section anchor resolves to its chapter
        if any(s["anchor"].casefold() == low for s in c["sections"]):
            return c
    for c in chapters:
        if low in c["title"].casefold():
            return c
    return None


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------

def _commands_in(lines: List[str]) -> List[str]:
    """Runnable commands mentioned in a block — fenced lines and inline code."""
    found: List[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            cmd = line.split("#")[0].strip()
            if cmd.split(" ")[0] in _CMD_TOOLS and len(cmd.split()) > 1:
                found.append(cmd)
            continue
        for code in _INLINE_CODE_RE.findall(line):
            code = code.strip()
            if code.split(" ")[0] in _CMD_TOOLS and len(code.split()) > 1:
                found.append(code)
    # de-dup, keep order
    seen = set()
    out = []
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def search_guide(chapters: List[Dict[str, Any]], query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Substring search over sections. Case- and width-insensitive enough for
    error strings pasted straight out of a terminal."""
    q = (query or "").strip().casefold()
    if not q:
        return []

    hits: List[Dict[str, Any]] = []
    for ch in chapters:
        blocks = ch["sections"] or [{
            "n": str(ch["n"]), "anchor": ch["anchor"], "title": ch["title"],
            "lines": ch["lines"], "start": ch["start"],
        }]
        for blk in blocks:
            matched = [(blk["start"] + i + 1, ln.strip())
                       for i, ln in enumerate(blk["lines"]) if q in ln.casefold()]
            if not matched:
                continue
            hits.append({
                "chapter": ch["title"],
                "chapter_n": ch["n"],
                "chapter_anchor": ch["anchor"],
                "section": blk["title"],
                "section_n": blk["n"],
                "anchor": blk["anchor"],
                "match_count": len(matched),
                "matches": [{"line": n, "text": t} for n, t in matched[:3]],
                "commands": _commands_in(blk["lines"])[:6],
            })
    hits.sort(key=lambda h: h["match_count"], reverse=True)
    return hits[:limit]


# --------------------------------------------------------------------------
# Troubleshooting index (derived, never hand-maintained)
# --------------------------------------------------------------------------

def _split_row(line: str) -> List[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _clean(cell: str) -> str:
    cell = re.sub(r"\*\*(.+?)\*\*", r"\1", cell)
    return cell.strip()


def symptom_index(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every symptom→fix pair in the manual, from its tables and [!FIX] callouts.

    The manual is the source of truth; this walks it on every call so a new
    row in a table is a new entry here with no extra step.
    """
    out: List[Dict[str, Any]] = []

    for ch in chapters:
        lines = ch["lines"]
        in_fence = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                i += 1
                continue
            if in_fence:
                i += 1
                continue

            # --- symptom tables -------------------------------------------
            if line.strip().startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
                header = _split_row(line)
                if header and any(h in _clean(header[0]).casefold() for h in _SYMPTOM_HEADERS):
                    j = i + 2
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        cells = [_clean(c) for c in _split_row(lines[j])]
                        if len(cells) >= 2 and cells[0]:
                            entry = {
                                "symptom": cells[0],
                                "cause": cells[1] if len(cells) >= 3 else "",
                                "fix": cells[-1],
                                "chapter": ch["title"],
                                "chapter_n": ch["n"],
                                "anchor": ch["anchor"],
                                "source": "table",
                            }
                            entry["commands"] = _commands_in([entry["fix"], entry["cause"]])
                            out.append(entry)
                        j += 1
                    i = j
                    continue

            # --- [!FIX] callouts ------------------------------------------
            m = _CALLOUT_RE.match(line)
            if m and m.group(1) == "FIX":
                block = [m.group(2)]
                j = i + 1
                while j < len(lines) and lines[j].startswith(">"):
                    block.append(lines[j][1:].strip())
                    j += 1
                for item in _callout_items(block):
                    entry = {
                        "symptom": item[0],
                        "cause": "",
                        "fix": item[1],
                        "chapter": ch["title"],
                        "chapter_n": ch["n"],
                        "anchor": ch["anchor"],
                        "source": "callout",
                    }
                    entry["commands"] = _commands_in([item[1]])
                    out.append(entry)
                i = j
                continue

            i += 1

    return out


def _callout_items(block: List[str]) -> List[Tuple[str, str]]:
    """A [!FIX] callout is either a bullet list of symptom/fix pairs or one
    paragraph. Split each bullet at the first colon; keep the rest verbatim."""
    items: List[Tuple[str, str]] = []
    current: Optional[str] = None
    for raw in block:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("- ") or s.startswith("* "):
            if current:
                items.append(_split_symptom(current))
            current = s[2:].strip()
        elif current is not None:
            current += " " + s
        else:
            current = s
    if current:
        items.append(_split_symptom(current))
    return [it for it in items if it[0]]


def _split_symptom(text: str) -> Tuple[str, str]:
    text = _clean(text)
    for sep in ("：", ": "):
        if sep in text:
            head, tail = text.split(sep, 1)
            if len(head) <= 120:
                return head.strip(), tail.strip()
    return (text[:120].strip(), text.strip())


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _emit_markdown(md: str, plain: bool) -> None:
    """Terminals get a rendered read; pipes and agents get raw markdown."""
    if plain or not sys.stdout.isatty():
        print(md)
        return
    try:
        from rich.console import Console
        from rich.markdown import Markdown

        Console().print(Markdown(md))
    except Exception:
        print(md)


def _print_chapter_list(chapters: List[Dict[str, Any]], lang: str, plain: bool) -> None:
    header = f"magi guide ({lang}) — {len(chapters)} chapters\n"
    rows = []
    for ch in chapters:
        rows.append(f"  {ch['n']:>2}  {ch['anchor']:<14} {ch['title']}")
        if ch["summary"]:
            rows.append(f"      {ch['summary']}")
    tail = ("\nRead one:      magi guide <number|anchor>\n"
            "Search:        magi guide --search \"<error text>\"\n"
            "Symptom index: magi guide --symptoms\n")
    print(header + "\n".join(rows) + "\n" + tail)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi guide",
        description="Read the built-in MAGI operating manual: chapters, full-text "
                    "search, and a symptom-to-fix index. Designed to be read by "
                    "people in a terminal and by agents with --json.")
    parser.add_argument("chapter", nargs="?", default=None,
                        help="Chapter number, anchor (e.g. 'ingest'), or part of its title. "
                             "Omit to list all chapters.")
    parser.add_argument("--search", "-s", default=None,
                        help="Find sections containing this text (paste an error message here).")
    parser.add_argument("--symptoms", action="store_true",
                        help="Dump the symptom -> cause -> fix index built from the manual.")
    parser.add_argument("--all", action="store_true", help="Print the whole manual.")
    parser.add_argument("--lang", choices=list(LANGS), default=None,
                        help="Language (default: zh; falls back to whichever ships).")
    parser.add_argument("--limit", type=int, default=8, help="Max search hits (default: 8).")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    parser.add_argument("--plain", action="store_true",
                        help="Raw markdown instead of terminal rendering.")
    args = parser.parse_args(argv)

    text, lang = load_guide(args.lang)
    if not text:
        payload = {"error": "guide not found in this installation",
                   "hint": "reinstall magi: pipx upgrade --install magi-research "
                           "(or uv tool install --force magi-research)"}
        print(json.dumps(payload, ensure_ascii=False) if args.json
              else f"error: {payload['error']} — {payload['hint']}", file=sys.stderr if not args.json else sys.stdout)
        return 1

    chapters = parse_chapters(text)

    if args.all:
        if args.json:
            print(json.dumps({"lang": lang, "content": text}, ensure_ascii=False))
        else:
            _emit_markdown(text, args.plain)
        return 0

    if args.symptoms:
        index = symptom_index(chapters)
        if args.search:
            q = args.search.casefold()
            index = [e for e in index
                     if q in e["symptom"].casefold() or q in e["fix"].casefold()]
        if args.json:
            print(json.dumps({"lang": lang, "count": len(index), "symptoms": index},
                             ensure_ascii=False))
            return 0 if index else 1
        if not index:
            print("no matching symptom in the manual")
            return 1
        for e in index:
            print(f"[{e['chapter_n']:>2} {e['anchor']}] {e['symptom']}")
            if e["cause"]:
                print(f"     cause: {e['cause']}")
            print(f"     fix:   {e['fix']}")
            for c in e["commands"][:3]:
                print(f"     $ {c}")
            print()
        return 0

    if args.search:
        hits = search_guide(chapters, args.search, args.limit)
        if args.json:
            print(json.dumps({"lang": lang, "query": args.search, "count": len(hits),
                              "hits": hits}, ensure_ascii=False))
            return 0 if hits else 1
        if not hits:
            print(f"no section mentions {args.search!r}\n"
                  f"try: magi guide --symptoms | magi guide --list")
            return 1
        for h in hits:
            print(f"[{h['section_n']:>4}] {h['chapter']} › {h['section']}   (magi guide {h['chapter_anchor']})")
            for m in h["matches"]:
                print(f"       {m['text']}")
            for c in h["commands"][:3]:
                print(f"       $ {c}")
            print()
        return 0

    if args.chapter:
        ch = find_chapter(chapters, args.chapter)
        if ch is None:
            msg = {"error": f"no chapter matching {args.chapter!r}",
                   "chapters": [{"n": c["n"], "anchor": c["anchor"], "title": c["title"]}
                                for c in chapters]}
            if args.json:
                print(json.dumps(msg, ensure_ascii=False))
            else:
                print(f"error: {msg['error']}")
                print("available: " + ", ".join(c["anchor"] for c in chapters))
            return 1
        if args.json:
            print(json.dumps({
                "lang": lang,
                "n": ch["n"], "anchor": ch["anchor"], "title": ch["title"],
                "summary": ch["summary"],
                "sections": [{"n": s["n"], "anchor": s["anchor"], "title": s["title"]}
                             for s in ch["sections"]],
                "commands": _commands_in(ch["lines"]),
                "content": chapter_text(ch),
            }, ensure_ascii=False))
        else:
            _emit_markdown(chapter_text(ch), args.plain)
        return 0

    if args.json:
        print(json.dumps({
            "lang": lang,
            "available_langs": available_langs(),
            "chapters": [{"n": c["n"], "anchor": c["anchor"], "title": c["title"],
                          "summary": c["summary"],
                          "sections": [{"n": s["n"], "anchor": s["anchor"], "title": s["title"]}
                                       for s in c["sections"]]}
                         for c in chapters],
        }, ensure_ascii=False))
    else:
        _print_chapter_list(chapters, lang, args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
