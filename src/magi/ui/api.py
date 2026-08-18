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
from fastapi.middleware.cors import CORSMiddleware
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


class JobCreateRequest(BaseModel):
    command: List[str] = Field(..., min_length=1)
    workspace: Optional[str] = None
    name: Optional[str] = None


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


def create_app() -> FastAPI:
    app = FastAPI(
        title="MAGI Research Workspace WebUI",
        version=magi.__version__,
        description="Local inspection, triage, and ops dashboard for the MAGI research workspace CLI.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


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

        digest_dir = ws / "inbox" / "radar"
        digests: list[dict] = []
        if digest_dir.is_dir():
            for p in sorted(digest_dir.glob("*-digest*.md"), reverse=True):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    status = "pending-review" if "status: pending-review" in text else "reviewed"
                    digests.append({
                        "name": p.name,
                        "path": str(p.relative_to(ws)).replace("\\", "/"),
                        "status": status,
                        "mtime": p.stat().st_mtime,
                        "size": p.stat().st_size,
                    })
                except Exception:
                    continue

        return {
            "workspace": str(ws),
            "seen_total": seen_count,
            "pending_digests": [d["name"] for d in digests if d["status"] == "pending-review"],
            "digests": digests,
        }

    @app.get("/api/workspace/radar/digest")
    def get_radar_digest(file: str = Query(...), workspace: Optional[str] = Query(None)) -> dict:
        ws = _resolve_workspace(workspace)
        digest_dir = (ws / "inbox" / "radar").resolve()
        target_path = (digest_dir / file).resolve()

        try:
            if not target_path.is_relative_to(digest_dir):
                raise HTTPException(status_code=400, detail="Invalid digest path")
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid digest path")

        if not target_path.is_file():
            raise HTTPException(status_code=404, detail=f"Digest file not found: {file}")

        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
            return {"file": file, "content": content}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Cannot read digest: {exc}")

    @app.get("/api/workspace/search")
    def get_workspace_search(
        q: str = Query(..., min_length=1),
        mode: str = Query("hybrid", pattern="^(hybrid|bm25|vector)$"),
        limit: int = Query(10, ge=1, le=100),
        workspace: Optional[str] = Query(None),
    ) -> dict:
        ws = _resolve_workspace(workspace)
        idx_path = ws / "output" / "index.db"
        if not idx_path.is_file():
            return {
                "workspace": str(ws),
                "query": q,
                "mode": mode,
                "results": [],
                "vector_available": False,
                "error": "No index found at output/index.db. Run 'magi index' first.",
            }

        conn = None
        try:
            from magi.retrieval import Embedder, _fts_query, _search_one_db, open_db, RRF_K
            import argparse

            args = argparse.Namespace(collection=None, mode=mode, query=q, k=limit)
            o = open_db(idx_path)
            if not o:
                return {"results": [], "vector_available": False, "error": "Index missing"}

            conn, vec_loaded = o
            embedder = Embedder()
            qvec = embedder.embed(q) if mode in ("hybrid", "vector") and embedder.available else None
            n = max(limit * 3, 20)

            ranks, bh, vh, vused = _search_one_db(conn, vec_loaded, args, qvec, n)
            scores = {cid: sum(1.0 / (RRF_K + r) for r in legs.values()) for cid, legs in ranks.items()}
            top = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]

            results = []
            for cid, score in top:
                row = conn.execute(
                    "SELECT path, collection, heading, start_line, end_line, content FROM chunks WHERE id=?",
                    (cid,),
                ).fetchone()
                if not row:
                    continue
                path, collection, heading, start_line, end_line, content = row
                legs = ranks.get(cid, {})
                results.append({
                    "id": cid,
                    "path": path,
                    "collection": collection,
                    "heading": heading,
                    "start_line": start_line,
                    "end_line": end_line,
                    "score": round(score, 4),
                    "bm25_rank": legs.get("bm25"),
                    "vector_rank": legs.get("vector"),
                    "content": content,
                })
            return {
                "workspace": str(ws),
                "query": q,
                "mode": mode,
                "results": results,
                "bm25_hits": bh,
                "vector_hits": vh,
                "vector_available": vused or (embedder.available and vec_loaded),
            }
        except Exception as exc:
            return {"results": [], "vector_available": False, "error": str(exc)}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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

    # ----------------------------------------------------------------------
    # 3. Asynchronous Jobs API
    # ----------------------------------------------------------------------

    @app.post("/api/jobs")
    def create_job_endpoint(req: JobCreateRequest) -> dict:
        ws = str(_resolve_workspace(req.workspace))
        job = task_manager.create_job(command=req.command, workspace=ws, name=req.name)
        return {"job_id": job.id, "status": job.status, "name": job.name}

    @app.get("/api/jobs")
    def list_jobs_endpoint() -> dict:
        return {"jobs": task_manager.list_jobs()}

    @app.get("/api/jobs/{job_id}")
    def get_job_endpoint(job_id: str) -> dict:
        job = task_manager.get_job(job_id)
        if not job:
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
