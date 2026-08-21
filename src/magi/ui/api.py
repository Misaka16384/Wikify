"""FastAPI routes and application factory for MAGI WebUI."""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib.resources
import json
import mimetypes
import os
import re
import sqlite3
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import magi
from magi.core.workspace import (
    find_hub_root,
    find_workspace_root,
    is_hub_root,
    is_topic_root,
)

# Windows' registry-driven mimetypes table often lacks .webp and .woff2, so the
# bundled background art and the KaTeX fonts would go out as
# application/octet-stream.
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
from magi.kb.detect_uncompiled import find_uncompiled
from magi.kb_registry import (
    _config_home,
    _set_enabled,
    load_registry,
    load_settings,
    register_kb,
    save_registry,
    searchable_kbs,
)
from magi.pm import bd_available, bd_status_summary
from magi.setup_cmd import doctor_rows, find_legacy_copies
from magi.sync import build_report
from magi.ui.jobs import task_manager


# --------------------------------------------------------------------------
# Request / Response Models
# --------------------------------------------------------------------------

class KBRegisterRequest(BaseModel):
    path: str
    name: Optional[str] = None
    enabled: bool = True


class KBToggleRequest(BaseModel):
    enabled: bool


class RadarReviewRequest(BaseModel):
    file: str
    action: str = "mark-reviewed"
    workspace: Optional[str] = None


class RadarCandidateRequest(BaseModel):
    file: str
    index: int
    action: str  # accept-to-inbox | create-issue
    workspace: Optional[str] = None


class IngestDecideRequest(BaseModel):
    batch_id: str
    item_id: str
    decision: str                     # approve | reject | reset
    workspace: Optional[str] = None


class IngestEnqueueRequest(BaseModel):
    """The browser extension's entire vocabulary.

    Deliberately tiny. This endpoint appends one line to a queue and can do
    nothing else — it never spawns a job, never writes into raw/ or wiki/, and
    what it queues stays inert until a human approves the batch it lands in.
    That is what lets it exist without authentication.
    """

    value: str = Field(..., min_length=1)
    library: Optional[str] = None
    title: Optional[str] = None


class JobCreateRequest(BaseModel):
    # Whitelisted operation id (see magi.ui.jobs.OPS) — raw argv is not accepted.
    op: str = Field(..., min_length=1)
    kb: Optional[str] = None          # registry name or workspace path; default: server workspace
    params: Dict[str, bool] = Field(default_factory=dict)
    confirm: Optional[str] = None     # must equal `op` for danger operations


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _resolve_workspace(workspace_param: Optional[str]) -> Path:
    if workspace_param:
        return Path(workspace_param).resolve()
    ws = find_workspace_root()
    if ws is not None:
        return ws
    return Path.cwd().resolve()


# Preview reads a whole file into a JSON reply; past a couple of megabytes
# that is a browser problem, not a reading experience.
DOC_PREVIEW_MAX_BYTES = 2 * 1024 * 1024

# Text the preview knows how to show. Refusing the rest is not about secrecy —
# the endpoint would happily base64 a 400 MB PDF into a JSON string.
DOC_PREVIEW_SUFFIXES = {
    ".md", ".markdown", ".txt", ".tex", ".bib", ".yaml", ".yml", ".json", ".csv",
}

# Figures a card can embed. Same door, different keyring.
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif"}


def _safe_workspace_file(ws: Path, rel: str, suffixes: set[str] | None = None) -> Path:
    """Resolve *rel* inside *ws*, or raise. The only door into the filesystem.

    Query strings arrive from the browser, so `..`, absolute paths and
    symlinks pointing out of the workspace all have to bounce here rather
    than at the read.
    """
    if not rel:
        raise HTTPException(status_code=400, detail="empty path")
    candidate = Path(rel)
    # Absoluteness is decided by the string, not by whichever OS is parsing
    # it: PurePath on Linux calls "C:/Windows/win.ini" relative, and on
    # Windows it calls "/etc/hosts" drive-relative. Either way the caller
    # plainly meant an absolute path, and either way the answer is no.
    if (candidate.is_absolute() or candidate.drive or rel[0] in "/\\"
            or re.match(r"^[A-Za-z]:[\\/]", rel)):
        raise HTTPException(status_code=400, detail="path must be workspace-relative")
    target = (ws / candidate).resolve()
    root = ws.resolve()
    if root != target and root not in target.parents:
        raise HTTPException(status_code=403, detail="path escapes the workspace")
    allowed = DOC_PREVIEW_SUFFIXES if suffixes is None else suffixes
    if target.suffix.lower() not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"{target.suffix or 'that file type'} is not served by this endpoint")
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"No such file: {candidate.as_posix()}")
    return target


def _reading_root(workspace: Optional[str], kb: Optional[str]) -> Path:
    """The workspace a file-reading endpoint is allowed to read from.

    Unlike the report endpoints, /doc and /asset return raw bytes, so the
    directory has to be a MAGI workspace (or a hub, or a registered KB) and
    not merely a path someone typed into the query string.
    """
    if kb and kb != "local":
        return _kb_root(kb)
    root = _resolve_workspace(workspace)
    if is_topic_root(root) or is_hub_root(root):
        return root
    registered = {Path(e["path"]).resolve()
                  for e in load_registry().get("kbs", {}).values()}
    if root.resolve() in registered:
        return root
    raise HTTPException(
        status_code=400,
        detail=f"{root} is not a MAGI workspace — pass a topic directory or kb=<name>")


def _kb_root(name: str) -> Path:
    """Root of a registered KB by name. Search results name their KB, not its
    path, and the browser has no business learning filesystem layout."""
    entry = load_registry().get("kbs", {}).get(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"KB '{name}' not found in registry")
    root = Path(entry["path"])
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"KB '{name}' path is gone: {root}")
    return root.resolve()


def _get_static_dir() -> Path:
    try:
        res = importlib.resources.files("magi.ui").joinpath("static")
        path = Path(str(res))
        if path.is_dir():
            return path
    except Exception:
        pass
    fallback = Path(__file__).parent / "static"
    return fallback


class RevalidatingStatic(StaticFiles):
    """Serve assets with must-revalidate.

    StaticFiles only sends etag/last-modified, so browsers apply
    heuristic freshness and can hold a stale styles.css/app.js across
    an upgrade — the UI then looks unchanged after a version bump.
    The ETag still makes every revalidation a cheap 304.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp


# --------------------------------------------------------------------------
# App Factory
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task_manager.set_event_loop(asyncio.get_running_loop())
    yield


def create_app(extra_allowed_hosts: list[str] | None = None) -> FastAPI:
    app = FastAPI(
        title="MAGI Research Workspace WebUI",
        version=magi.__version__,
        description="Local inspection, triage, and ops dashboard for the MAGI research workspace CLI.",
        lifespan=lifespan,
    )

    # Host allowlist blocks DNS-rebinding: a malicious site resolving to
    # 127.0.0.1 still sends its own Host header, which gets rejected here.
    # Deliberately NO CORS middleware — mutations are JSON-body-only, so
    # browsers require a preflight that (absent CORS headers) always fails.
    allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
    for h in extra_allowed_hosts or []:
        if h and h not in allowed_hosts:
            allowed_hosts.append(h)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


    # ----------------------------------------------------------------------
    # 1. Global & Registry API
    # ----------------------------------------------------------------------

    @app.get("/api/status")
    def get_status() -> dict:
        current_ws = find_workspace_root()
        hub_root = find_hub_root()
        kbs = load_registry().get("kbs", {})
        # This used to call doctor_rows() — which shells out for six external
        # tools and diffs every shipped skill against four agent CLIs' install
        # directories, ~450ms — and then read exactly two of its thirteen rows.
        # Both of those rows are hardcoded True in doctor_rows itself, and for
        # good reason: if this process is answering the request, magi and
        # Python are present. So the page-load path paid 450ms for a constant.
        # The genuine probe lives at /api/doctor, which Diagnostics fetches on
        # demand.
        doc_ok = True
        jobs = task_manager.list_jobs()
        active_jobs = [j for j in jobs if j["status"] == "running"]

        return {
            "version": magi.__version__,
            "cwd": str(Path.cwd().resolve()),
            "active_workspace": str(current_ws.resolve()) if current_ws else None,
            "hub": str(hub_root.resolve()) if hub_root else None,
            "registered_kbs_count": len(kbs),
            "doctor_ok": doc_ok,
            "active_jobs_count": len(active_jobs),
        }

    @app.get("/api/kb")
    def list_kbs() -> dict:
        data = load_registry()
        current = find_workspace_root()
        entries = sorted(data.get("kbs", {}).items())

        # Each report is filesystem + subprocess I/O over a different
        # workspace, so they overlap cleanly. Serially this was the slowest
        # request the dashboard makes and it is on the page-load path — with
        # six registered libraries it took 2.5s and the UI sat there.
        def report_for(entry: dict) -> dict | None:
            p = Path(entry["path"])
            if not (p.is_dir() and (p / "wiki").is_dir()):
                return None
            try:
                return build_report(p)
            except Exception:
                return None

        reports: list[dict | None] = [None] * len(entries)
        if entries:
            with ThreadPoolExecutor(max_workers=min(8, len(entries))) as pool:
                futures = {pool.submit(report_for, e): i for i, (_, e) in enumerate(entries)}
                for fut in as_completed(futures):
                    reports[futures[fut]] = fut.result()

        rows = []
        for (name, entry), sync_info in zip(entries, reports):
            p = Path(entry["path"])
            idx = p / "output" / "index.db"
            graph_db = p / "output" / "graph.db"
            is_cur = current is not None and p.resolve() == current.resolve()

            rows.append({
                "name": name,
                "path": entry["path"],
                "enabled": bool(entry.get("enabled", False)),
                "registered": entry.get("registered"),
                "indexed": idx.is_file(),
                "graph_built": graph_db.is_file(),
                "exists": p.is_dir(),
                "current": is_cur,
                "sync_ratio": sync_info.get("sync_ratio") if sync_info else None,
                "cores": sync_info.get("cores") if sync_info else None,
            })
        return {"kbs": rows}

    @app.post("/api/kb/register")
    def post_register_kb(req: KBRegisterRequest) -> dict:
        p = Path(req.path).resolve()
        if not p.is_dir():
            raise HTTPException(status_code=400, detail=f"Directory does not exist: {p}")
        name = register_kb(p, name=req.name, enabled=req.enabled, quiet=True)
        return {"name": name, "path": str(p), "enabled": req.enabled}

    @app.post("/api/kb/{name}/toggle")
    def toggle_kb(name: str, req: KBToggleRequest) -> dict:
        res = _set_enabled(name, req.enabled)
        if res != 0:
            raise HTTPException(status_code=404, detail=f"KB '{name}' not found in registry")
        return {"name": name, "enabled": req.enabled}

    @app.delete("/api/kb/{name}")
    def unregister_kb_endpoint(name: str) -> dict:
        data = load_registry()
        if name not in data.get("kbs", {}):
            raise HTTPException(status_code=404, detail=f"KB '{name}' not found in registry")
        del data["kbs"][name]
        save_registry(data)
        return {"name": name, "deleted": True}

    @app.get("/api/doctor")
    def get_doctor(workspace: Optional[str] = Query(None)) -> dict:
        # Most rows are about the machine, but the agent-CLI rows report which
        # skills are installed *in a workspace* — and with no argument that
        # resolved from the server's own working directory, so the modal said
        # "no skills in this workspace" about a library the reader was not
        # looking at. Report on the one the picker names.
        ws = _resolve_workspace(workspace)
        rows = doctor_rows(ws)
        legacy = find_legacy_copies()
        return {
            "workspace": str(ws) if ws else None,
            # `ok` stays for older clients; `status` is what distinguishes a
            # real problem from an optional component nobody installed.
            "doctor": [{"tool": r.name, "ok": r.ok, "status": r.status,
                        "detail": r.detail, "url": r.url} for r in rows],
            "legacy": [str(p) for p in legacy],
        }

    # ----------------------------------------------------------------------
    # 2. Workspace Introspection API
    # ----------------------------------------------------------------------

    @app.get("/api/workspace/sync")
    def get_workspace_sync(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        try:
            return build_report(ws)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to generate sync report: {exc}")

    @app.get("/api/workspace/claims")
    def get_workspace_claims(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        graph_db = ws / "output" / "graph.db"
        claims: list[dict] = []

        if graph_db.is_file():
            conn = None
            try:
                conn = sqlite3.connect(f"{graph_db.as_uri()}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT c.id, c.doc_id, c.text, c.status,
                           GROUP_CONCAT(COALESCE(e.source_type, ''), ' | ') AS source_type,
                           GROUP_CONCAT(COALESCE(e.source, ''), ' | ') AS source,
                           GROUP_CONCAT(COALESCE(e.quote, ''), ' | ') AS quote
                    FROM claims c
                    LEFT JOIN evidence e ON c.id = e.claim_id
                    GROUP BY c.id, c.doc_id, c.text, c.status
                    ORDER BY c.id
                    """
                )
                for r in cursor.fetchall():
                    claims.append(dict(r))
            except sqlite3.Error as e:
                pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        if not claims:
            # Fallback: scan markdown files for <!-- magi:claims ... --> or claims.txt
            from magi.kb.verify_claims import parse_blocks

            for md in ws.glob("wiki/**/*.md"):
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                    for m in re.finditer(r"<!--\s*magi:claims\s*\n(.*?)\n\s*-->", text, re.DOTALL):
                        blocks = parse_blocks(m.group(1))
                        for b in blocks:
                            claims.append({
                                "id": f"claim-{len(claims)+1}",
                                "doc_id": str(md.relative_to(ws)).replace("\\", "/"),
                                "text": b.get("claim"),
                                "status": b.get("status") or "unverified",
                                "source_type": b.get("source_type"),
                                "source": b.get("source"),
                                "quote": b.get("evidence"),
                            })
                except Exception:
                    continue

        verified_count = sum(1 for c in claims if c.get("status") in ("verified", "web-verified"))
        return {
            "workspace": str(ws),
            "claims": claims,
            "total": len(claims),
            "verified": verified_count,
            "unverified": len(claims) - verified_count,
        }

    @app.get("/api/workspace/backlog")
    def get_workspace_backlog(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        try:
            items = find_uncompiled(ws)
            return {"workspace": str(ws), "backlog": items, "count": len(items)}
        except Exception as exc:
            return {"workspace": str(ws), "backlog": [], "count": 0, "error": str(exc)}

    @app.get("/api/workspace/radar")
    def get_workspace_radar(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        radar_dir = ws / "output" / "radar"
        ledger_file = radar_dir / "seen.jsonl"
        seen_count = 0
        if ledger_file.is_file():
            try:
                with open(ledger_file, "r", encoding="utf-8", errors="replace") as f:
                    seen_count = sum(1 for line in f if line.strip())
            except Exception:
                pass

        from magi.radar import (harvest_age_days, last_harvest_date,
                                 load_triage, pending_names, scan_reports)

        digests = []
        pending_candidates = 0
        for r in scan_reports(ws):
            entry = dict(r)
            entry["path"] = str(Path(r["path"]).relative_to(ws)).replace("\\", "/")
            if entry["status"] == "pending-review":
                # "2 files pending" is not the number anyone acts on — papers are.
                try:
                    from magi.radar import parse_digest_candidates

                    text = Path(r["path"]).read_text(encoding="utf-8", errors="replace")
                    cands = parse_digest_candidates(text)
                    decided = load_triage(ws, entry["name"])
                    entry["candidates"] = len(cands)
                    entry["untriaged"] = sum(1 for c in cands
                                             if not decided.get(c.get("id") or ""))
                    pending_candidates += entry["untriaged"]
                except Exception:
                    entry["candidates"] = None
                    entry["untriaged"] = None
            digests.append(entry)

        return {
            "workspace": str(ws),
            "seen_total": seen_count,
            "last_harvest": last_harvest_date(ws),
            "harvest_age_days": harvest_age_days(ws),
            "pending_candidates": pending_candidates,
            "pending_digests": pending_names(digests, "digest"),
            "pending_citation_gaps": pending_names(digests, "citation-gap"),
            "digests": digests,
        }

    def _radar_report_path(ws: Path, file: str) -> Path:
        digest_dir = (ws / "inbox" / "radar").resolve()
        target_path = (digest_dir / file).resolve()
        try:
            ok = target_path.is_relative_to(digest_dir)
        except (ValueError, AttributeError):
            ok = False
        if not ok:
            raise HTTPException(status_code=400, detail="Invalid digest path")
        if not target_path.is_file():
            raise HTTPException(status_code=404, detail=f"Digest file not found: {file}")
        return target_path

    @app.get("/api/workspace/radar/digest")
    def get_radar_digest(file: str = Query(...), workspace: Optional[str] = Query(None)) -> dict:
        from magi.radar import load_triage, parse_digest_candidates, report_status

        ws = _resolve_workspace(workspace)
        target_path = _radar_report_path(ws, file)
        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Cannot read digest: {exc}")
        cands = parse_digest_candidates(content)
        decisions = load_triage(ws, file)
        for c in cands:
            c["decision"] = decisions.get(c.get("id") or "")
        return {
            "file": file,
            "content": content,
            "status": report_status(content),
            "kind": "citation-gap" if file.endswith("-citation-gaps.md") else "digest",
            "candidates": cands,
            "triaged": sum(1 for c in cands if c["decision"]),
        }

    # ----------------------------------------------------------------------
    # Ingest queue and batch review
    # ----------------------------------------------------------------------

    @app.get("/api/workspace/ingest/queue")
    def get_ingest_queue(workspace: Optional[str] = None) -> dict:
        from magi.ingest import ledger

        ws = _resolve_workspace(workspace)
        batches = []
        for batch_id in ledger.list_batches(ws):
            items = ledger.load_batch(ws, batch_id)
            if not items:
                continue
            batches.append({
                "batch_id": batch_id,
                "items": len(items),
                "undecided": len([i for i in items if not i.decided]),
                "committed": len([i for i in items if i.committed_path]),
                "failed": len([i for i in items if i.error]),
            })
        return {
            "workspace": str(ws),
            "pending": [e._asdict() for e in ledger.pending(ws)],
            "batches": list(reversed(batches)),
        }

    @app.get("/api/workspace/ingest/batch")
    def get_ingest_batch(batch: str, workspace: Optional[str] = None) -> dict:
        from magi.ingest import ledger

        ws = _resolve_workspace(workspace)
        if batch not in ledger.list_batches(ws):
            raise HTTPException(status_code=404, detail=f"no such batch: {batch}")

        items = []
        for item in ledger.load_batch(ws, batch):
            row = item._asdict()
            # Inline a preview rather than the whole document: a reviewer is
            # deciding whether the conversion worked, not reading the paper.
            row["preview"] = ""
            if item.staged_md:
                staged = Path(item.staged_md)
                # Containment: a staged path must live under this workspace's
                # own staging area, the same guard the radar report reader uses.
                try:
                    staged.resolve().relative_to(ledger.ingest_dir(ws).resolve())
                except (ValueError, OSError):
                    row["preview"] = ""
                else:
                    if staged.is_file():
                        row["preview"] = staged.read_text(
                            encoding="utf-8", errors="replace")[:20_000]
            items.append(row)
        return {"workspace": str(ws), "batch_id": batch, "items": items,
                "undecided": len([i for i in items if not i["decision"]])}

    @app.post("/api/workspace/ingest/decide")
    def post_ingest_decide(req: IngestDecideRequest) -> dict:
        from magi.ingest import ledger

        ws = _resolve_workspace(req.workspace)
        if req.decision not in ("approve", "reject", "reset"):
            raise HTTPException(status_code=400,
                                detail=f"unknown decision: {req.decision}")
        items = {i.item_id: i for i in ledger.load_batch(ws, req.batch_id)}
        item = items.get(req.item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"no such item: {req.item_id}")

        ledger.record_decision(ws, req.batch_id, req.item_id, req.decision)

        requeued = None
        if req.decision == "reject":
            nxt = ledger.next_rung(item.route)
            if nxt:
                ledger.enqueue(ws, source_type="arxiv", value=item.source_value,
                               route=nxt, retry_of=item.item_id, title=item.title)
                requeued = nxt
        return {"item_id": req.item_id, "decision": req.decision,
                "requeued_on": requeued}

    @app.post("/api/ingest/enqueue")
    def post_ingest_enqueue(req: IngestEnqueueRequest) -> dict:
        """Add one thing to a library's queue. The browser extension's only door.

        Its whole capability is appending a line to queue.jsonl. It imports no
        subprocess, no converter, and no job manager, so it structurally cannot
        do anything else — which is why it is safe without a token on a
        loopback-only server. Everything it queues waits for a human.
        """
        from magi.ingest import ledger
        from magi.ingest.enqueue import classify, resolve_library

        if req.library:
            target, err = resolve_library(req.library)
            if err:
                raise HTTPException(status_code=404, detail=err)
        else:
            target = _resolve_workspace(None)
        if target is None:
            raise HTTPException(status_code=400, detail="no workspace to queue into")

        source_type, value = classify(req.value)
        req_id = ledger.enqueue(target, source_type=source_type, value=value,
                                library=req.library, title=req.title)
        return {"req_id": req_id, "source_type": source_type, "value": value,
                "workspace": str(target), "status": "queued",
                "pending": len(ledger.pending(target))}

    @app.post("/api/workspace/radar/review")
    def post_radar_review(req: RadarReviewRequest) -> dict:
        from magi.radar import mark_report_reviewed

        if req.action != "mark-reviewed":
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
        ws = _resolve_workspace(req.workspace)
        target = _radar_report_path(ws, req.file)
        if not mark_report_reviewed(target):
            raise HTTPException(status_code=409, detail=f"Report is not pending-review: {req.file}")
        return {"file": req.file, "status": "reviewed"}

    @app.post("/api/workspace/radar/candidate")
    def post_radar_candidate(req: RadarCandidateRequest) -> dict:
        from magi.radar import parse_digest_candidates

        ws = _resolve_workspace(req.workspace)
        target = _radar_report_path(ws, req.file)
        cands = parse_digest_candidates(target.read_text(encoding="utf-8", errors="replace"))
        if not (0 <= req.index < len(cands)):
            raise HTTPException(status_code=404, detail=f"No candidate #{req.index} in {req.file}")
        cand = cands[req.index]

        from magi.radar import record_triage

        if req.action in ("dismiss", "reset"):
            cid = cand.get("id")
            if not cid:
                raise HTTPException(status_code=409,
                                    detail="This candidate has no id to record a decision against")
            record_triage(ws, req.file, cid, req.action)
            return {"candidate": cand, "decision": None if req.action == "reset" else "dismiss"}

        if req.action == "accept-to-inbox":
            import yaml

            slug = re.sub(r"[^\w\-]+", "-", (cand["title"] or "paper").lower()).strip("-")[:60] or "paper"
            dest = ws / "inbox" / f"radar-accept-{slug}.md"
            if dest.exists():
                raise HTTPException(status_code=409, detail=f"Already accepted: {dest.name}")
            # arXiv first, S2 second: the card tells the reader to go download
            # the PDF, and a Semantic Scholar landing page is not where that is.
            url = (f"https://arxiv.org/abs/{cand['arxiv_id']}"
                   if cand["arxiv_id"] else cand["url"])
            fm = {"title": cand["title"], "type": "papers", "source": "radar",
                  "id": cand["id"], "arxiv_id": cand["arxiv_id"], "url": url,
                  "status": "to-ingest"}
            fm = {k: v for k, v in fm.items() if v is not None}
            body = ("---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
                    + "---\n\n" + f"# {cand['title']}\n\n"
                    + (f"{url}\n\n" if url else "")
                    + f"Accepted from {req.file} via WebUI radar review.\n\n"
                    # This line used to read "download the PDF/source into
                    # inbox/ and run the wiki_ingest skill" — an instruction to
                    # an agent, which one duly improvised its way through into a
                    # per-page vision transcription. A command is not an
                    # invitation to improvise.
                    + "Ingest it with:\n\n"
                    + f"    magi ingest url {url or cand['id']}\n"
                    + "    magi ingest batch-run\n\n"
                    + "Then review and approve the batch: `magi ingest batch-list`.\n")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
            if cand.get("id"):
                record_triage(ws, req.file, cand["id"], "accept")
            return {"created": f"inbox/{dest.name}", "candidate": cand, "decision": "accept"}

        if req.action == "create-issue":
            from magi.pm import _run_bd, bd_available, find_beads_root

            if not bd_available():
                raise HTTPException(status_code=503, detail="bd (Beads) is not installed")
            beads_root = find_beads_root(ws)
            if beads_root is None:
                raise HTTPException(status_code=409, detail="No beads workspace found — run 'magi pm init' first")
            title = f"[{ws.name}] Survey: {cand['title']}"[:200]
            url = (f"https://arxiv.org/abs/{cand['arxiv_id']}"
                   if cand["arxiv_id"] else (cand["url"] or ""))
            desc = (url + (f" (id {cand['id']})" if cand["id"] else "")).strip() or "radar candidate"
            proc = _run_bd(["create", "-t", "survey", title,
                            "--label", "radar", "--label", f"topic:{ws.name}",
                            "-d", desc], cwd=beads_root)
            if proc.returncode != 0:
                raise HTTPException(status_code=502, detail=f"bd create failed: {proc.stderr[-200:]}")
            if cand.get("id"):
                record_triage(ws, req.file, cand["id"], "task")
            return {"issue_created": True, "candidate": cand, "decision": "task",
                    "output": proc.stdout.strip()[-200:]}

        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    @app.get("/api/workspace/search")
    def get_workspace_search(
        q: str = Query(..., min_length=1),
        mode: str = Query("hybrid", pattern="^(hybrid|bm25|vector)$"),
        limit: int = Query(10, ge=1, le=100),
        workspace: Optional[str] = Query(None),
        scope: str = Query("auto", pattern="^(auto|local|global)$"),
        kb: Optional[str] = Query(None),
        collection: Optional[str] = Query(None),
        path: Optional[str] = Query(None),
    ) -> dict:
        # Contract note: this is a thin passthrough over retrieval.run_search —
        # the response body is byte-identical in shape to `magi search --json`
        # (and the future `magi mcp` surface). Do not reshape fields here.
        from magi.retrieval import SearchError, run_search

        ws = _resolve_workspace(workspace)
        try:
            payload = run_search(q, mode=mode, k=limit, scope=scope, kb=kb,
                                 collection=collection, path=path,
                                 topic_dir=str(ws) if ws else None)
        except SearchError as exc:
            return {"query": q, "mode": mode, "scope": kb or scope, "results": [],
                    "vector_available": False, "error": exc.msg, "hint": exc.hint}
        except Exception as exc:
            return {"query": q, "mode": mode, "scope": kb or scope, "results": [],
                    "vector_available": False, "error": str(exc)}
        payload["workspace"] = str(ws)
        return payload

    @app.get("/api/workspace/doc")
    def get_workspace_doc(
        path: Optional[str] = Query(None),
        node: Optional[str] = Query(None),
        workspace: Optional[str] = Query(None),
        kb: Optional[str] = Query(None),
    ) -> dict:
        """Raw markdown for one file in a workspace, for the preview pane.

        Addressable two ways: by workspace-relative `path` (what search hits
        carry) or by graph `node` id (what the graph views carry). `kb` names
        a registered knowledge base instead of the current workspace — search
        is federated, so half the hits in a result list live somewhere else.
        The reply is source text; rendering, math included, is the browser's.
        """
        ws = _reading_root(workspace, kb)
        meta: dict[str, Any] = {}

        if not path:
            if not node:
                raise HTTPException(status_code=400, detail="pass path= or node=")
            graph_db = ws / "output" / "graph.db"
            if not graph_db.is_file():
                raise HTTPException(
                    status_code=404,
                    detail=f"Knowledge graph database not found at {graph_db}. Run 'magi graph build' first.")
            from magi.kb import graph_browse

            conn = None
            try:
                # open_ro, not a bare connect: it registers the Unicode-aware
                # ulower() the title fallback below needs.
                conn = graph_browse.open_ro(graph_db)
                # Wikilinks inside a card carry a title, a file stem or an
                # alias — never the node id. resolve_node_id knows all four,
                # exactly as `magi graph build` did when it drew the edges.
                resolved = graph_browse.resolve_node_id(conn, node)
                row = conn.execute(
                    "SELECT id, path, title, type, summary, updated FROM nodes WHERE id = ?",
                    (resolved,)).fetchone() if resolved else None
            except sqlite3.Error as exc:
                raise HTTPException(status_code=400, detail=f"Graph lookup failed: {exc}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
            if row is None:
                raise HTTPException(status_code=404, detail=f"No graph node with id {node!r}")
            meta = {k: row[k] for k in ("id", "title", "type", "summary", "updated")}
            path = row["path"]
            if not path:
                # Tag and ghost nodes are graph-only — they have no card yet.
                raise HTTPException(
                    status_code=404,
                    detail=f"Node {node!r} has no file behind it (it is a tag or an unwritten link)")

        target = _safe_workspace_file(ws, path)
        try:
            raw = target.read_bytes()
        except OSError as exc:
            raise HTTPException(status_code=404, detail=f"Cannot read {path}: {exc}")

        truncated = len(raw) > DOC_PREVIEW_MAX_BYTES
        if truncated:
            raw = raw[:DOC_PREVIEW_MAX_BYTES]
        content = raw.decode("utf-8", errors="replace")
        stat = target.stat()
        return {
            "workspace": str(ws),
            "path": Path(path).as_posix(),
            "content": content,
            "truncated": truncated,
            "bytes": stat.st_size,
            "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "node": meta or None,
        }

    @app.get("/api/workspace/asset")
    def get_workspace_asset(
        path: str = Query(...),
        workspace: Optional[str] = Query(None),
        kb: Optional[str] = Query(None),
    ):
        """One image out of a workspace, for figures embedded in a card.

        Cards compiled from papers point at `images/fig-3.png` next to them;
        without this the preview would be a page of broken icons.
        """
        from fastapi.responses import FileResponse

        ws = _reading_root(workspace, kb)
        target = _safe_workspace_file(ws, path, suffixes=ASSET_SUFFIXES)
        media, _ = mimetypes.guess_type(target.name)
        return FileResponse(target, media_type=media or "application/octet-stream")

    @app.get("/api/workspace/graph/query")
    def query_graph_sql(
        sql: str = Query(..., min_length=1),
        workspace: Optional[str] = Query(None),
    ) -> dict:
        ws = _resolve_workspace(workspace)
        graph_db = ws / "output" / "graph.db"
        if not graph_db.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Knowledge graph database not found at {graph_db}. Run 'magi graph build' first.",
            )

        query_stripped = sql.strip()

        # Clean comments and string literals to inspect query structure safely
        cleaned = re.sub(r"--[^\n]*", " ", query_stripped)
        cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"'(?:''|[^'])*'", "''", cleaned)
        cleaned = re.sub(r'"(?:""|[^"])*"', '""', cleaned)
        cleaned_upper = cleaned.strip().upper()

        # Strict SQL whitelist protection
        allowed_prefixes = ("SELECT", "WITH", "PRAGMA", "EXPLAIN")
        if not any(cleaned_upper.startswith(p) for p in allowed_prefixes):
            raise HTTPException(
                status_code=400,
                detail="Security Guard: Only SELECT, WITH (CTE), or PRAGMA read-only queries are allowed.",
            )

        # Block modifying keywords anywhere in query outside string literals
        blocked_keywords = [
            r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
            r"\bALTER\b", r"\bCREATE\b", r"\bATTACH\b", r"\bDETACH\b",
            r"\bREPLACE\b", r"\bEXEC\b", r"\bVACUUM\b", r"\bREINDEX\b",
        ]
        for pattern in blocked_keywords:
            if re.search(pattern, cleaned_upper):
                raise HTTPException(
                    status_code=400,
                    detail="Security Guard: Data modification statements are strictly blocked.",
                )

        conn = None
        try:
            conn = sqlite3.connect(f"{graph_db.as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA query_only = ON")
            cursor.execute(query_stripped)
            rows = cursor.fetchall()
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            results = [dict(r) for r in rows]
            return {"columns": col_names, "rows": results, "results": results, "count": len(results)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"SQL Error: {exc}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @app.get("/api/workspace/graph/browse")
    def browse_graph(
        view: str = Query("overview"),
        type: Optional[str] = Query(None),
        q: Optional[str] = Query(None),
        node: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        limit: Optional[int] = Query(None),
        tags: bool = Query(False),
        workspace: Optional[str] = Query(None),
    ) -> dict:
        from magi.kb import graph_browse

        if view not in ("overview", "nodes", "links", "claims", "tags", "broken", "map"):
            raise HTTPException(status_code=400, detail=f"Unknown view: {view}")
        ws = _resolve_workspace(workspace)
        graph_db = ws / "output" / "graph.db"
        if not graph_db.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Knowledge graph database not found at {graph_db}. Run 'magi graph build' first.",
            )
        # The map view returns the whole graph, so it gets a wider clamp.
        if view == "map":
            limit = max(1, min(limit if limit is not None else 800, 2000))
        else:
            limit = max(1, min(limit if limit is not None else 50, 500))

        conn = None
        try:
            conn = graph_browse.open_ro(graph_db)
            if view == "overview":
                results: Any = graph_browse.browse_overview(conn)
            elif view == "nodes":
                results = graph_browse.browse_nodes(conn, node_type=type, q=q, limit=limit)
            elif view == "links":
                if node:
                    results = graph_browse.browse_links(conn, node)
                else:
                    # Without a node to inspect, show the busiest ones instead.
                    results = graph_browse.browse_hubs(conn, limit=limit)
            elif view == "claims":
                results = graph_browse.browse_claims(conn, status=status, q=q, limit=limit)
            elif view == "tags":
                results = graph_browse.browse_tags(conn, q=q, limit=limit)
            elif view == "map":
                results = graph_browse.browse_map(conn, include_tags=tags, limit=limit)
            else:
                results = graph_browse.browse_broken(conn, limit=limit)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=400, detail=f"Graph browse error: {exc}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        if view == "map":
            count = len(results["nodes"])
        elif isinstance(results, list):
            count = len(results)
        else:
            count = 1
        return {
            "view": view,
            "results": results,
            "count": count,
        }

    @app.get("/api/workspace/pm")
    def get_workspace_pm(workspace: Optional[str] = Query(None)) -> dict:
        from magi.pm import find_beads_root

        ws = _resolve_workspace(workspace)
        avail = bd_available()
        summary = bd_status_summary(ws) if avail else None
        root = find_beads_root(ws) if avail else None
        # The task engine names its fields `<thing>_issues`; the sync report
        # (sync.balthasar_status) renames them to bare `ready`/`open`. The
        # panel read the *renamed* names off the *raw* payload, got undefined
        # for all four, and `|| 0` turned that into a confident zero: a
        # workspace with 17 ready tasks rendered READY 0 directly under a core
        # card that said "17 ready". Emit the normalised names here so the two
        # readers of this number can no longer drift apart.
        counts = {
            "ready": (summary or {}).get("ready_issues"),
            "in_progress": (summary or {}).get("in_progress_issues"),
            "blocked": (summary or {}).get("blocked_issues"),
            "open": (summary or {}).get("open_issues"),
        }
        return {
            "workspace": str(ws),
            "task_engine_ready": avail,
            "beads_available": avail,
            # The task store lives at the nearest ancestor that holds one, so
            # every topic under a hub shares one set of counts. That is not a
            # detail the panel can leave implicit while it sits under a picker
            # naming a single workspace.
            "store_root": str(root) if root else None,
            "shared_with_siblings": bool(root and root.resolve() != ws.resolve()),
            "counts": counts,
            "summary": summary,
        }

    @app.get("/api/workspace/bib")
    def get_workspace_bib(card: Optional[str] = Query(None),
                          all: bool = Query(False),
                          workspace: Optional[str] = Query(None)) -> dict:
        from magi.kb.bib_export import _find_cards, _read_frontmatter, build_entry

        if not card and not all:
            raise HTTPException(status_code=400, detail="Pass ?card=<slug> or ?all=1")
        ws = _resolve_workspace(workspace)
        cards = _find_cards(ws, card, bool(all))
        if not cards:
            raise HTTPException(status_code=404,
                                detail=f"No reference card found for '{card or 'wiki/references/'}'")
        entries = []
        for c in cards:
            fm = _read_frontmatter(c)
            entry = build_entry(c, fm)
            entries.append({"card": c.stem, "title": fm.get("title"),
                            "year": fm.get("year"), "bibtex": entry or None})
        return {"workspace": str(ws), "entries": entries, "count": len(entries)}

    @app.get("/api/workspace/drafts")
    def get_workspace_drafts(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        drafts_dir = ws / "drafts"
        items = []
        if drafts_dir.is_dir():
            for p in sorted(drafts_dir.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
                title = None
                try:
                    head = p.read_text(encoding="utf-8", errors="replace")[:2000]
                    m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", head, re.MULTILINE)
                    if m:
                        title = m.group(1)
                    else:
                        m = re.search(r"^#\s+(.+)$", head, re.MULTILINE)
                        if m:
                            title = m.group(1)
                except OSError:
                    pass
                items.append({"name": p.name,
                              "path": str(p.relative_to(ws)).replace("\\", "/"),
                              "title": title,
                              "mtime": p.stat().st_mtime,
                              "size": p.stat().st_size})
        return {"workspace": str(ws), "drafts": items, "count": len(items)}

    # ----------------------------------------------------------------------
    # 2b. Workspace config (whitelisted fields; surgical writes)
    # ----------------------------------------------------------------------

    CONFIG_FIELDS: Dict[str, dict] = {
        "radar.min_relevance": {"type": "number", "nullable": True},
        "radar.days": {"type": "int"},
        "radar.max_candidates": {"type": "int"},
        "radar.arxiv_categories": {"type": "list"},
        "radar.seed_arxiv_ids": {"type": "list"},
        "radar.own_arxiv_ids": {"type": "list"},
        "ocr.use_mineru": {"type": "bool"},
        "models.embedding": {"type": "str"},
    }

    def _config_field_value(data: dict, dotted: str):
        cur = data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

    @app.get("/api/workspace/config")
    def get_workspace_config(workspace: Optional[str] = Query(None)) -> dict:
        import yaml

        ws = _resolve_workspace(workspace)
        cfg_path = ws / "config.yaml"
        raw = cfg_path.read_text(encoding="utf-8", errors="replace") if cfg_path.is_file() else ""
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            data = {}
        fields = [{"key": k, **spec, "value": _config_field_value(data, k)}
                  for k, spec in CONFIG_FIELDS.items()]
        return {"workspace": str(ws), "config_path": str(cfg_path),
                "exists": cfg_path.is_file(), "fields": fields, "raw": raw}

    @app.post("/api/workspace/config")
    def post_workspace_config(payload: dict = Body(...)) -> dict:
        from magi.core.config_edit import ConfigEditError, set_config_value

        key = payload.get("key")
        value = payload.get("value")
        spec = CONFIG_FIELDS.get(key or "")
        if spec is None:
            raise HTTPException(status_code=400, detail=f"Config key not editable: {key}")

        ftype = spec["type"]
        if value is None:
            if not spec.get("nullable"):
                raise HTTPException(status_code=400, detail=f"{key} cannot be null")
        elif ftype == "number" and not isinstance(value, (int, float)):
            raise HTTPException(status_code=400, detail=f"{key} expects a number")
        elif ftype == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            raise HTTPException(status_code=400, detail=f"{key} expects an integer")
        elif ftype == "bool" and not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{key} expects true/false")
        elif ftype == "str" and not isinstance(value, str):
            raise HTTPException(status_code=400, detail=f"{key} expects a string")
        elif ftype == "list":
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise HTTPException(status_code=400, detail=f"{key} expects a list of strings")

        ws = _resolve_workspace(payload.get("workspace"))
        cfg_path = ws / "config.yaml"
        try:
            set_config_value(cfg_path, key, value)
        except ConfigEditError as exc:
            raise HTTPException(status_code=400, detail=f"Config edit failed: {exc}")
        return {"key": key, "value": value, "config_path": str(cfg_path)}

    # ----------------------------------------------------------------------
    # 3. Asynchronous Jobs API
    # ----------------------------------------------------------------------

    @app.get("/api/ops")
    def list_ops_endpoint() -> dict:
        # The catalog drives ALL operation buttons in the frontend — the UI
        # holds zero op-specific knowledge beyond i18n labels.
        from magi.ui.jobs import OPS

        return {"ops": [
            {
                "op": op_id,
                "scope": spec["scope"],
                "danger": spec["danger"],
                "label_i18n": spec["label_i18n"],
                "desc_i18n": spec.get("desc_i18n"),
                # What to call this op's reach on screen; `scope` is the
                # concurrency class and is too coarse to show.
                "badge_i18n": spec.get("badge_i18n"),
                "argv": ["magi", *spec["argv"]],
                "params": sorted((spec.get("params") or {}).keys()),
            }
            for op_id, spec in OPS.items()
        ]}

    @app.post("/api/jobs")
    def create_job_endpoint(req: JobCreateRequest) -> dict:
        from magi.ui.jobs import OPS, JobConflict

        spec = OPS.get(req.op)
        if spec is None:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {req.op}")
        # Danger ops re-verify on the server: the frontend's type-to-confirm
        # box feeds this field, but the check must not live only in JS.
        if spec["danger"] and req.confirm != req.op:
            raise HTTPException(
                status_code=400,
                detail=f"Dangerous operation requires confirm='{req.op}'")

        argv = list(spec["argv"])
        declared = spec.get("params") or {}
        for pname, enabled in (req.params or {}).items():
            if pname not in declared:
                raise HTTPException(status_code=400, detail=f"Unknown param '{pname}' for {req.op}")
            if enabled:
                argv.append(declared[pname])

        ws: Optional[Path] = None
        if req.kb:
            p = Path(req.kb)
            if p.is_dir():
                ws = p.resolve()
            else:
                entry = load_registry().get("kbs", {}).get(req.kb)
                if entry:
                    ws = Path(entry["path"]).resolve()
                else:
                    raise HTTPException(status_code=404, detail=f"KB '{req.kb}' not found in registry")
        if ws is None:
            ws = _resolve_workspace(None)

        try:
            job = task_manager.create_job(command=argv, workspace=str(ws),
                                          name=req.op, op_id=req.op, scope=spec["scope"])
        except JobConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"job_id": job.id, "status": job.status, "name": job.name, "op": req.op}

    @app.get("/api/jobs")
    def list_jobs_endpoint() -> dict:
        return {"jobs": task_manager.list_jobs()}

    @app.get("/api/jobs/{job_id}")
    def get_job_endpoint(job_id: str) -> dict:
        job = task_manager.get_job(job_id)
        if not job:
            rec = task_manager.get_archived(job_id)
            if rec is not None:
                data = dict(rec)
                data["logs"] = data.pop("log_tail", [])
                return data
            raise HTTPException(status_code=404, detail="Job not found")
        data = job.to_dict()
        with job._lock:
            data["logs"] = list(job.logs)
        return data

    @app.get("/api/jobs/{job_id}/stream")
    async def stream_job_endpoint(job_id: str):
        job = task_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return StreamingResponse(
            task_manager.stream_logs(job_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job_endpoint(job_id: str) -> dict:
        success = task_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Unable to cancel job (not found or not running)")
        return {"job_id": job_id, "cancelled": True}

    # ----------------------------------------------------------------------
    # 4. Docs & Help API
    # ----------------------------------------------------------------------

    @app.get("/api/docs/readme")
    def get_readme_docs(lang: Optional[str] = Query(None)) -> dict:
        # Three-level fallback so an installed `magi ui` (uv tool / pip) still
        # has docs: repo checkout -> wheel metadata long-description ->
        # GitHub raw (online).
        readme_zh = ""
        readme_en = ""
        source = None

        candidates = []
        root = Path(__file__).resolve()
        for _ in range(5):
            root = root.parent
            candidates.append(root)
        candidates.append(Path.cwd())
        for base in candidates:
            p_zh = base / "README.md"
            # Marker for "this is the repo checkout, not a random cwd". Uses the
            # package source tree because skills/ moved inside the package.
            if p_zh.is_file() and (base / "src" / "magi").is_dir():
                readme_zh = p_zh.read_text(encoding="utf-8", errors="replace")
                p_en = base / "README_en.md"
                if p_en.is_file():
                    readme_en = p_en.read_text(encoding="utf-8", errors="replace")
                source = "repo"
                break

        if not readme_zh:
            try:
                from importlib.metadata import metadata

                payload = metadata("magi-research").get_payload()
                if payload and payload.strip():
                    readme_zh = payload
                    source = "package-metadata"
            except Exception:
                pass

        if not readme_zh:
            try:
                import urllib.request

                base_url = "https://raw.githubusercontent.com/Misaka16384/magi/main/"
                with urllib.request.urlopen(base_url + "README.md", timeout=5) as r:
                    readme_zh = r.read().decode("utf-8", errors="replace")
                source = "github"
                try:
                    with urllib.request.urlopen(base_url + "README_en.md", timeout=5) as r:
                        readme_en = r.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
            except Exception:
                pass

        lang_norm = "en" if (lang and lang.strip().lower().startswith("en")) else "zh"
        selected = readme_en if lang_norm == "en" else readme_zh
        if not selected:
            selected = readme_zh if lang_norm == "en" else readme_en

        return {
            "readme_zh": readme_zh,
            "readme_en": readme_en,
            "content": selected,
            "lang": lang_norm,
            "source": source,
        }

    @app.get("/api/docs/commands")
    def get_commands_docs() -> dict:
        from magi.cli import _COMMANDS, _GROUP_HELP
        from magi.core.cli_i18n import GROUP_HELP_ZH, command_help_zh, group_help_zh

        cmd_list = []
        for key, (module_name, prepend, help_text) in sorted(_COMMANDS.items()):
            full_cmd = "magi " + " ".join(key)
            group = key[0] if len(key) > 1 else None
            cmd_list.append({
                "key": key,
                "command": full_cmd,
                "group": group,
                "group_help": _GROUP_HELP.get(group, "") if group else "",
                "group_help_zh": group_help_zh(group),
                "module": module_name,
                "help": help_text,
                "help_zh": command_help_zh(key),
            })
        return {"commands": cmd_list, "groups": _GROUP_HELP, "groups_zh": GROUP_HELP_ZH}

    @app.get("/api/docs/guide")
    def get_guide_docs(lang: Optional[str] = Query(None)) -> dict:
        """Scenario-based operating manual shipped inside the package.

        Content and parsing both come from ``magi.guide`` — the same single
        implementation behind the ``magi guide`` command and the magi_guide
        skill, so the manual reads identically to a person here and to an
        agent in a terminal.
        """
        from magi.guide import available_langs, load_guide, normalize_lang, parse_chapters

        lang_norm = normalize_lang(lang)
        content, served = load_guide(lang_norm)

        # Chapters come from the same parser `magi guide` uses, so a deep link
        # in this tab and a chapter reference from an agent name the same thing.
        chapters = [
            {"n": c["n"], "anchor": c["anchor"], "title": c["title"], "summary": c["summary"]}
            for c in parse_chapters(content)
        ] if content else []

        return {
            "content": content,
            "lang": served,
            "requested": lang_norm,
            "available": available_langs(),
            "chapters": chapters,
            "version": magi.__version__,
        }

    # ----------------------------------------------------------------------
    # 4b. UI backgrounds (user override dir beats packaged manifest)
    # ----------------------------------------------------------------------

    _BG_VARIANTS = ("blue", "red")
    _BG_EXTS = (".webp", ".jpg", ".jpeg", ".png")

    def _load_manifest(path: Path) -> Optional[dict]:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # ValueError covers JSONDecodeError and UnicodeDecodeError alike —
            # any unreadable manifest falls back instead of 500ing.
            return None
        return data if isinstance(data, dict) else None

    @app.get("/api/ui/backgrounds")
    def get_ui_backgrounds() -> dict:
        override = _config_home() / "ui-backgrounds"

        data = _load_manifest(override / "manifest.json")
        if data is not None:
            return {**data, "source": "user", "base_url": "/ui-bg/"}

        # No manifest: bare image files in blue/ or red/ still count as a
        # user override, with dimensions unknown.
        variants: Dict[str, list] = {}
        for variant in _BG_VARIANTS:
            vdir = override / variant
            if not vdir.is_dir():
                continue
            names = sorted(p.name for p in vdir.iterdir()
                           if p.is_file() and p.suffix.lower() in _BG_EXTS)
            if names:
                variants[variant] = [
                    {"file": f"{variant}/{name}", "w": None, "h": None, "aspect": None}
                    for name in names
                ]
        if variants:
            return {"variants": variants, "source": "user", "base_url": "/ui-bg/"}

        data = _load_manifest(_get_static_dir() / "backgrounds" / "manifest.json")
        if data is not None:
            return {**data, "source": "bundled", "base_url": "/backgrounds/"}

        return {"variants": {}, "source": "none", "base_url": ""}

    # ----------------------------------------------------------------------
    # 5. Static Files Mounting
    # ----------------------------------------------------------------------

    # Mounted unconditionally with check_dir=False: /api/ui/backgrounds
    # resolves the override dir per request, so the mount must serve files
    # dropped in AFTER server start too. A missing dir just 404s.
    ui_bg_dir = _config_home() / "ui-backgrounds"
    app.mount(
        "/ui-bg",
        RevalidatingStatic(directory=str(ui_bg_dir), check_dir=False),
        name="ui-bg",
    )

    static_dir = _get_static_dir()
    if static_dir.is_dir():
        app.mount(
            "/", RevalidatingStatic(directory=str(static_dir), html=True), name="static"
        )

    return app
