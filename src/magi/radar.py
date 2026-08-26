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

# ARXIV_ID_RE is re-exported here so a test that patches radar.ARXIV_ID_RE keeps
# working. The local copy it replaced knew only the modern 2405.00208 form, so a
# library holding cond-mat/0506438 was invisible to both the seed list and the
# already-have dedup.
from magi.core.arxiv_id import ARXIV_ID_RE
from magi.core.config_loader import load_config, get as cfg_get
from magi.core.http import USER_AGENT, Throttle as _CoreThrottle
from magi.core.http import http_json as core_http_json
from magi.core.http import http_text as core_http_text
from magi.core.workspace import find_workspace_root

# Per own-paper cap on citation-gap neighbour lookups. Each one is a separate
# Semantic Scholar request behind ~1.1s of enforced politeness, so this bounds
# both a run's wall time and its share of an anonymous rate limit.
NEIGHBOR_BUDGET = 20


# radar already spaces its own requests: a bare time.sleep(3) between arXiv
# category queries and time.sleep(1.1) after each Semantic Scholar call. Letting
# the shared Throttle also space them would double every wait, so radar opts out
# and keeps its own timing byte-for-byte. Folding these sleeps into the Throttle
# is a deliberate follow-up, not a drive-by.
_NO_THROTTLE = _CoreThrottle({})


#: Only this host is ever sent the key. Deciding per host rather than per call
#: site is the whole safety property: `radar.py` talks to Semantic Scholar and
#: to arXiv through the same two helpers, and a key attached at the helper
#: without this check would be a key mailed to arxiv.org on every harvest.
S2_HOST = "api.semanticscholar.org"


def s2_api_key(cfg: dict | None = None) -> str:
    """The Semantic Scholar key, env var first.

    Same shape as `embedding.api_key`: `radar.s2_api_key_env` names a variable
    that wins when set, and the config value is the fallback. A key pasted into
    config.yaml is a key in a file people put in git, so the env var is offered
    first and named in the comment beside the field — but refusing to read the
    config at all would just push people to hardcode it somewhere worse.

    *cfg* is the workspace's config and is never loaded here. Loading it
    without a ``start=`` reads from the process working directory, and the key
    lives in the workspace being harvested — so a scheduled run, whose working
    directory is wherever the scheduler put it, would have quietly gone back to
    being unauthenticated. Without a cfg only the environment is consulted,
    which is the one source that does not depend on where the process stands.
    """
    import os

    cfg = cfg or {}
    env_name = cfg_get(cfg, "radar.s2_api_key_env", "SEMANTIC_SCHOLAR_API_KEY")
    if env_name:
        from_env = os.environ.get(str(env_name), "")
        if from_env.strip():
            return from_env.strip()
    return str(cfg_get(cfg, "radar.s2_api_key", "") or "").strip()


def _auth_headers(url: str, cfg: dict | None = None) -> dict | None:
    if urllib.parse.urlsplit(url).hostname != S2_HOST:
        return None
    key = s2_api_key(cfg)
    return {"x-api-key": key} if key else None


def _http_json(url: str, payload: dict | None = None, timeout: int = 60,
               cfg: dict | None = None) -> dict:
    return core_http_json(url, payload, timeout, throttle=_NO_THROTTLE,
                          headers=_auth_headers(url, cfg))


def _http_text(url: str, timeout: int = 60, cfg: dict | None = None) -> str:
    return core_http_text(url, timeout, throttle=_NO_THROTTLE,
                          headers=_auth_headers(url, cfg))


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

def harvest_s2(seeds: list[str], limit: int, cfg: dict | None = None) -> list[dict]:
    if not seeds:
        return []
    url = ("https://api.semanticscholar.org/recommendations/v1/papers"
           f"?fields=title,externalIds,abstract,year,url,authors&limit={limit}")
    body = {"positivePaperIds": [f"ArXiv:{s}" for s in seeds]}
    try:
        data = _http_json(url, body, cfg=cfg)
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
            "title": re.sub(r"\s+", " ", title),
            "year": p.get("year"),
            # arXiv abstracts already get collapsed in harvest_arxiv; S2's did
            # not, and a newline inside one is enough to make the digest
            # re-parse as an extra candidate.
            "abstract": re.sub(r"\s+", " ", (p.get("abstract") or "")).strip()[:1500],
            "url": p.get("url"),
            "source": "s2-recommendation",
            "authors": [a.get("name") for a in (p.get("authors") or []) if a.get("name")],
        })
    return out


def harvest_s2_bulk(queries: list[str], limit: int, years: str | None = None,
                    cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """Keyword search over the whole Semantic Scholar corpus. Returns (candidates, failed).

    The radar's other two legs can only ever see new things. S2's
    recommendations endpoint draws from a fixed 60-day window (`from=recent`,
    its default and the only useful value outside computer science), and the
    arXiv leg reads a rolling listing. So a paper published last year that is
    squarely on topic — the kind you find by realising six months late that a
    subfield exists — was structurally unreachable: no amount of running the
    radar would surface it, because neither source was ever looking there.

    `/paper/search/bulk` is the endpoint that looks. It takes a query and a
    year range rather than a recency window, returns up to 1000 per page, and
    is free on the same key (or none).

    Empty `queries` disables the leg. It is off by default because a query
    list is a statement about what you are looking for, and guessing one from
    the library would produce confident noise.
    """
    if not queries:
        return [], []
    out: list[dict] = []
    failed: list[str] = []
    per_query = max(1, limit // len(queries))
    for i, query in enumerate(queries):
        if i:
            time.sleep(1.1)     # same politeness the rest of the S2 calls keep
        params = {
            "query": query,
            "fields": "title,externalIds,abstract,year,url,authors",
            "limit": str(min(per_query, 100)),
        }
        if years:
            params["year"] = str(years)
        url = ("https://api.semanticscholar.org/graph/v1/paper/search/bulk?"
               + urllib.parse.urlencode(params))
        try:
            data = _http_json(url, cfg=cfg)
        except Exception as exc:
            print(f"warning: S2 bulk search failed for {query!r}: {exc}", file=sys.stderr)
            failed.append(f"s2-bulk:{query}")
            continue
        for p_ in data.get("data", []) or []:
            ext = p_.get("externalIds") or {}
            title = (p_.get("title") or "").strip()
            if not title:
                continue
            out.append({
                "id": ext.get("ArXiv") or ext.get("DOI") or p_.get("paperId"),
                "arxiv_id": ext.get("ArXiv"),
                "doi": ext.get("DOI"),
                "title": re.sub(r"\s+", " ", title),
                "year": p_.get("year"),
                "abstract": re.sub(r"\s+", " ", (p_.get("abstract") or "")).strip()[:1500],
                "url": p_.get("url"),
                "source": "s2-bulk-search",
                "authors": [a.get("name") for a in (p_.get("authors") or []) if a.get("name")],
            })
    return out, failed


def _arxiv_entry_authors(entry: str) -> list[str]:
    """Author names from one Atom `<entry>` fragment, inner whitespace collapsed."""
    names = re.findall(r"<author>\s*<name>([^<]+)</name>", entry, re.DOTALL)
    return [re.sub(r"\s+", " ", n).strip() for n in names]


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
                "authors": _arxiv_entry_authors(entry),
            })
    return out, failed


# --------------------------------------------------------------------------
# report scanning (single source of truth for sync / status / WebUI)
# --------------------------------------------------------------------------

def scan_reports(topic: Path) -> list[dict]:
    """All radar reports under inbox/radar/, newest first.

    Each entry: {name, kind: digest|citation-gap, status: pending-review|reviewed,
    path (absolute str), mtime, size}. This is the one place that knows the
    file-naming and frontmatter-status conventions — sync hints, `radar
    status`, and the WebUI must all consume it instead of re-globbing.
    """
    digest_dir = topic / "inbox" / "radar"
    out: list[dict] = []
    if not digest_dir.is_dir():
        return out
    entries = [(p, "digest") for p in digest_dir.glob("*-digest*.md")]
    entries += [(p, "citation-gap") for p in digest_dir.glob("*-citation-gaps.md")]
    for p, kind in sorted(entries, key=lambda e: e[0].name, reverse=True):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            st = p.stat()
        except OSError:
            continue
        status = report_status(text)
        out.append({"name": p.name, "kind": kind, "status": status,
                    "path": str(p), "mtime": st.st_mtime, "size": st.st_size})
    return out


def pending_names(reports: list[dict], kind: str) -> list[str]:
    return [r["name"] for r in reports if r["kind"] == kind and r["status"] == "pending-review"]


def _candidate_lines(c: dict) -> list[str]:
    """Digest markdown lines for one candidate (no trailing blank).

    parse_digest_candidates must be able to read everything written here —
    keep the two in sync.
    """
    arxiv_link = f"https://arxiv.org/abs/{c['arxiv_id']}" if c.get("arxiv_id") else ""
    link = c.get("url") or arxiv_link
    # Every field below is re-parsed out of this markdown later, so anything
    # that could impersonate the format has to be neutralised on the way in:
    # a newline turns one candidate into two, and a backtick closes the id span
    # early (S2 falls back to a DOI when there is no arXiv id, and DOIs are
    # free-form). A blank title would produce a `## ` heading the parser skips.
    title = re.sub(r"\s+", " ", str(c.get("title") or "")).strip() or "(untitled)"
    cid = re.sub(r"\s+", " ", str(c.get("id") or "")).replace("`", "'").strip()
    lines = [f"## {title}", ""]
    meta = f"- id: `{cid}` · {c.get('year', '?')} · source: {c['source']}"
    if c.get("score") is not None:
        meta += f" · relevance: {c['score']}"
    lines.append(meta)
    names = c.get("authors") or []
    if names:
        # ", " is the round-trip separator parse_digest_candidates splits on,
        # so a comma inside one name ("Rodriguez, Jr.") would read back as two
        # authors — normalize it away here; candidates.jsonl keeps raw names.
        shown = [re.sub(r"\s+", " ", n.replace(",", " ")).strip() for n in names[:6]]
        lines.append("- authors: " + ", ".join(shown)
                     + (", et al." if len(names) > 6 else ""))
    if link:
        lines.append(f"- {link}")
    if arxiv_link and arxiv_link != link:
        lines.append(f"- {arxiv_link}")
    if c.get("abstract"):
        flat = re.sub(r"\s+", " ", str(c["abstract"])).strip()
        lines.append(f"- abstract: {_ellipsize(flat, 500)}")
    return lines


def parse_digest_candidates(text: str) -> list[dict]:
    """Parse a digest's candidate sections for programmatic review actions.

    Understands the format _candidate_lines writes: `## <title>` headings
    followed by `- id: \\`<id>\\` · ...` metadata lines, an optional
    `- authors: A, B, ...` line, and bare `- <url>` link lines.
    Tolerant of citation-gap reports (whose sections parse as title-only)
    and of older digests without authors lines.
    """
    out: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur:
                out.append(cur)
            cur = {"index": len(out), "title": m.group(1), "id": None,
                   "arxiv_id": None, "url": None, "relevance": None,
                   "authors": [], "abstract": None}
            continue
        if cur is None:
            continue
        mid = re.match(r"^- id: `([^`]+)`", line)
        if mid:
            cur["id"] = mid.group(1)
            mrel = re.search(r"relevance: (-?[0-9.]+)", line)
            if mrel:
                try:
                    cur["relevance"] = float(mrel.group(1))
                except ValueError:
                    pass
            continue
        mauth = re.match(r"^- authors: (.+)$", line)
        if mauth:
            names = mauth.group(1).split(", ")
            if names and names[-1] == "et al.":
                names = names[:-1]
            cur["authors"] = names
            continue
        # Citation-gap reports written before they carried an `- id:` line.
        # Their arXiv id lives in the `- candidate:` line instead; without this
        # an old report parses to a title with nothing to act on.
        mcand = re.match(r"^- candidate: .*?arXiv:([\w.\-]+)", line)
        if mcand and cur["id"] is None and mcand.group(1) != "?":
            cur["id"] = cur["arxiv_id"] = re.sub(r"v\d+$", "", mcand.group(1))
            continue
        mabs = re.match(r"^- abstract: (.+)$", line)
        if mabs:
            # The abstract is what a reviewer actually judges on, so it has to
            # survive back out of the digest and into the triage row.
            cur["abstract"] = mabs.group(1).strip()
            continue
        murl = re.match(r"^- (https?://\S+)\s*$", line)
        if murl:
            url = murl.group(1)
            if cur["url"] is None:
                cur["url"] = url
            ma = re.search(r"arxiv\.org/abs/([\w.\-]+)", url)
            if ma and cur["arxiv_id"] is None:
                cur["arxiv_id"] = re.sub(r"v\d+$", "", ma.group(1))
    if cur:
        out.append(cur)
    return out


def mark_report_reviewed(path: Path) -> bool:
    """Flip `status: pending-review` -> `status: reviewed` (first occurrence).

    Returns False when the report is not pending (already reviewed / foreign
    format) — callers surface that as a conflict rather than rewriting blindly.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    head, body = _split_frontmatter(text)
    if head is None or "status: pending-review" not in head:
        return False
    # Scoped to the frontmatter: a digest body is full of paper abstracts, and
    # one quoting "status: pending-review" would otherwise be the line that got
    # rewritten while the real frontmatter stayed pending forever.
    path.write_text(head.replace("status: pending-review", "status: reviewed", 1) + body,
                    encoding="utf-8")
    return True


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """(frontmatter-including-fences, rest). (None, text) when absent.

    Tolerates CRLF — these files are edited by hand on Windows.
    """
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return None, text
    return m.group(0), text[m.end():]


def report_status(text: str) -> str:
    """`pending-review` or `reviewed`, read from the frontmatter only."""
    head, _ = _split_frontmatter(text)
    return "pending-review" if head and "status: pending-review" in head else "reviewed"


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
            # One vector per PAPER, not per chunk. Averaging raw chunks lets a
            # long paper outvote a short one purely by length — and the old
            # `LIMIT 400` with no ORDER BY made it worse: past 400 chunks the
            # rows kept were whatever SQLite's physical storage order handed
            # back, which on a reindexed library silently dropped entire papers
            # out of the fingerprint with nothing in the log.
            rows = conn.execute(
                "SELECT c.path, v.embedding FROM chunks_vec v JOIN chunks c ON c.id = v.rowid "
                "WHERE c.collection IN ('concepts', 'references', 'topics', 'theses') "
                "ORDER BY c.path, c.id"
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return False
        per_paper: dict[str, list] = {}
        for path, blob in rows:
            per_paper.setdefault(path, []).append(np.frombuffer(blob, dtype=np.float32))
        mat = np.array([np.mean(vs, axis=0) for vs in per_paper.values()])
        centroid = mat.mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm == 0:
            return False
        centroid = centroid / norm

        emb = Embedder(start=topic)

        # In batches, because `emb.embed(text)` is `embed_many([text])` — one
        # request per candidate. A harvest scores forty of them, so this was
        # forty round trips where the embedder's own batch size asks for three.
        # (The connection is pooled by a requests.Session either way, so the
        # saving is per-request latency and server-side batching, not TCP
        # handshakes. No benchmark for it lives in this repo, so no factor is
        # claimed here.)
        wanted = [(c, f"{c.get('title') or ''}\n{(c.get('abstract') or '')[:800]}".strip())
                  for c in cands]
        wanted = [(c, t) for c, t in wanted if t]

        scored_any = False
        for start in range(0, len(wanted), emb.batch):
            chunk = wanted[start:start + emb.batch]
            vecs = emb.embed_many([t for _, t in chunk])
            if vecs is None:
                break  # Ollama went away — keep whatever we scored so far
            for (c, _), vec in zip(chunk, vecs):
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

def _apply_budget(cands: list[dict], max_c: int) -> list[dict]:
    """Cut to the candidate cap while guaranteeing arXiv recency a share.

    The intent was always that Semantic Scholar recommendations must not crowd
    out new arXiv listings — but reserving the budget at *fetch* time did
    nothing, because the relevance sort that follows re-merges both pools and
    the cap then falls wherever the scores land. On a real run that put 9 of
    the top 10 on the S2 side, which is exactly backwards for a tool whose job
    is to tell you what appeared this week.

    So the split is enforced here, after scoring: each source keeps its own
    best up to half the budget, and whichever source has spare capacity gives
    it to the other. Order within the result is still by score.
    """
    if len(cands) <= max_c:
        return cands
    recency = [c for c in cands if str(c.get("source", "")).startswith("arxiv-new")]
    rec_share = min(len(recency), max_c // 2)
    keep_ids = {id(c) for c in recency[:rec_share]}
    for c in cands:                       # fill the rest in score order
        if len(keep_ids) >= max_c:
            break
        keep_ids.add(id(c))
    return [c for c in cands if id(c) in keep_ids]


def _resolve_topic(args: argparse.Namespace) -> Path | None:
    """The workspace a radar command acts on, validated.

    An unchecked `--topic-dir` used to fail in two unhelpful ways: a path that
    does not exist got an `output/radar/` tree fabricated inside it and the
    command reported success, and a path that is a *file* crashed with a raw
    traceback out of `Path.mkdir`.
    """
    if not getattr(args, "topic_dir", None):
        topic = find_workspace_root()
        if topic is None:
            print("no workspace found (run from a topic directory or pass --topic-dir)",
                  file=sys.stderr)
        return topic
    topic = Path(args.topic_dir).expanduser().resolve()
    if not topic.exists():
        print(f"--topic-dir does not exist: {topic}", file=sys.stderr)
        return None
    if not topic.is_dir():
        print(f"--topic-dir is not a directory: {topic}", file=sys.stderr)
        return None
    return topic


def _append_jsonl(path: Path, records) -> None:
    """Append records to one of the radar ledgers, one writer at a time.

    These are the same shape as `output/ingest/queue.jsonl`, which has been
    written under a lock since the browser extension gave it a second writer —
    and its docstring says why: concurrent appends interleave, and a torn line
    is a paper that silently never gets ingested.

    The radar ledgers gained a second writer in v1.15.0 and no lock went with
    it. `magi radar triage` was added in that release, so the WebUI's triage
    endpoint and the CLI now write `triage.jsonl` together; `harvest` can be
    running from the scheduled task while somebody runs it by hand. A lost line
    here is a rejected paper that comes back, or a decision nobody recorded.

    On timeout it writes anyway, for the reason `ingest/ledger.py` gives: the
    fold over these files is last-write-wins per id, so a duplicate line is
    survivable in a way a missing one is not.
    """
    from filelock import FileLock, Timeout

    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if not body:
        return
    lock = FileLock(str(path.parent / ".lock"), timeout=10)
    try:
        with lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(body)
    except Timeout:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(body)


def _triage_path(topic: Path) -> Path:
    return topic / "output" / "radar" / "triage.jsonl"


def load_triage(topic: Path, report: str) -> dict[str, str]:
    """`{candidate id: decision}` recorded so far for one report.

    Triage is the weekly job and it does not finish in one sitting. Without
    somewhere to put "no", a reviewer could only record the handful of papers
    they kept — the other thirty-five decisions lived in their head until the
    tab was closed.
    """
    out: dict[str, str] = {}
    path = _triage_path(topic)
    if not path.is_file():
        return out
    try:
        # Streamed rather than read whole. These ledgers are append-only and
        # only ever folded front to back, so the full string and the list of
        # lines it splits into were two copies of a file that grows for the
        # life of the workspace, held for no reason. `errors="replace"` stays:
        # a byte that will not decode must not stop the fold.
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("report") != report or not rec.get("id"):
                    continue
                decision = rec.get("decision")
                if decision in (None, "reset"):
                    out.pop(rec["id"], None)      # last write wins, including undo
                else:
                    out[rec["id"]] = decision
    except OSError:
        pass
    return out


def record_triage(topic: Path, report: str, cand_id: str, decision: str) -> None:
    """Append one triage decision. `reset` clears a previous one."""
    _append_jsonl(_triage_path(topic), [{
        "report": report, "id": cand_id, "decision": decision,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }])


def last_harvest_date(topic: Path) -> str | None:
    """ISO date of the most recent harvest, or None if it never ran.

    Read from the ledger's own `first_seen` stamps — no new state to keep in
    sync. Nothing anywhere used to record this, so a radar whose scheduled task
    had quietly stopped firing looked exactly like one that ran an hour ago.
    """
    path = topic / "output" / "radar" / "seen.jsonl"
    if not path.is_file():
        return None
    newest: str | None = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    seen = json.loads(line).get("first_seen")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if isinstance(seen, str) and (newest is None or seen > newest):
                    newest = seen
    except OSError:
        return None
    return newest


def harvest_age_days(topic: Path) -> int | None:
    """Days since the last harvest, or None when it has never run."""
    last = last_harvest_date(topic)
    if not last:
        return None
    try:
        return (dt.date.today() - dt.date.fromisoformat(last)).days
    except ValueError:
        return None


def _load_ledger(path: Path) -> set[str]:
    seen: set[str] = set()
    if path.is_file():
        # Same treatment, and the same OSError guard the other two loaders
        # already had: an unreadable ledger means "nothing seen yet", which is
        # safe here — a duplicate candidate is survivable, a crashed harvest
        # is not.
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        seen.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass
    return seen


def cmd_harvest(args: argparse.Namespace) -> int:
    topic = _resolve_topic(args)
    if topic is None:
        return 1
    # Config comes from the workspace being harvested, not from wherever the
    # process happens to be standing. See load_config's `start` docstring.
    cfg = load_config(start=topic)
    categories = [str(c) for c in (cfg_get(cfg, "radar.arxiv_categories", None) or [])]
    # `args.days or …` treated an explicit --days 0 as "unset". 0 is a
    # meaningful request ("only today's listings"), so test for None.
    days = int(args.days if args.days is not None else cfg_get(cfg, "radar.days", 7))
    if days < 0:
        print("--days must be >= 0", file=sys.stderr)
        return 1
    max_c = int(cfg_get(cfg, "radar.max_candidates", 40))
    if max_c <= 0:
        # Every result would be discarded by the cap anyway. Say so before
        # spending a live S2 request and one arXiv round trip per category.
        print("radar.max_candidates is 0 — nothing to harvest "
              "(raise it in config.yaml to re-enable)", file=sys.stderr)
        return 0

    if not categories:
        print("note: radar.arxiv_categories is empty — new arXiv listings will "
              "not be scanned; only Semantic Scholar recommendations are used",
              file=sys.stderr)

    seeds = seed_ids(topic, cfg)
    lib_ids = library_arxiv_ids(topic)
    from_library = sum(1 for s in seeds if s in lib_ids)
    print(f"fingerprint: {len(seeds)} seeds ({from_library} of them from the library's "
          f"{len(lib_ids)} arXiv references)")

    bulk_queries = [str(q) for q in (cfg_get(cfg, "radar.bulk_queries", None) or [])]
    bulk_years = cfg_get(cfg, "radar.bulk_years", None)

    print("[radar] harvesting S2 recommendations...", file=sys.stderr)
    s2_cands = harvest_s2(seeds, limit=min(max(max_c // 2, 10), max_c), cfg=cfg)
    print(f"[radar] harvesting arXiv listings ({len(categories)} categories)...", file=sys.stderr)
    arxiv_cands, failed_sources = harvest_arxiv(categories, days)

    # The third leg, and the only one that can look backwards. Off unless
    # somebody wrote a query list, so a workspace that has not opted in pays
    # nothing and sees no change.
    bulk_cands: list[dict] = []
    if bulk_queries:
        print(f"[radar] searching S2 corpus ({len(bulk_queries)} queries"
              + (f", years {bulk_years}" if bulk_years else "") + ")...", file=sys.stderr)
        bulk_cands, bulk_failed = harvest_s2_bulk(
            bulk_queries, limit=min(max(max_c // 2, 10), max_c),
            years=str(bulk_years) if bulk_years else None, cfg=cfg)
        failed_sources = list(failed_sources) + bulk_failed

    candidates = s2_cands + arxiv_cands + bulk_cands

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
    fresh = _apply_budget(fresh, max_c)

    today = dt.date.today().isoformat()
    # Ledger first, then the cumulative log. The ledger is what stops a paper
    # being re-surfaced forever; the log is a convenience. Writing the log
    # first meant a failure in between (unwritable ledger, full disk) left
    # candidates recorded as harvested but never marked seen — so every later
    # run re-offered them, and the digest that would have carried them was
    # never written either.
    _append_jsonl(ledger_path, [{"id": c["id"], "first_seen": today,
                                 "source": c["source"]} for c in fresh])
    # candidates.jsonl is a cumulative log of harvested candidates — append,
    # never truncate (the per-digest list lives in the digest itself).
    _append_jsonl(radar_dir / "candidates.jsonl", fresh)

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
            lines += _candidate_lines(c)
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


def _s2_get(url: str, retries: int = 1, cfg: dict | None = None) -> dict:
    for attempt in range(retries + 1):
        try:
            return _http_json(url, cfg=cfg)
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
    topic = _resolve_topic(args)
    if topic is None:
        return 1
    cfg = load_config(start=topic)
    own_ids = [str(s) for s in (cfg_get(cfg, "radar.own_arxiv_ids", None) or [])]
    if not own_ids:
        own_ids = [str(s) for s in (cfg_get(cfg, "radar.seed_arxiv_ids", None) or [])]
        if own_ids:
            # Seeds are "papers that describe what we care about" — often other
            # people's. This report calls them "our paper" and asks who failed
            # to cite them, so say out loud that the fallback happened.
            print("note: radar.own_arxiv_ids is unset — falling back to "
                  "radar.seed_arxiv_ids, which may include papers you did not "
                  "write. Set radar.own_arxiv_ids in config.yaml.", file=sys.stderr)
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
        meta_failed = False
        try:
            meta = _s2_get(f"{base}/{pid}?fields=title,abstract", cfg=cfg)
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: S2 metadata lookup failed for {own}: {exc}", file=sys.stderr)
            meta = {}
            meta_failed = True
        own_meta[own] = {"title": (meta.get("title") or "").strip(),
                        "abstract": meta.get("abstract") or ""}
        try:
            refs = _s2_get(f"{base}/{pid}/references?fields=paperId,title&limit=200", cfg=cfg)
            time.sleep(1.1)
            cits = _s2_get(f"{base}/{pid}/citations?fields=paperId&limit=500", cfg=cfg)
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
            # "No references on S2" and "S2 refused to talk to us" are different
            # facts. Reporting a rate limit as the former told the user to wait
            # for indexing that had already happened.
            if meta_failed:
                print(f"warning: skipping {own} — Semantic Scholar did not answer "
                      f"(rate limit or outage), so we cannot tell whether it has "
                      f"reference data. Retry later.", file=sys.stderr)
            else:
                print(f"note: {own} has no reference data on S2 yet — skipping",
                      file=sys.stderr)
            continue

        url = (f"https://api.semanticscholar.org/recommendations/v1/papers"
               f"?fields=title,externalIds,abstract,year,url,paperId&limit=30")
        try:
            recs = _http_json(url, {"positivePaperIds": [pid]}, cfg=cfg)
            time.sleep(1.1)
        except Exception as exc:
            print(f"warning: recommendations failed for {own}: {exc}", file=sys.stderr)
            continue

        neighbors = recs.get("recommendedPapers", []) or []
        # Only neighbours that survive the cheap filters cost a request, so
        # count those. Announcing the raw neighbour count and then stopping at
        # an unmentioned internal cap read as "it gave up early" — and left the
        # user with no idea that ten papers were never examined at all.
        eligible = [c for c in neighbors
                    if c.get("paperId") and c["paperId"] not in citers
                    and (c.get("year") or 0) >= year_cut]
        budget = min(len(eligible), NEIGHBOR_BUDGET)
        skipped = len(eligible) - budget
        print(f"[radar] anchor {own}: refs={len(my_refs)} citers={len(citers)}, "
              f"{len(neighbors)} neighbors -> {len(eligible)} eligible, checking {budget}"
              + (f" (request budget; {skipped} not examined)" if skipped else ""),
              file=sys.stderr)
        checked = 0
        for cand in eligible[:budget]:
            cand_pid = cand["paperId"]
            checked += 1
            print(f"[radar]   neighbor {checked}/{budget}: {(cand.get('title') or '')[:60]}",
                  file=sys.stderr)
            try:
                cand_refs = _s2_get(f"{base}/{cand_pid}/references?fields=paperId&limit=200", cfg=cfg)
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
    # Only rewrite the machine-readable side when there is something to say.
    # It used to be truncated unconditionally while the markdown report was
    # written only `if findings`, so a run that found nothing (or hit a rate
    # limit) erased the previous run's results and left the report file behind
    # describing findings that no longer existed anywhere else.
    if findings:
        (radar_dir / "citation-gaps.jsonl").write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in findings),
            encoding="utf-8")

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
            title = re.sub(r"\s+", " ", str(f_.get("candidate_title") or "")).strip() or "(untitled)"
            cid = str(f_.get("candidate_arxiv") or f_.get("candidate_s2") or "").replace("`", "'")
            lines.append(f"## {title}")
            lines.append("")
            # Same `- id:` shape the harvest digest uses, so one parser reads
            # both and the WebUI can offer the same per-candidate actions here.
            lines.append(f"- id: `{cid}` · {f_.get('year', '?')} · source: citation-gap")
            lines.append(f"- should arguably cite: our arXiv:{f_['own_paper']}")
            lines.append(f"- candidate: {f_['year']} · arXiv:{f_['candidate_arxiv'] or '?'} · "
                         f"shared refs: {f_['shared_refs']}")
            titles = f_.get("shared_ref_titles") or []
            if titles:
                lines.append("- shared references include: " + "; ".join(titles))
            if f_.get("candidate_arxiv"):
                lines.append(f"- https://arxiv.org/abs/{f_['candidate_arxiv']}")
            if f_.get("url"):
                lines.append(f"- {f_['url']}")
            if f_.get("abstract"):
                flat = re.sub(r"\s+", " ", str(f_["abstract"])).strip()
                lines.append(f"- abstract: {_ellipsize(flat, 400)}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"citation-gap: {len(findings)} candidates -> {out}")
    else:
        print("citation-gap: no candidates survived the funnel")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    topic = _resolve_topic(args)
    if topic is None:
        return 1
    radar_dir = topic / "output" / "radar"
    ledger = _load_ledger(radar_dir / "seen.jsonl")
    reports = scan_reports(topic)
    pending = pending_names(reports, "digest")
    gap_pending = pending_names(reports, "citation-gap")
    failed_sources = None
    digest_dir = topic / "inbox" / "radar"
    if digest_dir.is_dir():
        digests = sorted(digest_dir.glob("*-digest*.md"))
        if digests:
            newest = max(digests, key=lambda p: p.stat().st_mtime)
            try:
                m = re.search(r"^sources_failed:\s*\[([^\]]*)\]",
                              newest.read_text(encoding="utf-8"), re.MULTILINE)
                if m:
                    failed_sources = m.group(1).strip()
            except OSError:
                pass
    age = harvest_age_days(topic)
    payload = {"seen_total": len(ledger), "pending_digests": pending,
               "pending_citation_gaps": gap_pending,
               "last_harvest": last_harvest_date(topic),
               "harvest_age_days": age,
               "last_digest_failed_sources": failed_sources}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        when = ("never harvested" if age is None
                else "harvested today" if age == 0
                else f"last harvest {age}d ago")
        print(f"radar: {when} · {len(ledger)} papers seen · "
              f"{len(pending)} digest(s) pending review"
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
    topic = _resolve_topic(args)
    if topic is None:
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
        print("magi not found on PATH — install it first: "
              "pipx upgrade --install magi-research", file=sys.stderr)
        return 1
    # Belt and braces on the working directory. `--topic-dir` now steers config
    # discovery on its own, but a scheduled task that also *starts* in the
    # workspace behaves identically to a hand-run command, which is the only
    # way this stays debuggable — Task Scheduler otherwise runs from
    # %SystemRoot%\System32, launchd from /, and cron from $HOME.
    if sys.platform == "win32":
        # schtasks has no start-in flag; `cmd /c cd /d <ws> && magi ...` is the
        # documented way to get one.
        cmd = ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", args.time,
               "/TN", task_name,
               "/TR", f'cmd /c cd /d "{topic}" && "{magi_exe}" radar harvest '
                      f'--topic-dir "{topic}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"Registered task {task_name} (daily {args.time}). "
                  f"Remove with: magi radar install-schedule --uninstall")
        else:
            print(proc.stdout.strip() or proc.stderr.strip(), file=sys.stderr)
        return proc.returncode
    elif sys.platform == "darwin":
        hh, mm = args.time.split(":")
        # Escape before interpolating: a workspace path is user text going into
        # XML, and an ampersand in a directory name — "Papers & Notes" is an
        # ordinary folder — produces a plist launchd refuses to parse, so the
        # schedule silently never runs.
        from xml.sax.saxutils import escape as _xml

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{_xml(str(label))}</string>
  <key>ProgramArguments</key><array>
    <string>{_xml(str(magi_exe))}</string><string>radar</string><string>harvest</string>
    <string>--topic-dir</string><string>{_xml(str(topic))}</string>
  </array>
  <key>WorkingDirectory</key><string>{_xml(str(topic))}</string>
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
        hh, mm = (args.time.split(":") + ["0"])[:2]
        # Quoted, like the schtasks branch above already is. cron runs the line
        # through a shell, so an unquoted path breaks at the first space — and
        # "~/My Papers" is an ordinary place to keep a workspace. The failure is
        # silent: cron just runs `cd ~/My` every night.
        print(f'add to crontab: {int(mm)} {int(hh)} * * * '
              f'cd "{topic}" && "{magi_exe}" radar harvest --topic-dir "{topic}"')
        return 0


def cmd_triage(args: argparse.Namespace) -> int:
    """Record a review decision where the WebUI reads it, or list what is there.

    There was no command for this. `record_triage`/`load_triage` existed and
    were called only from `magi.ui.api`, so the `radar_review` skill did the
    only thing left to it and hand-edited the digest's frontmatter — a second
    store nothing else reads. An agent could triage forty candidates and the
    radar panel would still show forty undecided, because the two surfaces
    were writing to different files and neither knew about the other.
    """
    topic = _resolve_topic(args)
    if topic is None:
        return 1

    reports = scan_reports(topic)
    if not reports:
        print("no radar reports under inbox/radar/", file=sys.stderr)
        return 1
    if args.report:
        match = [r for r in reports if r["name"] == args.report]
        if not match:
            print(f"no such report: {args.report}\navailable: "
                  + ", ".join(r["name"] for r in reports), file=sys.stderr)
            return 1
        report = match[0]
    else:
        pending = [r for r in reports if r["status"] == "pending-review"]
        report = (pending or reports)[0]

    text = Path(report["path"]).read_text(encoding="utf-8", errors="replace")
    cands = parse_digest_candidates(text)
    recorded = load_triage(topic, report["name"])

    if not args.decision:
        rows = [{"index": c["index"], "id": c["id"], "title": c["title"],
                 "decision": recorded.get(c["id"] or "")} for c in cands]
        if args.json:
            print(json.dumps({"report": report["name"], "candidates": rows},
                             ensure_ascii=False))
        else:
            print(f"{report['name']} — {len(rows)} candidate(s)")
            for r in rows:
                print(f"  [{r['index']:>2}] {r['decision'] or '-':<8} "
                      f"{(r['id'] or '?'):<24} {r['title']}")
        return 0

    if args.cand_id:
        cand = next((c for c in cands if c["id"] == args.cand_id), None)
        if cand is None:
            print(f"no candidate with id {args.cand_id} in {report['name']}",
                  file=sys.stderr)
            return 1
    elif args.index is not None:
        if not (0 <= args.index < len(cands)):
            print(f"no candidate #{args.index} in {report['name']} "
                  f"({len(cands)} present)", file=sys.stderr)
            return 1
        cand = cands[args.index]
    else:
        print("name a candidate with --id or --index", file=sys.stderr)
        return 2

    if not cand["id"]:
        print("that candidate carries no id to record a decision against",
              file=sys.stderr)
        return 1

    record_triage(topic, report["name"], cand["id"], args.decision)
    if args.json:
        print(json.dumps({"report": report["name"], "id": cand["id"],
                          "decision": None if args.decision == "reset" else args.decision},
                         ensure_ascii=False))
    else:
        verb = "cleared" if args.decision == "reset" else f"recorded {args.decision}"
        print(f"{verb}: {cand['title']}")
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

    p_t = sub.add_parser("triage", help="Record or list review decisions on a report's candidates")
    p_t.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_t.add_argument("--report", help="Report file name under inbox/radar/ (default: newest pending)")
    p_t.add_argument("--id", dest="cand_id", help="Candidate id (see the report, or --json)")
    p_t.add_argument("--index", type=int, help="Candidate position instead of its id")
    # The same three words the WebUI stores. A CLI that wrote "keep" where the
    # panel writes "accept" would put two vocabularies in one ledger, which is
    # the shape of the bug this command exists to close.
    p_t.add_argument("--decision", choices=["accept", "dismiss", "reset"],
                     help="Omit to list what is recorded so far")
    p_t.add_argument("--json", action="store_true")
    p_t.set_defaults(func=cmd_triage)

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
