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
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import magi
from magi.core.workspace import (
    INBOX_NON_SOURCES,
    find_workspace_root,
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
    edit_registry,
    edit_settings,
    load_registry,
    load_settings,
    register_kb,
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


class ZoteroImportRequest(BaseModel):
    collection_id: Optional[int] = None
    tag: Optional[str] = None
    keys: Optional[List[str]] = None
    all: bool = False
    workspace: Optional[str] = None


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


class TaskActionRequest(BaseModel):
    """One whitelisted action on one issue.

    Same shape of guarantee as the ops table: the action name arrives off the
    wire, so the set of things it can name is closed and lives in pm.py beside
    the `bd` calls it maps to.
    """

    task_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    workspace: Optional[str] = None


class FeatureRequest(BaseModel):
    """Turn one optional feature on or off, machine-wide.

    Must live at module scope: `from __future__ import annotations` turns the
    endpoint's `req: FeatureRequest` into a string, and FastAPI resolves it
    against this module's globals. Defined inside create_app() it is not
    found, and the parameter quietly becomes a query string instead of a body.
    """

    key: str = Field(..., min_length=1)
    enabled: bool
    #: "feature" flips one of MAGI's own workflows; "tool" only records
    #: whether an external tool is wanted, so the doctor stops raising it.
    kind: str = "feature"


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

def _upload_suffixes() -> set:
    """Exactly what an ingest route can handle, asked rather than restated.

    A hand-written list here accepted `.zip` and `.ltx`, which no route reads:
    the file would land in `inbox/`, be skipped by every pass forever, and read
    to whoever uploaded it exactly like the upload having failed silently.
    """
    from magi.ingest import routing

    return set(routing.TEXT_SUFFIXES) | set(routing.TEX_SUFFIXES) | {".pdf"}


UPLOAD_SUFFIXES = _upload_suffixes()

# A local PDF is routinely tens of megabytes and occasionally a few hundred.
# The cap exists so a mistake is refused rather than filling a disk.
UPLOAD_MAX_BYTES = 512 * 1024 * 1024


def upload_suffix(name: str) -> str:
    lower = name.lower()
    return ".tar.gz" if lower.endswith(".tar.gz") else os.path.splitext(lower)[1]


def safe_upload_name(raw: str) -> str:
    """A filename that can only ever name a file directly inside inbox/.

    Everything structural is stripped rather than escaped: take the last
    path-ish component under either separator, drop anything that is not a
    plain name character, and refuse the results that are still not a name.
    `..`, absolute paths, drive letters, NTFS streams and reserved device
    names all end here rather than being passed to `open()` and reasoned about
    later.
    """
    name = str(raw).replace("\\", "/").split("/")[-1].strip()
    # `\w` is Unicode-aware, so a paper called 拓扑序.pdf keeps its name. An
    # ASCII allow-list here renamed every non-Latin document to underscores,
    # which is not sanitising, it is losing the title.
    name = re.sub(r"[^\w.+\- ]", "_", name).strip(". ")
    if not name or set(name) <= {".", "_", " "}:
        raise HTTPException(status_code=400, detail="unusable filename")
    if name.split(".")[0].upper() in {
            "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
            "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3",
            "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}:
        name = "_" + name
    # Trim the stem, never the suffix: a plain `name[:180]` truncated
    # `<176 a's>.pdf` to `<180 a's>` and handed on a document with no
    # extension, which every router downstream reads as "no route for this".
    suffix = upload_suffix(name)
    stem = name[:len(name) - len(suffix)] if suffix else name
    return (stem[:180 - len(suffix)] or "upload") + suffix


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
    directory has to be a MAGI workspace or a registered library, and
    not merely a path someone typed into the query string.
    """
    if kb and kb != "local":
        return _kb_root(kb)
    root = _resolve_workspace(workspace)
    if is_topic_root(root):
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


def _shutdown_this_server() -> None:
    """Stop this server a moment from now, so the HTTP reply gets out first.

    SIGINT to our own process rather than ``os._exit``: uvicorn already knows
    how to unwind on it, and a dashboard that is being replaced should still
    close its files on the way out — those are the very files the upgrade is
    about to overwrite.

    Module level, not a closure inside ``create_app``, for one blunt reason: a
    test that exercises the upgrade endpoint would otherwise send this signal
    to the test runner. It did, once.
    """
    import os
    import signal
    import threading

    def stop() -> None:
        time.sleep(1.0)
        try:
            if os.name == "nt":
                os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)
            else:
                os.kill(os.getpid(), signal.SIGINT)
        except Exception:  # noqa: BLE001
            os._exit(0)

    threading.Thread(target=stop, daemon=True).start()


def _review_host_names() -> list:
    """Hosts a review can actually be sent to, from the one host table.

    Read at call time rather than hard-coded: a list kept by hand here went on
    offering a CLI that had been retired, and the dropdown was the last place
    anybody looked.
    """
    try:
        from magi import review

        return list(review.host_names())
    except Exception:
        return []


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
            "registered_kbs_count": len(kbs),
            "doctor_ok": doc_ok,
            "active_jobs_count": len(active_jobs),
        }

    @app.get("/api/update")
    def get_update(refresh: bool = Query(False)) -> dict:
        """Is there a newer release, and what would install it.

        By default this answers from the cache — the same one the CLI notice
        reads — so a page load never waits on pypi.org. `?refresh=1` is the
        button, and it accepts the wait because somebody asked for it.
        """
        from magi import update

        if refresh:
            latest = update.fetch_latest()
            if latest is not None:
                update.write_cache(latest)
            checked = latest is not None
        else:
            update.refresh_in_background()
            cached = update.read_cache()
            latest = cached.get("latest")
            latest = latest if isinstance(latest, str) else None
            checked = bool(cached)

        how = update.detect_install()
        return {
            "installed": magi.__version__,
            "latest": latest,
            # "could not look" is not "nothing newer": the page must be able to
            # tell the two apart, or a permanently offline machine reads as
            # permanently up to date.
            "checked": checked,
            "update_available": bool(latest and update.is_newer(latest, magi.__version__)),
            "install_method": how.kind,
            "command": " ".join(how.command) if how.command else "",
            "note": how.note,
            "can_apply": bool(how.command),
        }

    @app.get("/api/update/result")
    def get_update_result() -> dict:
        """What the last upgrade did. Written by a process nobody was watching.

        The helper runs after this server has exited, so this file is the only
        channel its outcome has. The page reads it when it comes back up.
        """
        from magi import update

        return update.read_result()

    @app.post("/api/update/result/clear")
    def clear_update_result() -> dict:
        from magi import update

        update.clear_result()
        return {"cleared": True}

    @app.post("/api/update/apply")
    def apply_update() -> dict:
        """Upgrade MAGI, by handing the job to something that outlives us.

        The dashboard cannot upgrade the package it is running from. On Windows
        this process holds its own venv's ``python.exe`` and every loaded
        ``.pyd`` open, so pipx or uv cannot replace them: the upgrade fails
        partway and leaves a half-written install — in front of somebody whose
        page has just gone blank, because the server was the thing being
        replaced.

        So: spawn a detached helper, tell it our pid and how to start us again,
        and shut down. It waits for us to go, upgrades, relaunches the dashboard
        on the same address, and writes the outcome where the new server can
        read it back. The page polls until it answers again.
        """
        import os

        from magi import update

        how = update.detect_install()
        if how.command is None:
            raise HTTPException(
                status_code=400,
                detail=how.note or "this install cannot be upgraded automatically")

        relaunch = [sys.executable, "-m", "magi", "ui", "--no-open",
                    "--host", str(getattr(app.state, "ui_host", "127.0.0.1")),
                    "--port", str(getattr(app.state, "ui_port", 8737))]

        update.clear_result()
        if not update.spawn_detached_upgrade(wait_pid=os.getpid(),
                                             relaunch=relaunch):
            raise HTTPException(status_code=500,
                                detail="could not start the upgrade helper")

        # Only now. The helper is already waiting on this pid, so a shutdown
        # that fails to happen is a stuck upgrade rather than a lost one — it
        # gives up after a minute and says so, instead of upgrading underneath
        # a process that is still running.
        _shutdown_this_server()
        return {"started": True, "command": " ".join(how.command),
                "relaunch": " ".join(relaunch),
                "reopen": f"http://{getattr(app.state, 'ui_host', '127.0.0.1')}:"
                          f"{getattr(app.state, 'ui_port', 8737)}"}

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
        with edit_registry() as data:
            if name not in data.get("kbs", {}):
                raise HTTPException(status_code=404,
                                    detail=f"KB '{name}' not found in registry")
            del data["kbs"][name]
        return {"name": name, "deleted": True}

    @app.get("/api/features")
    def get_features() -> dict:
        """What is turned on, and what a button could honestly do about it.

        Two lists, kept apart because only one of them is actionable from here.
        `features` are MAGI's own workflows: a switch, and for task tracking a
        dependency MAGI installs itself. `tools` are other people's software —
        MAGI cannot install any of them, so `can_install` is false and `url` is
        the only useful thing a button has to offer. Saying otherwise on screen
        would be a button that cannot keep its promise.

        Machine-wide, both of them: none of this is per-workspace, which is why
        there is no workspace parameter to pass.
        """
        import shutil as _shutil

        from magi.features import FEATURES, feature_enabled
        from magi.setup_cmd import MINERU_URL, OPTIONAL_TOOLS, wanted_optionals

        wanted = wanted_optionals()
        feats = []
        for f in FEATURES:
            feats.append({
                "key": f.key,
                "label": f.label,
                "what": f.what,
                "enabled": feature_enabled(f.key),
                "needs": f.needs or None,
                "needs_installed": (not f.needs) or bool(_shutil.which(f.needs)),
                "can_install": f.magi_installs,
                # The op a "turn it on" button should run once enabled. None
                # means flipping the switch is the whole job.
                "op": "install-tasks" if f.key == "tasks" else None,
            })

        tools = []
        for t in OPTIONAL_TOOLS:
            tools.append({
                "key": t.key,
                "label": t.label,
                "unlocks": t.unlocks,
                "installed": bool(_shutil.which(t.binary)),
                # Absent means never asked, which reads as wanted.
                "wanted": bool(wanted.get(t.key, True)),
                "url": t.url,
                "hint": t.install_hint or None,
                "can_install": False,
                "op": "pull-models" if t.key == "ollama" else None,
            })
        tools.append({
            "key": "mineru", "label": "MinerU",
            "unlocks": "cloud PDF conversion, strong on formulas and layout",
            # A hosted service, not a binary: "installed" is not a question you
            # can ask of it, so it reports on the token instead.
            "installed": None,
            "wanted": bool(wanted.get("mineru", False)),
            "url": MINERU_URL,
            "hint": "sign up, then put the token in config.yaml under "
                    "ocr.mineru_api_token",
            "can_install": False, "op": None,
        })
        return {"features": feats, "tools": tools}

    @app.post("/api/features")
    def post_feature(req: FeatureRequest) -> dict:
        """Turn a feature on/off, or record whether a tool is wanted.

        Writes to the machine-wide settings file, not a workspace — the same
        file `magi setup` writes. Installing anything is a separate, explicit
        step: this only ever flips a flag.
        """
        from magi.features import FEATURE_KEYS, set_feature
        from magi.setup_cmd import OPTIONAL_TOOLS

        if req.kind == "feature":
            if req.key not in FEATURE_KEYS:
                raise HTTPException(status_code=404,
                                    detail=f"Unknown feature: {req.key}")
            set_feature(req.key, req.enabled)
            return {"key": req.key, "enabled": req.enabled, "kind": "feature"}

        if req.kind == "tool":
            known = {t.key for t in OPTIONAL_TOOLS} | {"mineru"}
            if req.key not in known:
                raise HTTPException(status_code=404,
                                    detail=f"Unknown tool: {req.key}")
            with edit_settings() as data:
                chosen = dict(data.get("optional_features") or {})
                chosen[req.key] = bool(req.enabled)
                data["optional_features"] = chosen
            return {"key": req.key, "enabled": req.enabled, "kind": "tool"}

        raise HTTPException(status_code=400, detail=f"Unknown kind: {req.kind}")

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

    # The v2 surface — map, feed, threads, decisions, the dump — lives in its
    # own module. It is a different kind of route from the rest of this file:
    # everything there is derived from `threads/` on every request, and none of
    # it decides anything the CLI does not already decide.
    #
    # It gets the *checking* resolver. Its write routes create files, and
    # `_resolve_workspace` validates nothing — a path typed into a request body
    # would otherwise become an `inbox/` and a `decisions.md` in any directory
    # this process can write to.
    from magi.ui import v2 as v2_routes

    def _v2_workspace(workspace: Optional[str]) -> Path:
        return _reading_root(workspace, None)

    v2_routes.register(app, _v2_workspace)

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
        # The same order the CLI shows, from the same function. Two renderings
        # of one queue that disagree about which item is most urgent is the
        # drift this codebase keeps paying for elsewhere.
        ordered = ledger.review_order(ledger.load_batch(ws, batch))
        for item in ordered:
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
        # Counted off the items, not off the dicts they were flattened into:
        # `BatchItem.decided` asks whether the decision is one of the two words
        # that mean something, and `not row["decision"]` only agrees with that
        # while nothing has ever written a third value.
        return {"workspace": str(ws), "batch_id": batch, "items": items,
                "undecided": len(ledger.undecided(ordered))}

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
            # The CLI's function, not a second copy of it. This endpoint used
            # to inline the enqueue with source_type hardcoded to "arxiv".
            requeued = ledger.requeue_next_rung(ws, item)
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
        from magi.ingest.enqueue import classify, clean_title, resolve_library

        if req.library:
            target, err = resolve_library(req.library)
            if err:
                raise HTTPException(status_code=404, detail=err)
        else:
            # Omitting the library is fine when the server was started inside a
            # workspace — that is unambiguous, and every other endpoint reads
            # an unspecified workspace the same way.
            #
            # It is not fine when it was not. `_resolve_workspace` then falls
            # through to bare `Path.cwd()`, so the paper would be filed into
            # whatever directory `magi ui` happened to be launched in — which
            # is what a browser extension whose library picker failed to load
            # used to do, silently. A paper in the wrong library is worse than
            # one that was never queued: it is not lost, it is somewhere else,
            # and nobody looks there.
            target = find_workspace_root()
            if target is None:
                known = sorted(load_registry().get("kbs", {}))
                raise HTTPException(
                    status_code=400,
                    detail="this server was not started inside a workspace, so "
                           "there is no default — name the library to queue "
                           "into: " + (", ".join(known) if known
                                       else "none are registered"))
        if target is None:
            raise HTTPException(status_code=400, detail="no workspace to queue into")

        source_type, value = classify(req.value)
        # The browser sends the tab's title verbatim — the extension parses
        # nothing on purpose — so arXiv's "[2410.11942] " prefix arrives with
        # it. Cleaning it here keeps that rule in one place, shared with the
        # CLI path.
        # Ask before appending so the answer can be honest. `enqueue` is
        # idempotent for anything still waiting, and a caller told "queued"
        # when nothing was queued is worse off than one told nothing at all —
        # the duplicate it was trying to avoid is at least visible.
        already = ledger.find_pending(target, source_type, value)
        req_id = ledger.enqueue(target, source_type=source_type, value=value,
                                library=req.library, title=clean_title(req.title))
        return {"req_id": req_id, "source_type": source_type, "value": value,
                "workspace": str(target),
                "status": "already-queued" if already else "queued",
                "pending": len(ledger.pending(target))}

    @app.post("/api/ingest/upload")
    async def post_ingest_upload(
        request: Request,
        name: str = Query(..., description="the file's own name, no path"),
        workspace: Optional[str] = Query(None),
    ) -> dict:
        """Put one local document into a workspace's `inbox/`. Nothing else.

        The WebUI had no way to get a file off the reader's own disk. Every
        ingest door it did have took an identifier — a URL, a DOI, an arXiv id
        — so someone holding a PDF that is not on arXiv, which is most PDFs,
        had no path into their library at all without opening a terminal. The
        two surfaces meant for feeding a library were the two that could not.

        Deliberately as small as the enqueue door next to it: this writes a
        file and does not import a converter, a subprocess or the job manager,
        so a loopback server exposes no more than "a file can appear in
        inbox/". Getting it *out* of inbox/ is a separate, visible step.

        Raw bytes rather than multipart, because multipart would mean adding
        `python-multipart` to everyone's install for one endpoint, and a
        browser can send a File as a fetch body as it stands.
        """
        ws = _resolve_workspace(workspace)
        if not (ws / "inbox").is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"{ws} is not a MAGI workspace (no inbox/) — pick one first")

        filename = safe_upload_name(name)
        suffix = upload_suffix(filename)
        if suffix not in UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"no ingest route for '{suffix or filename}' — accepted: "
                       + ", ".join(sorted(UPLOAD_SUFFIXES)))

        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail="file is too large")

        inbox = ws / "inbox"
        dest = inbox / filename
        # inbox/ is ORIGINAL. Landing on a name that is already there would
        # destroy a document waiting to be ingested, so take the next free one
        # and say which it was.
        # Not `dest.stem`: pathlib strips only the last suffix, so a second
        # `paper.tar.gz` became `paper.tar-2.tar.gz`. `safe_upload_name` above
        # already slices compound suffixes correctly — the two places in this
        # function that take a name apart have to agree about where it ends.
        stem = filename[:len(filename) - len(suffix)] if suffix else filename
        n = 2
        while dest.exists():
            dest = inbox / f"{stem}-{n}{suffix}"
            n += 1

        # Stream to a temp file in the same directory and rename: a connection
        # that dies half way must not leave a truncated PDF looking like a
        # document ready to convert.
        tmp = inbox / f".upload_{os.getpid()}_{dest.name}"
        written = 0
        try:
            with open(tmp, "wb") as fh:
                async for chunk in request.stream():
                    written += len(chunk)
                    if written > UPLOAD_MAX_BYTES:
                        raise HTTPException(status_code=413, detail="file is too large")
                    fh.write(chunk)
            if not written:
                raise HTTPException(status_code=400, detail="empty upload")
            os.replace(tmp, dest)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise

        return {"workspace": str(ws), "path": str(dest),
                "name": dest.name, "bytes": written,
                "renamed": dest.name != filename,
                "inbox_pending": sum(1 for p in inbox.iterdir() if p.is_file()
                                     and p.name not in INBOX_NON_SOURCES
                                     and not p.name.startswith("."))}

    def _zotero_data_dir():
        """The Zotero library, or a 409 carrying the CLI's own explanation.

        This calls the CLI's resolver rather than restating its rules. The
        first version restated them and got both halves wrong while carrying a
        docstring claiming parity: it accepted a stored setting on
        `Path(chosen).is_dir()` alone, where the CLI requires `zotero.sqlite`
        to actually be in there, and it silently picked a lone candidate —
        which the CLI refuses to do, for a reason written down beside the
        refusal: a machine with a live library and an abandoned sync folder is
        ordinary, and importing the frozen one looks exactly like success.

        A claim of parity is worth less than an import.
        """
        from magi.ingest.zotero_import import _chosen_data_dir

        data_dir, err = _chosen_data_dir(None)
        if data_dir is None:
            raise HTTPException(status_code=409, detail=err)
        return data_dir

    @app.get("/api/zotero/collections")
    def get_zotero_collections() -> dict:
        """The Zotero folder tree, for picking one to import.

        Zotero import was CLI-only, which made it the one source of papers the
        dashboard could not touch — and it is the source most people's papers
        are already in.
        """
        from magi.ingest.zotero import list_collections

        data_dir = _zotero_data_dir()
        try:
            cols = list_collections(data_dir)
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"could not read the Zotero library: {exc}")
        return {"data_dir": str(data_dir), "collections": cols}

    @app.post("/api/zotero/import")
    def post_zotero_import(req: ZoteroImportRequest) -> dict:
        """Queue a Zotero selection. Queues only — nothing is fetched here.

        Same door every other source uses: what this writes is queue entries a
        human still has to approve, so the panel's existing convert → approve →
        commit flow applies unchanged.
        """
        from magi.ingest import ledger
        from magi.ingest.zotero import read_items
        from magi.ingest.zotero_import import plan_routes

        ws = _resolve_workspace(req.workspace)
        if not (ws / "output").is_dir() and not (ws / "wiki").is_dir():
            raise HTTPException(status_code=400,
                                detail=f"{ws} is not a MAGI workspace")
        if req.collection_id is None and not req.tag and not req.keys and not req.all:
            raise HTTPException(
                status_code=400,
                detail="name what to import: a collection, a tag, some item keys, "
                       "or all=true for the whole library")

        data_dir = _zotero_data_dir()
        try:
            items = read_items(data_dir, collection_id=req.collection_id,
                               tag=req.tag, keys=req.keys or None)
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"could not read the Zotero library: {exc}")

        # The DOI->arXiv lookup the CLI does is a live Semantic Scholar call.
        # A click in a dashboard should not silently become a network round
        # trip of unpredictable length, so the WebUI queues on what the library
        # already knows and lets `batch-run` resolve the rest.
        plan, skipped = plan_routes(items)

        queued = []
        for item, source_type, value in plan:
            already = ledger.find_pending(ws, source_type, value)
            req_id = ledger.enqueue(ws, source_type=source_type, value=value,
                                    title=item.title)
            queued.append({"req_id": req_id, "title": item.title,
                           "source_type": source_type, "value": value,
                           "status": "already-queued" if already else "queued"})

        by_route: Dict[str, int] = {}
        for q in queued:
            by_route[q["source_type"]] = by_route.get(q["source_type"], 0) + 1
        return {"workspace": str(ws), "queued": queued, "by_route": by_route,
                "skipped": [i.title for i in skipped],
                "pending": len(ledger.pending(ws))}

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

        if req.action in ("accept-to-inbox", "queue"):
            # Accepting used to write `inbox/radar-accept-<slug>.md` — a stub
            # whose body was a paragraph of instructions telling somebody to go
            # and run `magi ingest url`. Nothing ran them. What did happen is
            # that `magi ingest auto` routes any .md in inbox/ to `add`, so the
            # note got filed into `raw/notes/` as a document: counted by
            # `magi wiki uncompiled`, indexed by `magi search`, and reported as
            # part of the library. Accepting ten candidates manufactured ten
            # empty papers whose entire content was a request to fetch the real
            # one.
            #
            # A radar candidate is an arXiv id or a URL, which is exactly what
            # the queue takes — the same door the browser extension and the
            # upload button use. So queue it, and let the pipeline fetch,
            # convert and gate it like anything else.
            from magi.ingest import ledger
            from magi.ingest.enqueue import classify, clean_title

            value = (f"arXiv:{cand['arxiv_id']}" if cand["arxiv_id"]
                     else (cand["url"] or cand["id"]))
            if not value:
                raise HTTPException(
                    status_code=409,
                    detail="This candidate carries no arXiv id, URL or id to queue")
            source_type, resolved = classify(value)
            already = ledger.find_pending(ws, source_type, resolved)
            req_id = ledger.enqueue(ws, source_type=source_type, value=resolved,
                                    title=clean_title(cand["title"]))
            if cand.get("id"):
                record_triage(ws, req.file, cand["id"], "accept")
            return {"req_id": req_id, "source_type": source_type, "value": resolved,
                    "status": "already-queued" if already else "queued",
                    "pending": len(ledger.pending(ws)),
                    "candidate": cand, "decision": "accept"}

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
        kinds: Optional[str] = Query(None),
        skeleton: bool = Query(False),
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
                results = graph_browse.browse_map(
                    conn, include_tags=tags, limit=limit, skeleton=skeleton,
                    kinds=[k for k in (kinds or "").split(",") if k] or None)
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

    @app.get("/api/workspace/tasks")
    def get_workspace_tasks(workspace: Optional[str] = Query(None),
                            scope: str = Query("workspace", pattern="^(workspace|hub)$"),
                            include_closed: bool = Query(False)) -> dict:
        """The issues themselves, not just how many there are.

        The panel used to show four counts and nothing else, over a store
        shared by every topic under the hub — so "17 ready" was a number the
        reader could neither open nor attribute. Every issue MAGI opens is
        labelled with its workspace, so the same store answers per library.
        """
        from magi.pm import find_beads_root, list_tasks

        ws = _resolve_workspace(workspace)
        rows = list_tasks(ws, scope=scope, include_closed=include_closed)
        root = find_beads_root(ws)
        if rows is None:
            return {"workspace": str(ws), "store_root": None, "scope": scope,
                    "tasks": [], "here": 0, "elsewhere": 0}
        # Both numbers, always: "0 here" is only informative next to "17 under
        # the hub" — otherwise an empty panel looks like a broken one.
        every = list_tasks(ws, scope="hub", include_closed=include_closed) or []
        here = sum(1 for r in every if r["is_here"])
        return {
            "workspace": str(ws),
            "store_root": str(root) if root else None,
            "scope": scope,
            "tasks": rows,
            "here": here,
            "elsewhere": len(every) - here,
        }

    @app.post("/api/workspace/tasks/act")
    def post_task_action(req: TaskActionRequest) -> dict:
        from magi.pm import TASK_ACTIONS, act_on_task

        if req.action not in TASK_ACTIONS:
            raise HTTPException(status_code=400,
                                detail=f"Unknown action: {req.action}")
        ws = _resolve_workspace(req.workspace)
        ok, msg = act_on_task(ws, req.task_id, req.action)
        if not ok:
            raise HTTPException(status_code=409, detail=msg or "task action failed")
        return {"task_id": req.task_id, "action": req.action, "output": msg}

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
        # How hard the close gate pushes. Editable here because the alternative
        # is a person who wants it stricter for a week reaching for a text
        # editor — and the level the gate reads has to be the level they set,
        # not one the protocol text alone believes in.
        "research.coaching": {"type": "str", "choices": ["off", "light", "strict"]},
        "research.wip_limit": {"type": "int"},
        "research.stall_days": {"type": "int"},
        # Empty means "probe PATH for one that is not the author", which is
        # the default and usually the right answer. It is spelled "" rather
        # than null because a `<select>` has no null: the DOM turns one into
        # the string "null", which the server then refuses — an option the UI
        # offers and the API rejects.
        "research.review_host": {"type": "str",
                                 "choices": [""] + _review_host_names()},
        # What a model may be pinned to. Empty no longer means "that CLI's own
        # default": it falls through to the host record's cheap tier, because
        # design-v2 §11 asks for a cheap reviewer and a setting nobody fills in
        # was quietly getting the most expensive model on the account. Naming a
        # model MAGI cannot reach still turns every review into an error, which
        # is why the WebUI offers a list where the host can produce one.
        "research.review_model": {"type": "str", "nullable": True},
        # How hard the reviewer thinks. Empty means that host's own default —
        # unlike the model, there is no cheap tier to fall back to, because the
        # model id usually already carries the level.
        "research.review_effort": {"type": "str",
                                   "choices": ["", "low", "medium", "high"]},
        # Calls per calendar week before the gate refuses, and the switch that
        # turns MAGI's own calls off entirely. Counted in calls because a
        # headless CLI does not say what a request cost.
        "research.weekly_calls": {"type": "int"},
        "research.llm_calls": {"type": "bool"},
        # How many lines the rule section in AGENTS.md may hold. Small on
        # purpose: the block is read at the start of every session on every
        # host, so a rule that goes in has to be worth what every later
        # session pays to read it.
        "research.rule_budget": {"type": "int"},
        # The library's own rules, in the closed vocabulary `core/rules.py`
        # defines. Editable here because retiring one is a thing a person does,
        # and `magi reflect retire` is the other way to do it.
        "research.rules": {"type": "list_of_maps"},
        # Agent CLIs this workspace knows about, beyond the ones that ship in
        # `core/hosts.py`. There are too many CLIs in the world to enumerate,
        # so a host is a record: a binary, where its skills go, how to call it
        # headless. The one thing a record cannot supply is a transcript
        # reader, and a host without one simply contributes no sessions.
        "research.hosts": {"type": "list_of_maps"},
        # Which *other* registered libraries this project's searches reach.
        # The registry's `enabled` flag is machine-wide and says whether a
        # library may be read at all; this says which ones this project reads,
        # and empty means none — searching stops at your own library unless
        # you ask for more.
        "research.search_projects": {"type": "list"},
        "radar.min_relevance": {"type": "number", "nullable": True},
        "radar.days": {"type": "int"},
        "radar.max_candidates": {"type": "int"},
        "radar.arxiv_categories": {"type": "list"},
        "radar.seed_arxiv_ids": {"type": "list"},
        "radar.own_arxiv_ids": {"type": "list"},
        "ocr.use_mineru": {"type": "bool"},
        # Tokens are the reason people go back to a text editor. They are
        # `secret`, which the WebUI renders masked and never echoes back once
        # set — the value is write-only from the browser's point of view.
        "ocr.mineru_api_token": {"type": "secret"},
        # Free, optional, and the difference between a private per-endpoint
        # quota and sharing an anonymous one with everybody.
        "radar.s2_api_key": {"type": "secret"},
        "models.embedding": {"type": "str"},
        "embedding.provider": {"type": "str", "choices": ["ollama", "openai"]},
        "embedding.base_url": {"type": "str", "nullable": True},
        "embedding.model": {"type": "str", "nullable": True},
        "embedding.api_key": {"type": "secret"},
    }

    #: Marked secret so the reader never leaves with someone else's key on
    #: screen — GET returns whether one is set, never what it is.
    SECRET_FIELDS = {k for k, v in CONFIG_FIELDS.items() if v.get("type") == "secret"}

    def _redact_secrets(raw: str) -> str:
        """Mask the value of any secret key in a raw config dump.

        Matches on the leaf name, because the dump is a flat text file and the
        endpoint has no parsed position to work from. Over-masking a comment
        that happens to mention a token is harmless; under-masking is not.
        """
        leaves = {k.split(".")[-1] for k in SECRET_FIELDS}
        pattern = re.compile(
            rf"^(\s*(?:{'|'.join(map(re.escape, leaves))})\s*:\s*)(\S.*)$", re.MULTILINE)
        return pattern.sub(lambda m: m.group(1) + "********", raw)

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

        # The checking resolver: this endpoint reads a file out of whatever
        # directory the query string named, and its sibling below creates one.
        ws = _reading_root(workspace, None)
        cfg_path = ws / "config.yaml"
        raw = cfg_path.read_text(encoding="utf-8", errors="replace") if cfg_path.is_file() else ""
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            data = {}
        fields = []
        for k, spec in CONFIG_FIELDS.items():
            value = _config_field_value(data, k)
            if k in SECRET_FIELDS:
                # Say whether it is set, never what it is. A dashboard on a
                # shared screen should not be a way to read somebody's key.
                fields.append({"key": k, **spec, "value": None,
                               "is_set": bool(str(value or "").strip())})
            else:
                fields.append({"key": k, **spec, "value": value})
        # `raw` is the whole file, which for a config holding a token would
        # hand it straight back. Blank the secret lines in that copy too.
        return {"workspace": str(ws), "config_path": str(cfg_path),
                "exists": cfg_path.is_file(), "fields": fields,
                "raw": _redact_secrets(raw)}

    @app.post("/api/workspace/config")
    def post_workspace_config(payload: dict = Body(...)) -> dict:
        from magi.core.config_edit import ConfigEditError, set_config_value

        key = payload.get("key")
        value = payload.get("value")
        spec = CONFIG_FIELDS.get(key or "")
        if spec is None:
            raise HTTPException(status_code=400, detail=f"Config key not editable: {key}")

        ftype = spec["type"]
        choices = spec.get("choices")
        if choices and value is not None and value not in choices:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be one of: {', '.join(map(str, choices))}")
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
        elif ftype == "secret":
            if not isinstance(value, str):
                raise HTTPException(status_code=400, detail=f"{key} expects a string")
            # The browser renders a masked field; submitting it untouched must
            # not overwrite a real key with the mask.
            if set(value.strip()) == {"*"}:
                raise HTTPException(status_code=400,
                                    detail=f"{key}: that is the mask, not a key")
        elif ftype == "list":
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise HTTPException(status_code=400, detail=f"{key} expects a list of strings")
        elif ftype == "list_of_maps":
            # There was no branch here at all, so any shape was written and
            # reported as saved. A string under `research.hosts` was then
            # silently dropped by `hosts._configured`, and a malformed rule
            # under `research.rules` came back as a violation of itself that
            # blocked every session close — in both cases long after the UI
            # said it had worked.
            if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
                raise HTTPException(status_code=400,
                                    detail=f"{key} expects a list of records")
            if key == "research.rules":
                from magi.core import rules as rules_mod

                # Refused where it is written, which is what `rules.parse`
                # exists for: the alternative is discovering it at the gate,
                # at the worst moment, in a workspace that will not close.
                try:
                    rules_mod.parse(value)
                except rules_mod.RuleError as exc:
                    raise HTTPException(status_code=400, detail=f"{key}: {exc}")
            if key == "research.hosts":
                from magi.core import hosts as hosts_mod

                bad = [record for record in value if hosts_mod.host_from(record) is None]
                if bad:
                    named = ", ".join(str(r.get("key") or "?") for r in bad)
                    raise HTTPException(
                        status_code=400,
                        detail=f"{key}: unusable record(s): {named}. A host needs "
                               f"at least a `key`.")

        # Writing `research.*` now changes what the close gate enforces, so
        # "any path somebody typed" is not a workspace this may write to.
        ws = _reading_root(payload.get("workspace"), None)
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
                # Which panel a generic button for this op belongs on. `None`
                # means the panel already has a better-contextualised control
                # and must not get a second one.
                "home": spec.get("home"),
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
        # Four-level fallback so an installed `magi ui` still has docs:
        # packaged copies -> repo checkout -> wheel metadata -> GitHub raw.
        #
        # The packaged copies come first because they are the only source that
        # works for everyone. Metadata carries the long_description, which is
        # README.md alone — so before this, every user who did not launch from
        # a git checkout got a Chinese README and a *blank* English tab.
        readme_zh = ""
        readme_en = ""
        source = None

        try:
            import importlib.resources as _res

            import magi.docs as _docs

            zh = _res.files(_docs) / "readme.zh.md"
            en = _res.files(_docs) / "readme.en.md"
            if zh.is_file():
                readme_zh = zh.read_text(encoding="utf-8")
                if en.is_file():
                    readme_en = en.read_text(encoding="utf-8")
                source = "packaged"
        except Exception:
            pass

        candidates = []
        root = Path(__file__).resolve()
        for _ in range(5):
            root = root.parent
            candidates.append(root)
        candidates.append(Path.cwd())
        for base in candidates if not readme_zh else []:
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
        implementation behind the ``magi guide`` command and the docs
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
