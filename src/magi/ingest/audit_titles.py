r"""`magi ingest audit-titles` — which cards a bad extraction damaged.

A title extractor that got it wrong does not leave a broken file. It leaves a
plausible one: a paper filed under "Abstract", or under a title cut at a word
boundary so it still reads like a title. On a real 37-paper library, 13 of the
committed cards were wrong and nothing in the project could tell.

They can be found without re-fetching anything, and this is the whole idea:
`output/ingest/batch-*.jsonl` records the title *as extracted*, and that
directory is in the never-rebuilt set. So the ledger is a snapshot of what the
extractor said at the time, and the card is what is there now. Where they
disagree, one of them has been edited — by a person correcting it, or by
nothing at all, which is the case worth finding.

What this does not do is decide who is right. It has no network and no
authority; it names the pairs and leaves the judgement where it belongs. The
suggested check is one batched arXiv API call, which is what the person who
found this did by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


def card_title(path: Path) -> str | None:
    """The `title:` a committed card carries, or None if it has none."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    end = head.find("\n---", 3)
    m = _FRONTMATTER_TITLE_RE.search(head[:end if end > 0 else len(head)])
    if not m:
        return None
    return m.group(1).strip().strip("'\"")


def _ledger_titles(topic: Path) -> dict[str, dict]:
    """`{arxiv_id: {title, committed_path}}` from every batch ever run.

    Later batches win: a paper re-ingested after a fix should be judged on the
    run that produced the card sitting there now.
    """
    out: dict[str, dict] = {}
    ledger_dir = topic / "output" / "ingest"
    for path in sorted(ledger_dir.glob("batch-*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("kind") != "item":
                continue
            aid = rec.get("arxiv_id") or rec.get("source_value")
            if not aid:
                continue
            out[str(aid)] = {"title": rec.get("title"),
                             "committed_path": rec.get("committed_path"),
                             "batch": path.name}
    return out


_CARD_ARXIV_RE = re.compile(r"^arxiv_id:\s*['\"]?([^'\"\n]+)", re.MULTILINE)


def _cards_by_arxiv_id(topic: Path) -> dict[str, tuple[Path, str]]:
    """`{arxiv_id: (path, title)}` for every committed source card.

    Matched on the id rather than on a path from the ledger: `committed_path`
    is not recorded on an item, so joining on it found nothing at all and
    reported a clean library — the precise false answer this command exists to
    avoid giving.
    """
    out: dict[str, tuple[Path, str]] = {}
    for card in sorted((topic / "raw").rglob("*.md")):
        if card.name == "_index.md":
            continue
        try:
            head = card.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        m = _CARD_ARXIV_RE.search(head)
        title = card_title(card)
        if m and title:
            out[m.group(1).strip()] = (card, title)
    return out


def _same_title(a: str, b: str) -> bool:
    """Two titles that differ only in wrapping or quoting are the same title.

    The ledger sometimes stores a title with its quotes included while the
    card's frontmatter has them stripped. Reporting that pair would put a
    formatting artifact in a list whose whole value is that every row means
    something.
    """
    def norm(s: str) -> str:
        return " ".join(s.split()).strip("'\"").strip()

    return norm(a) == norm(b)


def disagreements(topic: Path) -> list[dict]:
    """Cards whose title differs from what the extractor recorded.

    Whitespace is normalised before comparing — a difference in wrapping is
    not a difference in the title, and reporting one would bury the real ones.
    """
    cards = _cards_by_arxiv_id(topic)
    found = []
    for aid, rec in sorted(_ledger_titles(topic).items()):
        was = rec.get("title")
        if not was or aid not in cards:
            continue
        card, now = cards[aid]
        if _same_title(str(was), now):
            continue
        found.append({"arxiv_id": aid, "extracted": str(was), "on_disk": now,
                      "path": str(card), "batch": rec["batch"]})
    return found


def cmd_audit_titles(args) -> int:
    from magi.core.workspace import find_workspace_root

    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no project found (run inside one, or pass --project-dir)", file=sys.stderr)
        return 1
    topic = Path(topic)

    ledger = _ledger_titles(topic)
    if not ledger:
        print("no ingest ledger here — nothing has been ingested through a batch")
        return 0

    found = disagreements(topic)
    if args.json:
        print(json.dumps({"checked": len(ledger), "disagreements": found},
                         indent=2, ensure_ascii=False))
        return 0

    print(f"checked {len(ledger)} ingested paper(s) against what the extractor recorded")
    if not found:
        print("every card still carries the title it was filed with.")
        print("\nThat is not the same as every title being right — it means "
              "nothing has been\nedited since. To check them against the source, "
              "ask arXiv in one call:")
        print(f"  http://export.arxiv.org/api/query?id_list="
              f"{','.join(list(ledger)[:20])}")
        return 0

    print(f"\n{len(found)} card(s) no longer match the extracted title:\n")
    for row in found:
        print(f"  {row['arxiv_id']}")
        print(f"    extracted: {row['extracted'][:88]}")
        print(f"    on disk  : {row['on_disk'][:88]}")
    print("\nA difference means somebody corrected it, which is worth knowing: the "
          "\nfilename was built from the title at commit time and is never "
          "regenerated,\nso those cards still carry the old slug. `magi ingest "
          "audit-titles --json`\ngives the paths.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest audit-titles", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir",
                        help="Project root (default: discovered)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    return cmd_audit_titles(args)


if __name__ == "__main__":
    sys.exit(main())
