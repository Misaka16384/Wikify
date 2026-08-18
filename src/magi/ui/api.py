"""FastAPI routes and application factory for MAGI WebUI."""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib.resources
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import magi
from magi.core.workspace import find_hub_root, find_workspace_root
from magi.kb.detect_uncompiled import find_uncompiled
from magi.kb_registry import (
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
        doc = doctor_rows()
        doc_ok = all(ok for name, ok, _ in doc if name in ("magi", "python"))
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
        rows = []
        for name, entry in sorted(data.get("kbs", {}).items()):
            p = Path(entry["path"])
            idx = p / "output" / "index.db"
            graph_db = p / "output" / "graph.db"
            is_cur = current is not None and p.resolve() == current.resolve()

            # Attempt a quick report if workspace exists
            sync_info = None
            if p.is_dir() and (p / "wiki").is_dir():
                try:
                    sync_info = build_report(p)
                except Exception:
                    pass

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
    def get_doctor() -> dict:
        rows = doctor_rows()
        legacy = find_legacy_copies()
        return {
            "doctor": [{"tool": name, "ok": ok, "detail": detail} for name, ok, detail in rows],
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

        from magi.radar import pending_names, scan_reports

        digests = []
        for r in scan_reports(ws):
            entry = dict(r)
            entry["path"] = str(Path(r["path"]).relative_to(ws)).replace("\\", "/")
            digests.append(entry)

        return {
            "workspace": str(ws),
            "seen_total": seen_count,
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
        from magi.radar import parse_digest_candidates

        ws = _resolve_workspace(workspace)
        target_path = _radar_report_path(ws, file)
        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Cannot read digest: {exc}")
        return {
            "file": file,
            "content": content,
            "status": "pending-review" if "status: pending-review" in content else "reviewed",
            "kind": "citation-gap" if file.endswith("-citation-gaps.md") else "digest",
            "candidates": parse_digest_candidates(content),
        }

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

        if req.action == "accept-to-inbox":
            import yaml

            slug = re.sub(r"[^\w\-]+", "-", (cand["title"] or "paper").lower()).strip("-")[:60] or "paper"
            dest = ws / "inbox" / f"radar-accept-{slug}.md"
            if dest.exists():
                raise HTTPException(status_code=409, detail=f"Already accepted: {dest.name}")
            url = cand["url"] or (f"https://arxiv.org/abs/{cand['arxiv_id']}" if cand["arxiv_id"] else None)
            fm = {"title": cand["title"], "type": "papers", "source": "radar",
                  "id": cand["id"], "arxiv_id": cand["arxiv_id"], "url": url,
                  "status": "to-ingest"}
            fm = {k: v for k, v in fm.items() if v is not None}
            body = ("---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
                    + "---\n\n" + f"# {cand['title']}\n\n"
                    + (f"{url}\n\n" if url else "")
                    + f"Accepted from {req.file} via WebUI radar review — "
                      "download the PDF/source into inbox/ and run the wiki_ingest skill.\n")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
            return {"created": f"inbox/{dest.name}", "candidate": cand}

        if req.action == "create-issue":
            from magi.pm import _run_bd, bd_available, find_beads_root

            if not bd_available():
                raise HTTPException(status_code=503, detail="bd (Beads) is not installed")
            beads_root = find_beads_root(ws)
            if beads_root is None:
                raise HTTPException(status_code=409, detail="No beads workspace found — run 'magi pm init' first")
            title = f"[{ws.name}] Survey: {cand['title']}"[:200]
            url = cand["url"] or (f"https://arxiv.org/abs/{cand['arxiv_id']}" if cand["arxiv_id"] else "")
            desc = (url + (f" (id {cand['id']})" if cand["id"] else "")).strip() or "radar candidate"
            proc = _run_bd(["create", "-t", "survey", title,
                            "--label", "radar", "--label", f"topic:{ws.name}",
                            "-d", desc], cwd=beads_root)
            if proc.returncode != 0:
                raise HTTPException(status_code=502, detail=f"bd create failed: {proc.stderr[-200:]}")
            return {"issue_created": True, "candidate": cand,
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

    @app.get("/api/workspace/pm")
    def get_workspace_pm(workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        avail = bd_available()
        summary = bd_status_summary(ws) if avail else None
        return {
            "workspace": str(ws),
            "task_engine_ready": avail,
            "beads_available": avail,
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
        root = Path(__file__).parent.parent.parent.parent
        readme_zh = ""
        readme_en = ""
        p_zh = root / "README.md"
        p_en = root / "README_en.md"
        if p_zh.is_file():
            readme_zh = p_zh.read_text(encoding="utf-8", errors="replace")
        if p_en.is_file():
            readme_en = p_en.read_text(encoding="utf-8", errors="replace")

        # Fallback to current working directory if not found in root
        if not readme_zh:
            cwd_zh = Path.cwd() / "README.md"
            if cwd_zh.is_file():
                readme_zh = cwd_zh.read_text(encoding="utf-8", errors="replace")
        if not readme_en:
            cwd_en = Path.cwd() / "README_en.md"
            if cwd_en.is_file():
                readme_en = cwd_en.read_text(encoding="utf-8", errors="replace")

        lang_norm = "en" if (lang and lang.strip().lower().startswith("en")) else "zh"
        selected = readme_en if lang_norm == "en" else readme_zh
        if not selected:
            selected = readme_zh if lang_norm == "en" else readme_en

        return {
            "readme_zh": readme_zh,
            "readme_en": readme_en,
            "content": selected,
            "lang": lang_norm,
        }

    @app.get("/api/docs/commands")
    def get_commands_docs() -> dict:
        from magi.cli import _COMMANDS, _GROUP_HELP

        cmd_list = []
        for key, (module_name, prepend, help_text) in sorted(_COMMANDS.items()):
            full_cmd = "magi " + " ".join(key)
            group = key[0] if len(key) > 1 else None
            cmd_list.append({
                "key": key,
                "command": full_cmd,
                "group": group,
                "group_help": _GROUP_HELP.get(group, "") if group else "",
                "module": module_name,
                "help": help_text,
            })
        return {"commands": cmd_list, "groups": _GROUP_HELP}

    # ----------------------------------------------------------------------
    # 5. Static Files Mounting
    # ----------------------------------------------------------------------

    static_dir = _get_static_dir()
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
