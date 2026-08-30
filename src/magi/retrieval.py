"""magi index / magi search — the Casper core (retrieval state).

Hybrid local retrieval over the workspace markdown corpus:
- BM25 via stdlib SQLite FTS5
- vectors via sqlite-vec + Ollama embeddings (same model as `magi link`,
  ``models.embedding`` in config.yaml)
- fusion via Reciprocal Rank Fusion (RRF)

Degrades gracefully: when Ollama is unreachable the index still builds
(BM25-only) and hybrid searches fall back to BM25, reporting
``vector_available: false``. Cross-platform note: on macOS use a Python
whose sqlite3 supports loadable extensions (Homebrew/uv builds do).

Index lives at ``<workspace>/output/index.db``. Collections are derived
from paths: concepts / references / topics / theses / raw.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from magi.core.config_loader import load_config, get as cfg_get
from magi.core.workspace import find_workspace_root

MAX_CHUNK_LINES = 250
RRF_K = 60


# --------------------------------------------------------------------------
# infrastructure
# --------------------------------------------------------------------------

def _die(msg: str, hint: str | None = None, as_json: bool = False) -> int:
    if as_json:
        payload: dict[str, str] = {"error": msg}
        if hint:
            payload["hint"] = hint
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(msg + (f" — {hint}" if hint else ""), file=sys.stderr)
    return 1


def open_db(db_path: Path, create: bool = False,
            want_vectors: bool = True) -> tuple[sqlite3.Connection, bool] | None:
    """Open the index db. Returns (conn, vec_loaded) or None when absent.

    `want_vectors=False` skips loading sqlite-vec, which drags numpy in behind
    it — a fifth of a second of import time that a `--mode bm25` search has no
    use for. Callers that might touch `chunks_vec` must leave it on.
    """
    if not create and not db_path.is_file():
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    if not create:
        # A file that exists but holds no schema is what an interrupted
        # `magi index` leaves behind: SQLite creates the file on connect, and
        # the tables only arrive at the first commit. Reporting it as "no
        # index" is the truth and routes it to the caller's existing
        # skip-this-KB path. Left alone it read as a healthy index right up
        # until the first query, and because search is federated, ONE such
        # file made every other library on the machine unsearchable with a raw
        # `no such table: chunks_fts`.
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'").fetchone()
        if row is None:
            conn.close()
            return None
    vec_loaded = False
    if not want_vectors:
        return conn, False
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        vec_loaded = True
    except (ImportError, AttributeError, sqlite3.OperationalError) as exc:
        print(f"note: sqlite-vec unavailable ({exc}); vector search disabled", file=sys.stderr)
    return conn, vec_loaded


# FTS5's default unicode61 tokenizer treats a whole run of CJK characters as
# ONE token, which blinds BM25 for Chinese/Japanese queries entirely. We index
# and query through overlapping character bigrams instead ("注意力" ->
# "注意 意力") — the standard CJK IR baseline. Latin text passes through
# untouched, so English search behaviour is unchanged.
_CJK_RUN = re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ]+")

FTS_VERSION = "2"


def fts_text(text: str) -> str:
    """Segment CJK runs into overlapping bigrams for FTS indexing/querying."""
    def _seg(m: re.Match) -> str:
        s = m.group(0)
        if len(s) < 2:
            return f" {s} "
        return " " + " ".join(s[i:i + 2] for i in range(len(s) - 1)) + " "
    return _CJK_RUN.sub(_seg, text)


def _fts_schema_version(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='fts_version'").fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def ensure_schema(conn: sqlite3.Connection, dims: int | None, vec_loaded: bool = False) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, hash TEXT, mtime REAL);
        CREATE TABLE IF NOT EXISTS chunks(
            id INTEGER PRIMARY KEY, path TEXT, collection TEXT, heading TEXT,
            start_line INT, end_line INT, content TEXT, content_fts TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        """
    )
    # Legacy dbs predate the content_fts column
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "content_fts" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN content_fts TEXT")

    if _fts_schema_version(conn) != FTS_VERSION:
        # (Re)build the FTS layer with CJK bigram segmentation. Runs once per
        # index db — new dbs take this path on first creation too.
        conn.executescript(
            """
            DROP TRIGGER IF EXISTS chunks_ai;
            DROP TRIGGER IF EXISTS chunks_ad;
            DROP TABLE IF EXISTS chunks_fts;
            """
        )
        rows = conn.execute("SELECT id, content FROM chunks").fetchall()
        if rows:
            conn.executemany(
                "UPDATE chunks SET content_fts=? WHERE id=?",
                [(fts_text(c or ""), i) for i, c in rows],
            )
        conn.executescript(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                content_fts, content='chunks', content_rowid='id');
            CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, content_fts) VALUES (new.id, new.content_fts);
            END;
            CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content_fts) VALUES('delete', old.id, old.content_fts);
            END;
            """
        )
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('fts_version', ?)",
            (FTS_VERSION,),
        )
        conn.commit()
    if dims and vec_loaded:
        # Changing embedding model changes the vector width, and the table is
        # CREATE IF NOT EXISTS — so a switch from a 1024-dim model to a
        # 1536-dim one would keep the old table and start writing rows that do
        # not fit it. Refuse, and name the one command that fixes it, rather
        # than letting search quietly return nonsense.
        prior = conn.execute("SELECT value FROM meta WHERE key='dims'").fetchone()
        if prior and _has_vec_table(conn, vec_loaded):
            try:
                prior_dims = int(prior[0])
            except (TypeError, ValueError):
                prior_dims = None
            if prior_dims and prior_dims != dims:
                raise SearchError(
                    f"this index holds {prior_dims}-dimension vectors but the "
                    f"configured embedding model produces {dims}",
                    "the embedding model changed — rebuild with 'magi index --rebuild'")
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(embedding float[{dims}])"
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('dims', ?)", (str(dims),)
        )


def _has_vec_table(conn: sqlite3.Connection, vec_loaded: bool) -> bool:
    if not vec_loaded:
        return False
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='chunks_vec'"
    ).fetchone()
    return row is not None


# --------------------------------------------------------------------------
# embeddings (Ollama)
# --------------------------------------------------------------------------

# How many chunks to hand Ollama in one request. Measured on a local
# qwen3-embedding:0.6b: one-at-a-time cost ~7.7s per chunk under load, a batch
# of 8 ~2.1s each, a batch of 32 ~1.0s each. Nearly all of it is per-request
# overhead, so batching is the difference between a 20-minute index and a
# 3-minute one.
#
# 16 rather than the fastest measured 32: a batch is a memory multiplier on the
# server side, and an Ollama that gets OOM-killed halfway through costs far
# more than the last 20% of throughput. Raise it with `ollama.embed_batch` in
# config.yaml on a machine with headroom.
EMBED_BATCH = 16


# A person waiting on a search box is not a batch job. The indexing loop may
# legitimately sit on Ollama for minutes, and Ollama serves requests one at a
# time, so a query issued during an index run used to queue behind it — 7 to 33
# seconds of apparent hang with nothing on screen to explain it. Past this
# ceiling the search gives up on vectors, returns its BM25 half, and says so
# through `vector_degraded`, which beats an unbounded wait.
QUERY_EMBED_TIMEOUT = 8.0

# How long a failed embedder stays disabled before it is worth asking again.
DISABLED_COOLDOWN = 30.0

_shared_query_embedder: "tuple[str, Embedder] | None" = None


def _query_embedder(start=None) -> "Embedder":
    """One Embedder for the whole process's searches.

    A fresh one per query re-ran the Ollama preflight — a round trip to
    /api/tags — before every single search, and threw away the pooled
    connection each time.

    Keyed on the workspace it was built for. A process-wide singleton built
    from ambient config is the same bug one level up: search two libraries in
    one process and the second one silently uses the first one's model.
    """
    global _shared_query_embedder
    key = str(start) if start else ""
    if _shared_query_embedder is None or _shared_query_embedder[0] != key:
        _shared_query_embedder = (key, Embedder(start=start))
    return _shared_query_embedder[1]


class _EmbedGone(Exception):
    """The embedding server is unreachable — as opposed to it answering with
    a refusal. Only this kind of failure is worth restarting and retrying."""


def _wrap_transport(exc: Exception) -> Exception:
    """Decide whether a failed request is worth restarting Ollama over.

    A refused connection means the server is gone, and autostart can bring it
    back. A timeout means the opposite — it is there and busy — and retrying
    just makes the caller wait the whole ceiling a second time. An interactive
    search that should have given up after 8 seconds took 17 before this
    distinction existed.
    """
    try:
        import requests

        if isinstance(exc, requests.exceptions.Timeout):
            return exc
        if isinstance(exc, requests.exceptions.ConnectionError):
            return _EmbedGone("embedding server unreachable")
    except ImportError:  # pragma: no cover - requests is a dependency
        pass
    return exc


def _embedding_api_key(cfg: dict) -> str:
    """The key for a cloud embedding provider.

    An env var is offered first and named in the docs, because a key pasted
    into config.yaml is a secret sitting in a file people put in git. Reading
    it from config is still supported — refusing would just push people to
    hardcode it somewhere worse — but the env var wins when both are set.
    """
    import os

    env_name = cfg_get(cfg, "embedding.api_key_env", "MAGI_EMBEDDING_API_KEY")
    if env_name:
        from_env = os.environ.get(str(env_name), "")
        if from_env.strip():
            return from_env.strip()
    return str(cfg_get(cfg, "embedding.api_key", "") or "").strip()


class Embedder:
    """Lazy Ollama embedding client; flips to disabled on first failure."""

    def __init__(self, start=None) -> None:
        # `start` is the workspace this was created for. Without it the
        # embedding model and endpoint come from whatever config sits
        # above the process cwd, which is not necessarily the library
        # being indexed.
        cfg = load_config(start=start)
        # Two providers, one interface. `ollama` is a local install; `openai`
        # is any service speaking OpenAI's /v1/embeddings — which is what
        # SiliconFlow, Jina, Gemini's compat layer, DeepInfra, Together and
        # OpenAI itself all speak, so one code path serves the lot. Providers
        # with a bespoke schema (Cohere, Voyage, Zhipu) are deliberately not
        # here: each would be its own client for one model.
        self.provider = str(cfg_get(cfg, "embedding.provider", "ollama") or "ollama").lower()
        if self.provider == "openai":
            self.base_url = str(
                cfg_get(cfg, "embedding.base_url", "https://api.openai.com/v1")).rstrip("/")
            self.model = (cfg_get(cfg, "embedding.model", None)
                          or cfg_get(cfg, "models.embedding", "text-embedding-3-small"))
            self.api_key = _embedding_api_key(cfg)
        else:
            self.base_url = cfg_get(cfg, "ollama.base_url", "http://127.0.0.1:11434").rstrip("/")
            self.model = cfg_get(cfg, "models.embedding", "qwen3-embedding:0.6b")
            self.api_key = ""
        self.available: bool | None = None  # unknown until first call
        self._preflighted = False
        self._disabled_at = 0.0
        self._session = None
        # /api/embed (batch) arrived in Ollama 0.3.4; /api/embeddings (single)
        # is the older one. None = not yet established which this server has.
        self._batch_api: bool | None = None
        try:
            self.batch = max(1, int(cfg_get(cfg, "ollama.embed_batch", EMBED_BATCH)))
        except (TypeError, ValueError):
            self.batch = EMBED_BATCH

    def _preflight(self) -> bool:
        """Wake a stopped Ollama, and speak up only when a human is needed.

        A server that was merely asleep is not worth a line of output — it
        gets started. A missing install or an unpulled model is, because both
        otherwise show up as nothing more than a silent BM25-only index.
        """
        if self._preflighted:
            return self.available is not False
        self._preflighted = True
        if self.provider == "openai":
            if not self.api_key:
                self.available = False
                self._disabled_at = time.monotonic()
                print("note: embedding.provider is 'openai' but no API key is set — "
                      "put one in embedding.api_key, or in $MAGI_EMBEDDING_API_KEY",
                      file=sys.stderr)
                return False
            return True
        from magi.core import ollama as ollama_svc

        state, _ = ollama_svc.ensure_model(self.base_url, self.model)
        if not state.running or not state.has_model(self.model):
            self.available = False
            # Stamped so the cooldown applies here too: without it a
            # long-lived process would re-probe (and re-attempt autostart) on
            # every single search against a machine with no Ollama on it.
            self._disabled_at = time.monotonic()
            return False
        return True

    def _http(self):
        """A pooled session. A fresh TCP connection per chunk is pure overhead
        on a run that makes thousands of calls to the same local port."""
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def _disable(self, exc: Exception) -> None:
        # Failing at the start and failing halfway through are different
        # events for the user: the first means "no vectors today", the second
        # means "your index is now partially embedded and you should rerun".
        # Reporting both as one silent flag is how a run stopped at 64 of 1371
        # chunks and still exited 0 without a word.
        if self.available is True:
            print(f"warning: Ollama stopped responding mid-run ({type(exc).__name__}); "
                  f"remaining chunks are BM25-only — rerun 'magi index' to backfill them",
                  file=sys.stderr)
        elif self.available is None:
            print(f"note: Ollama embeddings unavailable ({type(exc).__name__}); "
                  f"continuing BM25-only", file=sys.stderr)
        self.available = False
        self._disabled_at = time.monotonic()

    def embed(self, text: str, timeout: float | None = None) -> list[float] | None:
        vecs = self.embed_many([text], timeout=timeout)
        return vecs[0] if vecs else None

    def embed_many(self, texts: list[str], timeout: float | None = None) -> list[list[float]] | None:
        """Embed a batch, or return None if embeddings are unavailable.

        All-or-nothing on purpose: a half-embedded batch would leave chunks
        silently without vectors, and the caller cannot tell which. Returning
        None means "no vectors this run", which the index already handles by
        falling back to BM25 and backfilling on the next run.
        """
        if not texts:
            return []
        if self.available is False:
            # Disabling is sticky so one long run does not retry a dead server
            # thousands of times — but a `magi ui` process lives for days, and
            # an embedder that stayed disabled forever meant a single blip took
            # vector search out until the server was restarted. Re-arm once the
            # cooldown passes and let the next call find out.
            if (time.monotonic() - self._disabled_at) < DISABLED_COOLDOWN:
                return None
            self.available = None
            self._preflighted = False
        if not self._preflight():
            return None

        payload = [t[:8000] for t in texts]

        # One retry, and only for a server that went away: an index run is
        # long enough that Ollama can be OOM-killed or restarted underneath
        # it, and autostart already knows how to bring it back — it just used
        # to run once, at startup, and never again. A malformed request or a
        # missing model is not retried; it would fail identically.
        for attempt in (0, 1):
            try:
                return self._post_batch(payload, timeout)
            except _EmbedGone as exc:
                if attempt == 0:
                    self._preflighted = False
                    if self._preflight():
                        print("note: Ollama went away mid-run; restarted it and retrying",
                              file=sys.stderr)
                        continue
                self._disable(exc.__cause__ or exc)
                return None
            except Exception as exc:
                self._disable(exc)
                return None
        return None

    def _post_batch(self, payload: list[str],
                    timeout: float | None = None) -> list[list[float]]:
        """One round trip for the whole batch. Raises; never returns None."""
        # Scale the ceiling with the batch: a 16-chunk request legitimately
        # takes longer than a single one, and a timeout here costs the run.
        # An interactive caller passes its own, much shorter, ceiling.
        if timeout is None:
            timeout = 60 + 10 * len(payload)

        if self.provider == "openai":
            try:
                resp = self._http().post(
                    f"{self.base_url}/embeddings",
                    json={"model": self.model, "input": payload},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=timeout,
                )
            except Exception as exc:
                raise _wrap_transport(exc) from exc
            resp.raise_for_status()
            # OpenAI's response is not guaranteed to come back in request
            # order; it carries an index per row and the docs say to use it.
            rows = resp.json().get("data") or []
            if len(rows) != len(payload):
                raise ValueError(
                    f"asked for {len(payload)} embeddings, got {len(rows)}")
            ordered = sorted(rows, key=lambda r: r.get("index", 0))
            vecs = [r.get("embedding") for r in ordered]
            if not all(vecs):
                raise ValueError("empty embedding in batch")
            self.available = True
            return vecs

        if self._batch_api is not False:
            try:
                resp = self._http().post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": payload},
                    timeout=timeout,
                )
            except Exception as exc:
                raise _wrap_transport(exc) from exc
            if resp.status_code != 404:
                resp.raise_for_status()
                vecs = resp.json().get("embeddings")
                if not vecs or len(vecs) != len(payload) or not all(vecs):
                    raise ValueError("short or empty embedding batch")
                self._batch_api = True
                self.available = True
                return vecs
            # Ollama predates /api/embed; use the single-prompt route from
            # here on rather than probing again on every batch.
            self._batch_api = False

        out: list[list[float]] = []
        for text in payload:
            try:
                resp = self._http().post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=timeout,
                )
            except Exception as exc:
                raise _wrap_transport(exc) from exc
            resp.raise_for_status()
            vec = resp.json().get("embedding")
            if not vec:
                raise ValueError("empty embedding")
            out.append(vec)
        self.available = True
        return out


def _serialize(vec: list[float]) -> bytes:
    from sqlite_vec import serialize_float32

    return serialize_float32(vec)


# --------------------------------------------------------------------------
# indexing
# --------------------------------------------------------------------------

# Navigation/backmatter headings in wiki cards that carry no retrievable
# content of their own (mostly wikilink lists).
_BOILERPLATE_HEADINGS = {
    "see also", "sources", "references", "related", "further reading",
    "参考文献", "相关条目", "另见", "来源",
    # `magi link` writes this section into every concept card, and it is
    # nothing but concept names — left indexed, it outranks the actual
    # definitions for any concept-name query.
    "语义关联 (semantic links)", "语义关联", "semantic links",
}


def _collection_of(rel: Path) -> str:
    parts = rel.parts
    if parts[0] == "raw":
        return "raw"
    if parts[0] == "drafts":
        return "drafts"
    if parts[0] == "threads":
        return "threads"
    if parts[0] == "wiki" and len(parts) > 1 and parts[1] in ("concepts", "references", "topics", "theses"):
        return parts[1]
    return "other"


def _iter_corpus(root: Path):
    # `threads/` is indexed but deliberately absent from `wiki_common
    # .CORPUS_DIRS`: that tuple drives the maintenance passes that *rewrite*
    # files, and a discussion is append-only — nothing reformats somebody's
    # post. Searchable, not editable.
    for base in ("wiki", "raw", "drafts", "threads"):
        d = root / base
        if not d.is_dir():
            continue
        for p in d.rglob("*.md"):
            if p.name == "_index.md" or ".backup" in p.parts:
                continue
            yield p


#: How much more a chunk counts when the caller named a research line and the
#: chunk is in that line's focus. A boost rather than a filter on purpose: the
#: answer to a question asked from inside a line is often in a paper the line
#: has never cited, and filtering to the focus set would hide exactly that.
FOCUS_BOOST = 1.5


#: How much a collection counts for in a query that did not ask for it.
#: `threads/` holds propositions in progress — a conjecture nobody has tested
#: is not the answer to "what is X", and letting one outrank a concept card is
#: how a guess gets read back as knowledge. Asking for it by name
#: (`--collection threads`) is a filter, not a ranking, so the penalty lifts.
_COLLECTION_WEIGHT = {"threads": 0.6}


def _line_focus(args):
    """The focus set for `--line`, or `None`. Never fatal: a search that cannot
    work out what a line is looking at is still a search."""
    line = getattr(args, "line", None)
    if not line:
        return None
    try:
        from magi import state

        from magi.core.workspace import find_workspace_root

        root = args.topic_dir or find_workspace_root()
        return state.focus(root, line) if root else None
    except Exception:  # noqa: BLE001
        return None


def _apply_focus(conns, merged, focus, weights) -> None:
    """Multiply in the focus boost for chunks whose file the line points at.

    Local knowledge base only. The focus set is a list of paths relative to
    *this* workspace's root, and another registered library will happily have
    its own `wiki/concepts/toric-code.md` — matching by path across libraries
    would boost a file the line has never heard of because its name collided.
    """
    wanted = {str(path).replace("\\", "/") for path in focus}
    by_kb: dict = {}
    for name, cid in merged:
        if name != "local":
            continue
        by_kb.setdefault(name, []).append(cid)

    for name, ids in by_kb.items():
        placeholders = ",".join("?" * len(ids))
        rows = conns[name].execute(
            f"SELECT id, path FROM chunks WHERE id IN ({placeholders})", ids)
        for cid, path in rows:
            if str(path).replace("\\", "/") in wanted:
                weights[(name, cid)] = weights.get((name, cid), 1.0) * FOCUS_BOOST


def _collection_weights(conns, merged) -> dict:
    """`{(kb, chunk_id): multiplier}` for the chunks a search is ranking.

    One query per knowledge base rather than one per chunk: the candidate pool
    after fusion is small, but it is not one row.
    """
    by_kb: dict = {}
    for name, cid in merged:
        by_kb.setdefault(name, []).append(cid)

    weights: dict = {}
    for name, ids in by_kb.items():
        placeholders = ",".join("?" * len(ids))
        rows = conns[name].execute(
            f"SELECT id, collection FROM chunks WHERE id IN ({placeholders})", ids)
        for cid, coll in rows:
            weight = _COLLECTION_WEIGHT.get(coll)
            if weight is not None:
                weights[(name, cid)] = weight
    return weights


def _chunk(text: str) -> list[tuple[str, int, int, str]]:
    """Split into (heading, start_line, end_line, content) chunks."""
    lines = text.split("\n")
    boundaries = [0]
    for i, line in enumerate(lines):
        if i and re.match(r"^#{1,3} ", line):
            boundaries.append(i)
    boundaries.append(len(lines))

    chunks: list[tuple[str, int, int, str]] = []
    for a, b in zip(boundaries, boundaries[1:]):
        seg = lines[a:b]
        # cap oversized segments
        for s in range(0, len(seg), MAX_CHUNK_LINES):
            part = seg[s: s + MAX_CHUNK_LINES]
            body = "\n".join(part).strip()
            if not body:
                continue
            heading = ""
            m = re.match(r"^#{1,3} (.+)$", part[0]) if part else None
            if m:
                heading = m.group(1).strip()
            chunks.append((heading, a + s + 1, a + s + len(part), body))
    return chunks


class _Progress:
    """Throttled progress lines for a command that can run for minutes.

    Plain lines, not a redrawn carriage-return bar: this output is read as
    often through the WebUI's job log as through a terminal, and a `\\r` bar
    turns into one unreadable smear there. One line every few seconds is
    enough to tell "working" from "wedged", which is the whole job.
    """

    INTERVAL = 3.0

    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self._last = 0.0

    def start(self, message: str) -> None:
        if self.quiet:
            return
        print(f"index: {message}", flush=True)
        self._last = time.monotonic()

    def tick(self, message: str, force: bool = False) -> None:
        if self.quiet:
            return
        now = time.monotonic()
        if not force and (now - self._last) < self.INTERVAL:
            return
        self._last = now
        print(f"index: {message}", flush=True)


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        return _die("no workspace found (run from a topic directory or pass --topic-dir)")
    db_path = root / "output" / "index.db"
    # The one honest remedy for a changed embedding model: the vector table is
    # created with a fixed width and cannot be widened in place, so the file
    # has to go. Nothing else in the workspace is touched — the index is
    # derived data, rebuilt from wiki/ and raw/ every time.
    if getattr(args, "rebuild", False) and db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            # Windows refuses to unlink a file another *process* has open, and
            # something usually does: the WebUI opens the index read-only per
            # request, `magi search` holds it for the length of a query, a DB
            # browser holds it indefinitely. The comment below covers the
            # in-process case; this is the one a person actually hits, and it
            # used to surface as a raw traceback out of pathlib with no hint
            # that closing a window would fix it.
            return _die(f"{db_path} is open in another process — close the "
                        f"WebUI (or any other magi command using this "
                        f"workspace) and run it again")
        print(f"magi index: removed {db_path} — rebuilding from scratch")
    opened = open_db(db_path, create=True)
    assert opened is not None
    conn, vec_loaded = opened

    # The index is written under an open connection for the length of the
    # whole run and there was no close on any path out. It matters most on
    # Windows, where `--rebuild` unlinks this same file: a connection left
    # open by an earlier in-process call makes that unlink fail.
    try:

        embedder = Embedder(start=root)
        dims: int | None = None
        if not args.no_vectors:
            probe = embedder.embed("magi index probe")
            dims = len(probe) if probe else None
        ensure_schema(conn, dims, vec_loaded)
        vec_on = dims is not None and _has_vec_table(conn, vec_loaded)

        seen: set[str] = set()
        changed = unchanged = embedded = 0

        # Embedding is the long pole — minutes, sometimes tens of minutes. Saying
        # nothing for that whole stretch is indistinguishable from being hung, and
        # that is exactly how it was reported. Throttled so a terminal and a job
        # log both stay readable.
        progress = _Progress(quiet=getattr(args, "quiet", False))

        # (chunk rowid, body) waiting for a vector. Flushed at every file boundary:
        # SQLite can hand a deleted rowid to the next insert, so a pending vector
        # must never outlive the DELETE of another file's chunks.
        pending: list[tuple[int, str]] = []

        def flush_vectors(final: bool = False) -> None:
            nonlocal embedded, vec_on
            if not pending:
                return
            vecs = embedder.embed_many([body for _, body in pending])
            if vecs is None:
                vec_on = False          # BM25-only from here; next run backfills
                pending.clear()
                return
            conn.executemany(
                "INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)",
                [(cid, _serialize(vec)) for (cid, _), vec in zip(pending, vecs)],
            )
            embedded += len(vecs)
            pending.clear()
            progress.tick(f"embedding: {embedded} chunks vectorized", force=final)

        for p in _iter_corpus(root):
            rel = p.relative_to(root).as_posix()
            seen.add(rel)
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"warning: cannot read {rel}: {exc}", file=sys.stderr)
                continue
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            row = conn.execute("SELECT hash FROM files WHERE path=?", (rel,)).fetchone()
            if row and row[0] == digest:
                unchanged += 1
                continue
            changed += 1
            old_ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE path=?", (rel,))]
            if old_ids and _has_vec_table(conn, vec_loaded):
                conn.executemany("DELETE FROM chunks_vec WHERE rowid=?", [(i,) for i in old_ids])
            conn.execute("DELETE FROM chunks WHERE path=?", (rel,))
            collection = _collection_of(Path(rel))
            for heading, s, e, body in _chunk(text):
                # Card-template boilerplate sections (See Also / Sources lists)
                # otherwise crowd real content out of the BM25 top ranks.
                if collection != "raw" and heading.strip().rstrip(":").lower() in _BOILERPLATE_HEADINGS:
                    continue
                cur = conn.execute(
                    "INSERT INTO chunks(path, collection, heading, start_line, end_line, content, content_fts) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (rel, collection, heading, s, e, body, fts_text(body)),
                )
                if vec_on:
                    pending.append((cur.lastrowid, body))
                    if len(pending) >= embedder.batch:
                        flush_vectors()
            flush_vectors()
            conn.execute(
                "INSERT OR REPLACE INTO files(path, hash, mtime) VALUES(?,?,?)",
                (rel, digest, p.stat().st_mtime),
            )
            conn.commit()

        # prune deleted files
        gone = [r[0] for r in conn.execute("SELECT path FROM files").fetchall() if r[0] not in seen]
        for rel in gone:
            old_ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE path=?", (rel,))]
            if old_ids and _has_vec_table(conn, vec_loaded):
                conn.executemany("DELETE FROM chunks_vec WHERE rowid=?", [(i,) for i in old_ids])
            conn.execute("DELETE FROM chunks WHERE path=?", (rel,))
            conn.execute("DELETE FROM files WHERE path=?", (rel,))
        conn.commit()

        # Backfill vectors for chunks missed in earlier BM25-only runs. On a
        # library first indexed without Ollama this is the entire corpus, so it is
        # the longest phase of the command by far — batched, reported, and
        # committed as it goes, because an interrupted run that threw away twenty
        # minutes of embedding was worse than one that stops half-done.
        if dims is not None and _has_vec_table(conn, vec_loaded) and not args.no_vectors and embedder.available:
            missing = conn.execute(
                "SELECT id, content FROM chunks WHERE id NOT IN (SELECT rowid FROM chunks_vec)"
            ).fetchall()
            if missing:
                progress.start(f"backfilling vectors for {len(missing)} chunks")
            done = 0
            for start in range(0, len(missing), embedder.batch):
                batch = missing[start:start + embedder.batch]
                vecs = embedder.embed_many([body for _, body in batch])
                if vecs is None:
                    break
                conn.executemany(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)",
                    [(cid, _serialize(vec)) for (cid, _), vec in zip(batch, vecs)],
                )
                conn.commit()       # survive a Ctrl-C with the work done so far
                embedded += len(vecs)
                done += len(vecs)
                progress.tick(f"backfill: {done}/{len(missing)} chunks",
                              force=done == len(missing))
            conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vec_total = (
            conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[0]
            if _has_vec_table(conn, vec_loaded) else 0
        )
        print(f"index: {total} chunks ({changed} files updated, {unchanged} unchanged, "
              f"{len(gone)} pruned) · vectors {vec_total}/{total}"
              + ("" if dims else (" · BM25-only (--no-vectors)" if args.no_vectors
                                 else " · BM25-only (Ollama unavailable)")))

        # Register this workspace in the global KB registry so other
        # workspaces can federate over it (magi kb list / disable to manage).
        try:
            from magi.kb_registry import register_kb

            register_kb(root, quiet=True)
        except Exception:
            pass
        return 0
    finally:
        conn.close()


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------

def _fts_query(q: str) -> str:
    # OR semantics: full-question queries should still hit documents that
    # match only some tokens (BM25 ranking rewards multi-token matches).
    # CJK runs are bigram-segmented to mirror how the index was built.
    tokens = [t.replace('"', "") for t in fts_text(q).split() if t.strip('"')]
    return " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'


def _rrf(ranks: dict[int, dict[str, int]]) -> dict[int, float]:
    return {
        cid: sum(1.0 / (RRF_K + r) for r in d.values())
        for cid, d in ranks.items()
    }


def _search_one_db(conn, vec_loaded, args, qvec, n):
    """Run the BM25/vector legs on one index db.

    Returns (ranks {cid: {leg: rank}}, bm25_hits, vector_hits, vector_used).
    """
    where = ""
    params: list = []
    if getattr(args, "collection", None):
        where += " AND c.collection = ?"
        params.append(args.collection)
    if getattr(args, "path", None):
        where += " AND c.path GLOB ?"
        params.append(args.path)

    ranks: dict[int, dict[str, int]] = {}
    dists: dict[int, float] = {}
    bm25_hits = vector_hits = 0
    vector_used = False

    if args.mode in ("hybrid", "bm25"):
        if _fts_schema_version(conn) != FTS_VERSION and _CJK_RUN.search(args.query):
            print("note: this index predates CJK-aware tokenization — "
                  "re-run 'magi index' there to make Chinese queries match",
                  file=sys.stderr)
        rows = conn.execute(
            "SELECT c.id FROM chunks_fts f JOIN chunks c ON c.id = f.rowid "
            f"WHERE chunks_fts MATCH ?{where} ORDER BY bm25(chunks_fts) LIMIT ?",
            [_fts_query(args.query), *params, n],
        ).fetchall()
        bm25_hits = len(rows)
        for r, (cid,) in enumerate(rows):
            ranks.setdefault(cid, {})["bm25"] = r + 1

    if qvec is not None and args.mode in ("hybrid", "vector") and _has_vec_table(conn, vec_loaded):
        dims_row = conn.execute("SELECT value FROM meta WHERE key='dims'").fetchone()
        if dims_row and int(dims_row[0]) == len(qvec):
            rows = conn.execute(
                "SELECT v.rowid, v.distance FROM chunks_vec v JOIN chunks c ON c.id = v.rowid "
                f"WHERE v.embedding MATCH ? AND k = ?{where} ORDER BY v.distance",
                [_serialize(qvec), n, *params],
            ).fetchall()
            vector_used = True
            vector_hits = len(rows)
            for r, (cid, dist) in enumerate(rows):
                ranks.setdefault(cid, {})["vector"] = r + 1
                dists[cid] = float(dist)
        else:
            print("note: index dims mismatch current embedding model — re-run 'magi index' there",
                  file=sys.stderr)
    return ranks, bm25_hits, vector_hits, vector_used, dists


# Bands for the vector leg's L2 distance, chosen off a 40-query baseline on a
# real 1371-chunk library (see docs: Search -> reading the result badges).
#
# These are LABELS, not a filter. A filter was the obvious idea and the data
# killed it: across that baseline the worst real query ("tensor network
# renormalization") had a best hit at 0.912 while the best junk query
# ("🙂🙂🙂") reached 0.843, so real and junk overlap
# and no cutoff separates them. Any threshold that caught the junk would also
# have dropped true hits for exactly the broad, exploratory queries someone
# types before they know a library's vocabulary. Showing how close a match is
# lets the reader judge; guessing a boundary for them silently loses results.
CLOSENESS_STRONG = 0.70
CLOSENESS_RELATED = 0.88


def closeness_label(distance: float | None) -> str | None:
    """`strong` / `related` / `weak` for one vector hit, or None if it had no
    vector leg (a pure keyword match carries no distance)."""
    if distance is None:
        return None
    if distance <= CLOSENESS_STRONG:
        return "strong"
    if distance <= CLOSENESS_RELATED:
        return "related"
    return "weak"


class SearchError(Exception):
    """Search cannot run; carries the user-facing message + remediation hint."""

    def __init__(self, msg: str, hint: str | None = None):
        super().__init__(msg)
        self.msg = msg
        self.hint = hint


def run_search(query: str, mode: str = "hybrid", k: int = 8, scope: str = "auto",
               kb: str | None = None, collection: str | None = None,
               path: str | None = None, topic_dir: str | None = None,
               focus: set | None = None) -> dict:
    """Shared search core. The returned payload IS the contract — identical for
    `magi search --json`, the WebUI API, and the future `magi mcp` surface.
    Raises SearchError when search cannot run at all."""
    from magi.kb_registry import load_registry, searchable_kbs

    root = Path(topic_dir).resolve() if topic_dir else find_workspace_root()

    targets = []
    if kb:
        if kb == "local":
            if root is None:
                raise SearchError("no local workspace found", "run from a topic directory")
            targets = [("local", root / "output" / "index.db")]
        else:
            entry = load_registry()["kbs"].get(kb)
            if not entry:
                raise SearchError(f"unknown KB '{kb}'", "see 'magi kb list'")
            targets = [(kb, Path(entry["path"]) / "output" / "index.db")]
    else:
        if root is not None and scope in ("auto", "local"):
            targets.append(("local", root / "output" / "index.db"))
        if scope in ("auto", "global"):
            targets.extend((name, p / "output" / "index.db")
                           for name, p in searchable_kbs(exclude=root))
        if not targets:
            if scope == "local":
                raise SearchError("no workspace found", "run from a topic directory or pass --topic-dir")
            raise SearchError("no workspace here and no searchable registered KBs",
                              "run inside a topic dir, or 'magi kb register' + 'magi kb enable'")

    opened_targets = []
    kbs_skipped: list[str] = []
    try:
        for name, dbp in targets:
            o = open_db(dbp, want_vectors=mode != "bm25")
            if o is None:
                if name == "local" and len(targets) == 1:
                    raise SearchError("no index at output/index.db", "run 'magi index' first")
                # Another KB with no index is housekeeping. *This* workspace
                # with no index means the search never looked at what the
                # person asked about — said at the end instead, where the last
                # line is read, because here it sits above a page of results
                # from other libraries and gets scrolled past.
                if name != "local":
                    print(f"note: KB '{name}' has no index — skipping", file=sys.stderr)
                kbs_skipped.append(name)
                continue
            opened_targets.append((name, *o))
        if not opened_targets:
            raise SearchError("no searchable index found in any target KB",
                              "run 'magi index' in the workspace(s)")

        # Said before the results as well as after them. Putting it last fixed
        # one half — above a page of output it was scrolled past — and the
        # retest found the other: the hits from other libraries are topically
        # convincing, and somebody who reads the top one first has already
        # acted on a stranger's note by the time the caveat arrives.
        if "local" in kbs_skipped:
            print("This workspace has no index — everything below is from "
                  "other libraries, not from here.", file=sys.stderr)

        n = max(k * 3, 20)
        qvec = None
        vector_degraded = False
        if mode in ("hybrid", "vector"):
            qvec = _query_embedder(root).embed(query, timeout=QUERY_EMBED_TIMEOUT)
            vector_degraded = qvec is None
        sargs = argparse.Namespace(query=query, mode=mode, k=k,
                                   collection=collection, path=path)

        merged = {}
        distances: dict[tuple, float] = {}
        conns = {}
        bm25_hits = vector_hits = 0
        vector_available = False
        for name, conn, vec_loaded in opened_targets:
            conns[name] = conn
            ranks, bh, vh, vused, dmap = _search_one_db(conn, vec_loaded, sargs, qvec, n)
            for cid, dv in dmap.items():
                distances[(name, cid)] = dv
            bm25_hits += bh
            vector_hits += vh
            vector_available = vector_available or vused
            for cid, legs in ranks.items():
                merged[(name, cid)] = legs

        if mode == "vector" and not vector_available:
            if vector_degraded:
                raise SearchError(
                    "vector search unavailable — Ollama did not answer in "
                    f"{QUERY_EMBED_TIMEOUT:.0f}s",
                    "an indexing job monopolises the embedding server while it runs; "
                    "wait for it to finish, or use --mode bm25")
            raise SearchError("vector search unavailable — this index holds no vectors",
                              "run 'magi index' to embed it (MAGI starts Ollama itself; "
                              "if it is not installed, get it from https://ollama.com)")

        weights = _collection_weights(conns, merged) if not collection else {}
        if focus:
            _apply_focus(conns, merged, focus, weights)
        scores = {
            key: sum(1.0 / (RRF_K + r) for r in legs.values()) * weights.get(key, 1.0)
            for key, legs in merged.items()
        }
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:k]

        results = []
        for (name, cid), score in top:
            row = conns[name].execute(
                "SELECT path, collection, heading, start_line, end_line, content "
                "FROM chunks WHERE id=?", (cid,),
            ).fetchone()
            if not row:
                continue
            rpath, coll, heading, s, e, content = row
            snippet = " ".join(content.split())[:300]
            dist = distances.get((name, cid))
            results.append({
                "kb": name, "path": rpath, "collection": coll, "heading": heading,
                "lines": [s, e], "score": round(score, 5),
                "bm25_rank": merged[(name, cid)].get("bm25"),
                "vector_rank": merged[(name, cid)].get("vector"),
                "distance": round(dist, 4) if dist is not None else None,
                "closeness": closeness_label(dist),
                "snippet": snippet,
            })

        return {
            "query": query, "mode": mode, "scope": kb or scope,
            "kbs_searched": [name for name, *_ in opened_targets],
            "kbs_skipped": kbs_skipped,
            "vector_available": vector_available,
            "vector_degraded": vector_degraded,
            "bm25_hits": bm25_hits, "vector_hits": vector_hits,
            "best_distance": round(min(distances.values()), 4) if distances else None,
            "weak_semantic_match": (
                bool(distances) and min(distances.values()) > CLOSENESS_RELATED),
            "results": results,
        }
    finally:
        # A long-lived server calls this repeatedly — never leak connections.
        for _, conn, _vl in opened_targets:
            try:
                conn.close()
            except Exception:
                pass


def cmd_search(args: argparse.Namespace) -> int:
    """Federated search: current workspace + enabled KBs from the global
    registry. --scope local restricts to the current workspace; --kb
    <name> targets one registered KB."""
    try:
        payload = run_search(args.query, mode=args.mode, k=args.k, scope=args.scope,
                             focus=_line_focus(args), kb=args.kb, collection=args.collection,
                             path=args.path, topic_dir=args.topic_dir)
    except SearchError as exc:
        return _die(exc.msg, hint=exc.hint, as_json=args.json)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        results = payload["results"]
        if not results:
            print("no results")
            if _CJK_RUN.search(args.query):
                print("(tip: if this index was built before CJK-aware tokenization, "
                      "re-run 'magi index'; otherwise try shorter keywords or --mode vector)")
        for i, r in enumerate(results, 1):
            marks = "+".join(k for k in ("bm25", "vector")
                             if r["bm25_rank" if k == "bm25" else "vector_rank"] is not None)
            kb_tag = "" if r["kb"] == "local" else f" [kb:{r['kb']}]"
            print(f"{i}. {r['path']}:{r['lines'][0]}-{r['lines'][1]} [{r['collection']}]{kb_tag} ({marks})")
            if r["heading"]:
                print(f"   # {r['heading']}")
            print(f"   {r['snippet'][:200]}")
        if len(payload["kbs_searched"]) > 1:
            print(f"(searched: {', '.join(payload['kbs_searched'])} — narrow with --scope local or --kb <name>)")
        if "local" in payload["kbs_skipped"]:
            # Last, and in its own words. Everything above this line came from
            # other libraries, and a person who does not know that reads it as
            # an answer about their own work.
            # Flushed first: this goes to stderr and the results to stdout,
            # and under a pipe stdout is block-buffered — without this the
            # warning about everything above it arrives before it.
            sys.stdout.flush()
            where = "Nothing above is from it" if results else "It was not searched"
            print(f"\nThis workspace is not searchable yet — it has no index. "
                  f"{where}.\nRun 'magi index' here, then search again.",
                  file=sys.stderr)
        if not payload["vector_available"] and args.mode == "hybrid":
            print("(BM25-only: this index holds no vectors — run 'magi index' to add them)")
    return 0


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    # `prog` is the command as typed. Naming two commands here produced
    # `usage: magi index|search search [-h] …` — a usage line that looks like
    # a bug in the first thing a person reads about the command.
    parser = argparse.ArgumentParser(prog="magi", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Build/refresh the hybrid retrieval index")
    p_index.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_index.add_argument("--no-vectors", action="store_true", help="Skip embeddings (BM25 only)")
    p_index.add_argument("--rebuild", action="store_true",
                         help="Delete the index and build it again — needed after "
                              "changing the embedding model, whose vector width "
                              "an existing index cannot change")
    p_index.add_argument("--quiet", action="store_true",
                         help="Suppress embedding progress lines (final summary still prints)")
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="Hybrid BM25+vector search with RRF fusion")
    p_search.add_argument("query")
    p_search.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_search.add_argument("--collection", choices=["concepts", "references", "topics", "theses",
                                                   "raw", "drafts", "threads", "other"])
    p_search.add_argument("--path", help="Only search chunks whose file path matches this glob, "
                                         "e.g. --path 'raw/papers/2026-*higher-rank*' (applies per KB)")
    p_search.add_argument("--line", help="Rank what this research line is looking at higher. "
                                         "A boost, not a filter: the answer is often in a paper "
                                         "the line has never cited.")
    p_search.add_argument("-k", type=int, default=8, help="Max results (default 8)")
    p_search.add_argument("--mode", choices=["hybrid", "bm25", "vector"], default="hybrid")
    p_search.add_argument("--scope", choices=["auto", "local", "global"], default="auto",
                          help="auto = current workspace + enabled registered KBs (default); "
                               "local = current workspace only; global = registered KBs only")
    p_search.add_argument("--kb", help="Search a single registered KB by name ('local' = current workspace)")
    p_search.add_argument("--json", action="store_true")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
