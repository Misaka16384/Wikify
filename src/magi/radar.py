"""magi radar — literature radar (feature A: discovery of relevant new papers).

Deterministic harvest, designed for unattended scheduled runs:

1. **Fingerprint**: seed arXiv IDs = ``radar.seed_arxiv_ids`` from config
   + every arXiv ID found in ``wiki/references/*.md`` (frontmatter or body).
2. **Harvest**:
   - Semantic Scholar Recommendations API (multi-seed, server-side ranking)
   - arXiv API recent listings for ``radar.arxiv_categories``
3. **Dedupe** against the cumulative ledger ``output/radar/seen.jsonl``
   and against the library's own papers.
4. **Output**: ``output/radar/candidates.jsonl`` (machine) and
   ``inbox/radar/YYYY-MM-DD-digest.md`` (human/agent digest).

Judgment (triage) is NOT done here — the radar_review skill reads the
digest in the next agent session, scores candidates against the wiki,
and files bd issues (type: survey) for papers worth reading.

Config (config.yaml):
    radar:
      arxiv_categories: [cond-mat.str-el, hep-th]
      seed_arxiv_ids: ["2606.25340", ...]
      days: 7          # arXiv recency window
      max_candidates: 40
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from magi.core.config_loader import load_config, get as cfg_get
from magi.core.workspace import find_workspace_root

ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b")
USER_AGENT = "magi-radar/0.1 (research workspace tool)"


def _http_json(url: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _http_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# fingerprint
# --------------------------------------------------------------------------

def library_arxiv_ids(topic: Path) -> set[str]:
    """arXiv IDs referenced anywhere in wiki/references cards."""
    ids: set[str] = set()
    refs = topic / "wiki" / "references"
    if refs.is_dir():
        for p in refs.rglob("*.md"):
            if p.name == "_index.md":
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in ARXIV_ID_RE.finditer(text):
                ids.add(m.group(1))
    return ids


def seed_ids(topic: Path, cfg: dict) -> list[str]:
    seeds = [str(s) for s in (cfg_get(cfg, "radar.seed_arxiv_ids", None) or [])]
    lib = sorted(library_arxiv_ids(topic))
    # config seeds first, then library papers; S2 caps positivePaperIds, keep it sane
    merged = list(dict.fromkeys(seeds + lib))
    return merged[:50]


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------

def harvest_s2(seeds: list[str], limit: int) -> list[dict]:
    if not seeds:
        return []
    url = ("https://api.semanticscholar.org/recommendations/v1/papers"
           f"?fields=title,externalIds,abstract,year,url&limit={limit}")
    body = {"positivePaperIds": [f"ArXiv:{s}" for s in seeds]}
    try:
        data = _http_json(url, body)
    except Exception as exc:
        print(f"warning: S2 recommendations failed: {exc}", file=sys.stderr)
        return []
    out = []
    for p in data.get("recommendedPapers", []) or []:
        ext = p.get("externalIds") or {}
        out.append({
            "id": ext.get("ArXiv") or ext.get("DOI") or p.get("paperId"),
            "arxiv_id": ext.get("ArXiv"),
            "doi": ext.get("DOI"),
            "title": (p.get("title") or "").strip(),
            "year": p.get("year"),
            "abstract": (p.get("abstract") or "")[:1500],
            "url": p.get("url"),
            "source": "s2-recommendation",
        })
    return out


def harvest_arxiv(categories: list[str], days: int, per_cat: int = 30) -> list[dict]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for i, cat in enumerate(categories):
        if i:
            time.sleep(3)  # arXiv politeness: 1 request / 3 s
        q = urllib.parse.quote(f"cat:{cat}")
        url = (f"https://export.arxiv.org/api/query?search_query={q}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={per_cat}")
        try:
            feed = _http_text(url)
        except Exception as exc:
            print(f"warning: arXiv query failed for {cat}: {exc}", file=sys.stderr)
            continue
        for entry in feed.split("<entry>")[1:]:
            aid = re.search(r"<id>https?://arxiv.org/abs/([^<]+)</id>", entry)
            title = re.search(r"<title>([^<]+)</title>", entry)
            pub = re.search(r"<published>([^<]+)</published>", entry)
            summary = re.search(r"<summary>([^<]+)</summary>", entry, re.DOTALL)
            if not (aid and title and pub):
                continue
            try:
                pub_dt = dt.datetime.fromisoformat(pub.group(1).replace("Z", "+00:00"))
            except ValueError:
                continue
            if pub_dt < cutoff:
                continue
            arxiv_id = re.sub(r"v\d+$", "", aid.group(1))
            out.append({
                "id": arxiv_id,
                "arxiv_id": arxiv_id,
                "doi": None,
                "title": re.sub(r"\s+", " ", title.group(1)).strip(),
                "year": pub_dt.year,
                "abstract": re.sub(r"\s+", " ", summary.group(1)).strip()[:1500] if summary else "",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "source": f"arxiv-new:{cat}",
                "published": pub_dt.date().isoformat(),
            })
    return out


# --------------------------------------------------------------------------
# harvest command
# --------------------------------------------------------------------------

def _load_ledger(path: Path) -> set[str]:
    seen: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def cmd_harvest(args: argparse.Namespace) -> int:
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    cfg = load_config()
    categories = [str(c) for c in (cfg_get(cfg, "radar.arxiv_categories", None) or [])]
    days = int(args.days or cfg_get(cfg, "radar.days", 7))
    max_c = int(cfg_get(cfg, "radar.max_candidates", 40))

    seeds = seed_ids(topic, cfg)
    lib_ids = library_arxiv_ids(topic)
    print(f"fingerprint: {len(seeds)} seeds ({len(lib_ids)} from library)")

    # Reserve roughly half the candidate budget for arXiv recency so S2
    # recommendations cannot crowd new listings out of the cap entirely.
    candidates = harvest_s2(seeds, limit=max(max_c // 2, 10)) + harvest_arxiv(categories, days)

    radar_dir = topic / "output" / "radar"
    radar_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = radar_dir / "seen.jsonl"
    seen = _load_ledger(ledger_path)

    fresh: list[dict] = []
    dedup: set[str] = set()
    for c in candidates:
        cid = c.get("id")
        if not cid or cid in seen or cid in dedup:
            continue
        if c.get("arxiv_id") and c["arxiv_id"] in lib_ids:
            continue  # already in the library
        dedup.add(cid)
        fresh.append(c)
    fresh = fresh[:max_c]

    today = dt.date.today().isoformat()
    (radar_dir / "candidates.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in fresh), encoding="utf-8")
    with open(ledger_path, "a", encoding="utf-8") as f:
        for c in fresh:
            f.write(json.dumps({"id": c["id"], "first_seen": today, "source": c["source"]},
                               ensure_ascii=False) + "\n")

    if fresh:
        digest_dir = topic / "inbox" / "radar"
        digest_dir.mkdir(parents=True, exist_ok=True)
        digest = digest_dir / f"{today}-digest.md"
        lines = [
            "---",
            f"title: \"Radar digest {today}\"",
            "type: radar-digest",
            "status: pending-review",
            f"candidates: {len(fresh)}",
            "---",
            "",
            f"# Literature Radar — {today}",
            "",
            f"{len(fresh)} new candidates. Triage with the **radar_review** skill:",
            "score each against the wiki, file `bd` issues (type: survey) for keepers,",
            "then set `status: reviewed` in this file's frontmatter.",
            "",
        ]
        for c in fresh:
            link = c.get("url") or (f"https://arxiv.org/abs/{c['arxiv_id']}" if c.get("arxiv_id") else "")
            lines.append(f"## {c['title']}")
            lines.append("")
            lines.append(f"- id: `{c['id']}` · {c.get('year', '?')} · source: {c['source']}")
            if link:
                lines.append(f"- {link}")
            if c.get("abstract"):
                lines.append(f"- abstract: {c['abstract'][:500]}")
            lines.append("")
        digest.write_text("\n".join(lines), encoding="utf-8")
        print(f"harvest: {len(fresh)} new candidates -> {digest}")
    else:
        print("harvest: no new candidates")
    return 0


# --------------------------------------------------------------------------
# feature B: citation-gap scout ("should cite us but didn't")
# --------------------------------------------------------------------------

def _s2_paper_ids(payload_rows: list[dict], key: str) -> set[str]:
    """Collect S2 paperIds (canonical) from citations/references rows."""
    out: set[str] = set()
    for row in payload_rows:
        p = row.get(key) or {}
        pid = p.get("paperId")
        if pid:
            out.add(pid)
    return out


def _s2_get(url: str, retries: int = 1) -> dict:
    for attempt in range(retries + 1):
        try:
            return _http_json(url)
        except Exception as exc:
            if attempt < retries and "429" in str(exc):
                time.sleep(5)
                continue
            raise
    return {}


def cmd_citation_gap(args: argparse.Namespace) -> int:
    """Four-layer funnel per own paper P (precision over recall — this is
    a SCOUT, its output is a human-review queue, not a verdict):
      1. candidates = S2 recommendations seeded on P (semantic neighbors)
      2. minus actual citers of P (S2 citations endpoint)
      3. recency window (default: last 2 years)
      4. co-citation signal: candidate shares >= min_shared references
         with P (they cite what we cite, but not us)
    Survivors go to inbox/radar/<date>-citation-gaps.md for LLM+human triage.
    """
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    cfg = load_config()
    own_ids = [str(s) for s in (cfg_get(cfg, "radar.own_arxiv_ids", None)
                                or cfg_get(cfg, "radar.seed_arxiv_ids", None) or [])]
    if args.paper:
        own_ids = [args.paper]
    if not own_ids:
        print("no own papers configured (radar.own_arxiv_ids in config.yaml)", file=sys.stderr)
        return 1
    min_shared = int(cfg_get(cfg, "radar.citation_gap.min_shared_refs", 2))
    years_back = int(cfg_get(cfg, "radar.citation_gap.years", 2))
    year_cut = dt.date.today().year - years_back
    base = "https://api.semanticscholar.org/graph/v1/paper"

    findings: list[dict] = []
    for own in own_ids:
        pid = f"ArXiv:{own}"
        try:
            refs = _s2_get(f"{base}/{pid}/references?fields=paperId&limit=200")
            time.sleep(1.1)
            cits = _s2_get(f"{base}/{pid}/citations?fields=paperId&limit=500")
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: S2 lookup failed for {own}: {exc}", file=sys.stderr)
            continue
        my_refs = _s2_paper_ids(refs.get("data", []) or [], "citedPaper")
        citers = _s2_paper_ids(cits.get("data", []) or [], "citingPaper")
        if not my_refs:
            print(f"note: {own} has no reference data on S2 yet — skipping", file=sys.stderr)
            continue

        url = (f"https://api.semanticscholar.org/recommendations/v1/papers"
               f"?fields=title,externalIds,abstract,year,url,paperId&limit=30")
        try:
            recs = _http_json(url, {"positivePaperIds": [pid]})
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: recommendations failed for {own}: {exc}", file=sys.stderr)
            continue

        checked = 0
        for cand in recs.get("recommendedPapers", []) or []:
            cand_pid = cand.get("paperId")
            if not cand_pid or cand_pid in citers:
                continue  # layer 2: already cites us
            if (cand.get("year") or 0) < year_cut:
                continue  # layer 3: too old to act on
            if checked >= 20:
                break  # request-budget cap per own paper
            checked += 1
            try:
                cand_refs = _s2_get(f"{base}/{cand_pid}/references?fields=paperId&limit=200")
                time.sleep(1.1)
            except Exception:
                continue
            shared = _s2_paper_ids(cand_refs.get("data", []) or [], "citedPaper") & my_refs
            if len(shared) < min_shared:
                continue  # layer 4: no co-citation signal
            findings.append({
                "own_paper": own,
                "candidate_title": (cand.get("title") or "").strip(),
                "candidate_arxiv": (cand.get("externalIds") or {}).get("ArXiv"),
                "candidate_s2": cand_pid,
                "year": cand.get("year"),
                "shared_refs": len(shared),
                "url": cand.get("url"),
                "abstract": (cand.get("abstract") or "")[:800],
            })

    radar_dir = topic / "output" / "radar"
    radar_dir.mkdir(parents=True, exist_ok=True)
    (radar_dir / "citation-gaps.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in findings), encoding="utf-8")

    today = dt.date.today().isoformat()
    if findings:
        digest_dir = topic / "inbox" / "radar"
        digest_dir.mkdir(parents=True, exist_ok=True)
        out = digest_dir / f"{today}-citation-gaps.md"
        lines = [
            "---",
            f"title: \"Citation-gap scout {today}\"",
            "type: citation-gap-report",
            "status: pending-review",
            f"candidates: {len(findings)}",
            "---",
            "",
            f"# Citation-Gap Scout — {today}",
            "",
            "**This is a scout report, not a verdict.** Each candidate passed:",
            "semantic-neighbor ∧ not-citing-us ∧ recent ∧ shares "
            f">={min_shared} references with our paper. False positives are",
            "expected (survey-citing, scope limits, independent lines). Triage",
            "with the radar_review skill: judge the actual citation obligation",
            "from both abstracts + our claim cards, then file `bd create -t review`",
            "issues only for cases worth human follow-up.",
            "",
        ]
        for f_ in findings:
            lines.append(f"## {f_['candidate_title']}")
            lines.append("")
            lines.append(f"- should arguably cite: our arXiv:{f_['own_paper']}")
            lines.append(f"- candidate: {f_['year']} · arXiv:{f_['candidate_arxiv'] or '?'} · "
                         f"shared refs: {f_['shared_refs']}")
            if f_.get("url"):
                lines.append(f"- {f_['url']}")
            if f_.get("abstract"):
                lines.append(f"- abstract: {f_['abstract'][:400]}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"citation-gap: {len(findings)} candidates -> {out}")
    else:
        print("citation-gap: no candidates survived the funnel")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    radar_dir = topic / "output" / "radar"
    ledger = _load_ledger(radar_dir / "seen.jsonl")
    pending = []
    digest_dir = topic / "inbox" / "radar"
    if digest_dir.is_dir():
        for p in sorted(digest_dir.glob("*-digest.md")):
            try:
                if "status: pending-review" in p.read_text(encoding="utf-8"):
                    pending.append(p.name)
            except OSError:
                continue
    payload = {"seen_total": len(ledger), "pending_digests": pending}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"radar: {len(ledger)} papers seen · {len(pending)} digest(s) pending review")
        for name in pending:
            print(f"  -> inbox/radar/{name}")
    return 0


def cmd_install_schedule(args: argparse.Namespace) -> int:
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    import shutil
    import subprocess

    magi_exe = shutil.which("magi")
    if not magi_exe:
        print("magi not found on PATH — install with 'uv tool install .' first", file=sys.stderr)
        return 1
    task_name = f"magi-radar-{topic.name}"
    if sys.platform == "win32":
        cmd = ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", args.time,
               "/TN", task_name,
               "/TR", f'"{magi_exe}" radar harvest --topic-dir "{topic}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        print(proc.stdout.strip() or proc.stderr.strip())
        return proc.returncode
    elif sys.platform == "darwin":
        hh, mm = args.time.split(":")
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.magi.radar.{topic.name}</string>
  <key>ProgramArguments</key><array>
    <string>{magi_exe}</string><string>radar</string><string>harvest</string>
    <string>--topic-dir</string><string>{topic}</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>{int(hh)}</integer><key>Minute</key><integer>{int(mm)}</integer>
  </dict>
</dict></plist>
"""
        dest = Path.home() / "Library" / "LaunchAgents" / f"com.magi.radar.{topic.name}.plist"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(plist, encoding="utf-8")
        subprocess.run(["launchctl", "load", str(dest)], capture_output=True)
        print(f"launchd agent installed: {dest}")
        return 0
    else:
        print(f"add to crontab: 0 3 * * * {magi_exe} radar harvest --topic-dir {topic}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi radar", description=__doc__)
    sub = parser.add_subparsers(dest="radar_command", required=True)

    p_h = sub.add_parser("harvest", help="Fetch + dedupe new paper candidates (deterministic)")
    p_h.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_h.add_argument("--days", type=int, help="arXiv recency window (default: config radar.days or 7)")
    p_h.set_defaults(func=cmd_harvest)

    p_cg = sub.add_parser("citation-gap",
                          help="Scout recent papers that arguably should cite ours but don't")
    p_cg.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_cg.add_argument("--paper", help="Single own arXiv id (default: config radar.own_arxiv_ids)")
    p_cg.set_defaults(func=cmd_citation_gap)

    p_s = sub.add_parser("status", help="Ledger size + pending digests")
    p_s.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_s.add_argument("--json", action="store_true")
    p_s.set_defaults(func=cmd_status)

    p_i = sub.add_parser("install-schedule", help="Register a daily harvest (Task Scheduler / launchd)")
    p_i.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_i.add_argument("--time", default="03:00", help="Daily run time HH:MM (default 03:00)")
    p_i.set_defaults(func=cmd_install_schedule)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
