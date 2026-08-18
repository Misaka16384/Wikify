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


def _ellipsize(text: str, budget: int) -> str:
    """Truncate at the last whitespace within *budget* and append an ellipsis."""
    if len(text) <= budget:
        return text
    cut = text[:budget]
    ws = max(cut.rfind(" "), cut.rfind("\n"), cut.rfind("\t"))
    if ws > 0:
        cut = cut[:ws]
    return cut.rstrip() + "…"


def _numbered_path(path: Path) -> Path:
    """Return *path* if free, else the first numbered sibling (-2, -3, ...)."""
    if not path.exists():
        return path
    n = 2
    while True:
        cand = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not cand.exists():
            return cand
        n += 1


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
        title = (p.get("title") or "").strip()
        # Drop metadata-broken records (no title, or nothing but a title
        # fragment) — they cannot be triaged and pollute the digest.
        if not title:
            continue
        if not p.get("year") and not p.get("abstract") and not ext:
            continue
        out.append({
            "id": ext.get("ArXiv") or ext.get("DOI") or p.get("paperId"),
            "arxiv_id": ext.get("ArXiv"),
            "doi": ext.get("DOI"),
            "title": title,
            "year": p.get("year"),
            "abstract": (p.get("abstract") or "")[:1500],
            "url": p.get("url"),
            "source": "s2-recommendation",
        })
    return out


def harvest_arxiv(categories: list[str], days: int,
                  per_cat: int = 30) -> tuple[list[dict], list[str]]:
    """Returns (candidates, failed_category_names)."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out: list[dict] = []
    failed: list[str] = []
    for i, cat in enumerate(categories):
        if i:
            time.sleep(3)  # arXiv politeness: 1 request / 3 s
        q = urllib.parse.quote(f"cat:{cat}")
        url = (f"https://export.arxiv.org/api/query?search_query={q}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={per_cat}")
        feed = None
        for attempt in range(2):
            try:
                feed = _http_text(url)
                break
            except Exception as exc:
                if attempt == 0:
                    print(f"warning: arXiv query failed for {cat}: {exc} — retrying in 5s",
                          file=sys.stderr)
                    time.sleep(5)
                else:
                    print(f"warning: arXiv query failed for {cat} after retry: {exc}",
                          file=sys.stderr)
                    failed.append(cat)
        if feed is None:
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
    return out, failed


# --------------------------------------------------------------------------
# relevance scoring: cosine(candidate embedding, library centroid)
# --------------------------------------------------------------------------

def _score_candidates(topic: Path, cands: list[dict]) -> bool:
    """Attach c['score'] to each candidate: cosine similarity between the
    candidate's title+abstract embedding and the centroid of the library's
    own wiki chunk embeddings. Returns True when at least one candidate got
    scored (requires a vectorized index.db and a reachable Ollama)."""
    idx = topic / "output" / "index.db"
    if not idx.is_file() or not cands:
        return False
    try:
        import numpy as np

        from magi.retrieval import Embedder, open_db

        opened = open_db(idx)
        if not opened:
            return False
        conn, vec_loaded = opened
        try:
            if not vec_loaded:
                return False
            rows = conn.execute(
                "SELECT v.embedding FROM chunks_vec v JOIN chunks c ON c.id = v.rowid "
                "WHERE c.collection IN ('concepts', 'references', 'topics', 'theses') "
                "LIMIT 400"
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return False
        mat = np.array([np.frombuffer(r[0], dtype=np.float32) for r in rows])
        centroid = mat.mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm == 0:
            return False
        centroid = centroid / norm

        emb = Embedder()
        scored_any = False
        for c in cands:
            text = f"{c.get('title') or ''}\n{(c.get('abstract') or '')[:800]}".strip()
            if not text:
                continue
            vec = emb.embed(text)
            if vec is None:
                break  # Ollama went away — keep whatever we scored so far
            v = np.asarray(vec, dtype=np.float32)
            if v.shape != centroid.shape:
                return False  # index built with a different embedding model
            vn = float(np.linalg.norm(v))
            if vn:
                c["score"] = round(float(np.dot(centroid, v / vn)), 3)
                scored_any = True
        return scored_any
    except Exception as exc:
        print(f"warning: relevance scoring skipped ({exc})", file=sys.stderr)
        return False


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
    print("[radar] harvesting S2 recommendations...", file=sys.stderr)
    s2_cands = harvest_s2(seeds, limit=max(max_c // 2, 10))
    print(f"[radar] harvesting arXiv listings ({len(categories)} categories)...", file=sys.stderr)
    arxiv_cands, failed_sources = harvest_arxiv(categories, days)
    candidates = s2_cands + arxiv_cands

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

    # Score against the library fingerprint BEFORE the cap so the budget is
    # spent on the most relevant candidates, not on listing order.
    print("[radar] scoring candidates against library embedding centroid...", file=sys.stderr)
    scored = _score_candidates(topic, fresh)
    if scored:
        min_rel = cfg_get(cfg, "radar.min_relevance", None)
        if min_rel is not None:
            before = len(fresh)
            fresh = [c for c in fresh if c.get("score") is None or c["score"] >= float(min_rel)]
            dropped = before - len(fresh)
            if dropped:
                print(f"[radar] dropped {dropped} candidate(s) below radar.min_relevance={min_rel}",
                      file=sys.stderr)
        fresh.sort(key=lambda c: c.get("score", -1.0), reverse=True)
    else:
        print("[radar] relevance scoring unavailable (needs vectorized index + Ollama) — "
              "digest keeps source order", file=sys.stderr)
    fresh = fresh[:max_c]

    today = dt.date.today().isoformat()
    # candidates.jsonl is a cumulative log of harvested candidates — append,
    # never truncate (the per-digest list lives in the digest itself).
    with open(radar_dir / "candidates.jsonl", "a", encoding="utf-8") as f:
        for c in fresh:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(ledger_path, "a", encoding="utf-8") as f:
        for c in fresh:
            f.write(json.dumps({"id": c["id"], "first_seen": today, "source": c["source"]},
                               ensure_ascii=False) + "\n")

    if failed_sources:
        print(f"warning: some sources failed this harvest: {', '.join(failed_sources)}",
              file=sys.stderr)
    if fresh:
        digest_dir = topic / "inbox" / "radar"
        digest_dir.mkdir(parents=True, exist_ok=True)
        # Never overwrite an existing digest (it may hold a reviewed tally) —
        # a same-day re-harvest gets a numbered sibling instead.
        digest = _numbered_path(digest_dir / f"{today}-digest.md")
        lines = [
            "---",
            f"title: \"Radar digest {today}\"",
            "type: radar-digest",
            "status: pending-review",
            f"candidates: {len(fresh)}",
        ]
        if failed_sources:
            lines.append(f"sources_failed: [{', '.join(failed_sources)}]")
        lines += [
            "---",
            "",
            f"# Literature Radar — {today}",
            "",
            f"{len(fresh)} new candidates. Triage with the **radar_review** skill:",
            "score each against the wiki, file `bd` issues (type: survey) for keepers,",
            "then set `status: reviewed` in this file's frontmatter.",
            "",
        ]
        if scored:
            lines.append("_Sorted by relevance to this library (embedding cosine vs. wiki centroid)._")
            lines.append("")
        for c in fresh:
            arxiv_link = f"https://arxiv.org/abs/{c['arxiv_id']}" if c.get("arxiv_id") else ""
            link = c.get("url") or arxiv_link
            lines.append(f"## {c['title']}")
            lines.append("")
            meta = f"- id: `{c['id']}` · {c.get('year', '?')} · source: {c['source']}"
            if c.get("score") is not None:
                meta += f" · relevance: {c['score']}"
            lines.append(meta)
            if link:
                lines.append(f"- {link}")
            if arxiv_link and arxiv_link != link:
                lines.append(f"- {arxiv_link}")
            if c.get("abstract"):
                lines.append(f"- abstract: {_ellipsize(c['abstract'], 500)}")
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
    own_meta: dict[str, dict] = {}
    for own in own_ids:
        pid = f"ArXiv:{own}"
        try:
            meta = _s2_get(f"{base}/{pid}?fields=title,abstract")
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: S2 metadata lookup failed for {own}: {exc}", file=sys.stderr)
            meta = {}
        own_meta[own] = {"title": (meta.get("title") or "").strip(),
                        "abstract": meta.get("abstract") or ""}
        try:
            refs = _s2_get(f"{base}/{pid}/references?fields=paperId,title&limit=200")
            time.sleep(1.1)
            cits = _s2_get(f"{base}/{pid}/citations?fields=paperId&limit=500")
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: S2 lookup failed for {own}: {exc}", file=sys.stderr)
            continue
        ref_titles: dict[str, str] = {}
        for row in refs.get("data", []) or []:
            p = row.get("citedPaper") or {}
            if p.get("paperId"):
                ref_titles[p["paperId"]] = (p.get("title") or "").strip()
        my_refs = set(ref_titles)
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

        neighbors = recs.get("recommendedPapers", []) or []
        print(f"[radar] anchor {own}: refs={len(my_refs)} citers={len(citers)}, "
              f"scanning {len(neighbors)} neighbors...", file=sys.stderr)
        checked = 0
        for cand in neighbors:
            cand_pid = cand.get("paperId")
            if not cand_pid or cand_pid in citers:
                continue  # layer 2: already cites us
            if (cand.get("year") or 0) < year_cut:
                continue  # layer 3: too old to act on
            if checked >= 20:
                break  # request-budget cap per own paper
            checked += 1
            print(f"[radar]   neighbor {checked}/20: {(cand.get('title') or '')[:60]}",
                  file=sys.stderr)
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
                "shared_ref_titles": sorted(t for t in (ref_titles[s] for s in shared) if t)[:5],
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
        for own in own_ids:
            meta = own_meta.get(own) or {}
            if not (meta.get("title") or meta.get("abstract")):
                continue
            lines.append(f"## Our paper: {meta.get('title') or 'arXiv:' + own} (arXiv:{own})")
            lines.append("")
            if meta.get("abstract"):
                lines.append(_ellipsize(meta["abstract"], 400))
            lines.append("")
        for f_ in findings:
            lines.append(f"## {f_['candidate_title']}")
            lines.append("")
            lines.append(f"- should arguably cite: our arXiv:{f_['own_paper']}")
            lines.append(f"- candidate: {f_['year']} · arXiv:{f_['candidate_arxiv'] or '?'} · "
                         f"shared refs: {f_['shared_refs']}")
            titles = f_.get("shared_ref_titles") or []
            if titles:
                lines.append("- shared references include: " + "; ".join(titles))
            if f_.get("url"):
                lines.append(f"- {f_['url']}")
            if f_.get("abstract"):
                lines.append(f"- abstract: {_ellipsize(f_['abstract'], 400)}")
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
    gap_pending = []
    failed_sources = None
    digest_dir = topic / "inbox" / "radar"
    if digest_dir.is_dir():
        digests = sorted(digest_dir.glob("*-digest*.md"))
        for p in digests:
            try:
                if "status: pending-review" in p.read_text(encoding="utf-8"):
                    pending.append(p.name)
            except OSError:
                continue
        for p in sorted(digest_dir.glob("*-citation-gaps.md")):
            try:
                if "status: pending-review" in p.read_text(encoding="utf-8"):
                    gap_pending.append(p.name)
            except OSError:
                continue
        if digests:
            newest = max(digests, key=lambda p: p.stat().st_mtime)
            try:
                m = re.search(r"^sources_failed:\s*\[([^\]]*)\]",
                              newest.read_text(encoding="utf-8"), re.MULTILINE)
                if m:
                    failed_sources = m.group(1).strip()
            except OSError:
                pass
    payload = {"seen_total": len(ledger), "pending_digests": pending,
               "pending_citation_gaps": gap_pending,
               "last_digest_failed_sources": failed_sources}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"radar: {len(ledger)} papers seen · {len(pending)} digest(s) pending review"
              + (f" · {len(gap_pending)} citation-gap report(s) pending" if gap_pending else ""))
        for name in pending + gap_pending:
            print(f"  -> inbox/radar/{name}")
        if failed_sources:
            print(f"  warning: last digest had failed sources: {failed_sources}")
    return 0


def _schedule_names(topic: Path) -> tuple[str, str]:
    """(task_name, launchd_label) — a short hash of the full path avoids
    collisions between topics that share a directory basename."""
    import hashlib
    h = hashlib.sha1(str(topic).encode("utf-8")).hexdigest()[:6]
    return f"magi-radar-{topic.name}-{h}", f"com.magi.radar.{topic.name}.{h}"


def cmd_install_schedule(args: argparse.Namespace) -> int:
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    import shutil
    import subprocess

    task_name, label = _schedule_names(topic)
    if getattr(args, "uninstall", False):
        if sys.platform == "win32":
            proc = subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"],
                                  capture_output=True, text=True)
            if proc.returncode == 0:
                print(f"Removed task {task_name}.")
            else:
                print(proc.stdout.strip() or proc.stderr.strip(), file=sys.stderr)
            return proc.returncode
        elif sys.platform == "darwin":
            dest = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            subprocess.run(["launchctl", "unload", str(dest)], capture_output=True)
            if dest.exists():
                dest.unlink()
                print(f"Removed launchd agent {label} ({dest}).")
            else:
                print(f"no launchd agent found at {dest}", file=sys.stderr)
                return 1
            return 0
        else:
            print("remove the harvest line from your crontab manually (crontab -e)")
            return 0

    magi_exe = shutil.which("magi")
    if not magi_exe:
        print("magi not found on PATH — install with 'uv tool install .' first", file=sys.stderr)
        return 1
    if sys.platform == "win32":
        cmd = ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", args.time,
               "/TN", task_name,
               "/TR", f'"{magi_exe}" radar harvest --topic-dir "{topic}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"Registered task {task_name} (daily {args.time}). "
                  f"Remove with: magi radar install-schedule --uninstall")
        else:
            print(proc.stdout.strip() or proc.stderr.strip(), file=sys.stderr)
        return proc.returncode
    elif sys.platform == "darwin":
        hh, mm = args.time.split(":")
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>
    <string>{magi_exe}</string><string>radar</string><string>harvest</string>
    <string>--topic-dir</string><string>{topic}</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>{int(hh)}</integer><key>Minute</key><integer>{int(mm)}</integer>
  </dict>
</dict></plist>
"""
        dest = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(plist, encoding="utf-8")
        subprocess.run(["launchctl", "load", str(dest)], capture_output=True)
        print(f"Registered launchd agent {label} (daily {args.time}): {dest}. "
              f"Remove with: magi radar install-schedule --uninstall")
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
    p_i.add_argument("--uninstall", action="store_true",
                     help="Remove the scheduled task/agent instead of creating it")
    p_i.set_defaults(func=cmd_install_schedule)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
