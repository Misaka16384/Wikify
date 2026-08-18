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


def open_db(db_path: Path, create: bool = False) -> tuple[sqlite3.Connection, bool] | None:
    """Open the index db. Returns (conn, vec_loaded) or None when absent."""
    if not create and not db_path.is_file():
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    vec_loaded = False
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

class Embedder:
    """Lazy Ollama embedding client; flips to disabled on first failure."""

    def __init__(self) -> None:
        cfg = load_config()
        self.base_url = cfg_get(cfg, "ollama.base_url", "http://127.0.0.1:11434").rstrip("/")
        self.model = cfg_get(cfg, "models.embedding", "qwen3-embedding:0.6b")
        self.available: bool | None = None  # unknown until first call

    def embed(self, text: str) -> list[float] | None:
        if self.available is False:
            return None
        try:
            import requests

            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text[:8000]},
                timeout=60,
            )
            resp.raise_for_status()
            vec = resp.json().get("embedding")
            if not vec:
                raise ValueError("empty embedding")
            self.available = True
            return vec
        except Exception as exc:
            if self.available is None:
                print(f"note: Ollama embeddings unavailable ({type(exc).__name__}); "
                      f"continuing BM25-only", file=sys.stderr)
            self.available = False
            return None


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
}


def _collection_of(rel: Path) -> str:
    parts = rel.parts
    if parts[0] == "raw":
        return "raw"
    if parts[0] == "drafts":
        return "drafts"
    if parts[0] == "wiki" and len(parts) > 1 and parts[1] in ("concepts", "references", "topics", "theses"):
        return parts[1]
    return "other"


def _iter_corpus(root: Path):
    for base in ("wiki", "raw", "drafts"):
        d = root / base
        if not d.is_dir():
            continue
        for p in d.rglob("*.md"):
            if p.name == "_index.md" or ".backup" in p.parts:
                continue
            yield p


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


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        return _die("no workspace found (run from a topic directory or pass --topic-dir)")
    db_path = root / "output" / "index.db"
    opened = open_db(db_path, create=True)
    assert opened is not None
    conn, vec_loaded = opened

    embedder = Embedder()
    dims: int | None = None
    if not args.no_vectors:
        probe = embedder.embed("magi index probe")
        dims = len(probe) if probe else None
    ensure_schema(conn, dims, vec_loaded)
    vec_on = dims is not None and _has_vec_table(conn, vec_loaded)

    seen: set[str] = set()
    changed = unchanged = embedded = 0
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
                vec = embedder.embed(body)
                if vec is not None:
                    conn.execute(
                        "INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)",
                        (cur.lastrowid, _serialize(vec)),
                    )
                    embedded += 1
                else:
                    vec_on = False
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

    # backfill vectors for chunks missed in earlier BM25-only runs
    if dims is not None and _has_vec_table(conn, vec_loaded) and not args.no_vectors and embedder.available:
        missing = conn.execute(
            "SELECT id, content FROM chunks WHERE id NOT IN (SELECT rowid FROM chunks_vec)"
        ).fetchall()
        for cid, body in missing:
            vec = embedder.embed(body)
            if vec is None:
                break
            conn.execute("INSERT INTO chunks_vec(rowid, embedding) VALUES(?,?)", (cid, _serialize(vec)))
            embedded += 1
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
                "SELECT v.rowid FROM chunks_vec v JOIN chunks c ON c.id = v.rowid "
                f"WHERE v.embedding MATCH ? AND k = ?{where} ORDER BY v.distance",
                [_serialize(qvec), n, *params],
            ).fetchall()
            vector_used = True
            vector_hits = len(rows)
            for r, (cid,) in enumerate(rows):
                ranks.setdefault(cid, {})["vector"] = r + 1
        else:
            print("note: index dims mismatch current embedding model — re-run 'magi index' there",
                  file=sys.stderr)
    return ranks, bm25_hits, vector_hits, vector_used


def cmd_search(args: argparse.Namespace) -> int:
    """Federated search: current workspace + enabled KBs from the global
    registry. --scope local restricts to the current workspace; --kb
    <name> targets one registered KB."""
    from magi.kb_registry import load_registry, searchable_kbs

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()

    targets = []
    if args.kb:
        if args.kb == "local":
            if root is None:
                return _die("no local workspace found", hint="run from a topic directory", as_json=args.json)
            targets = [("local", root / "output" / "index.db")]
        else:
            entry = load_registry()["kbs"].get(args.kb)
            if not entry:
                return _die(f"unknown KB '{args.kb}'", hint="see 'magi kb list'", as_json=args.json)
            targets = [(args.kb, Path(entry["path"]) / "output" / "index.db")]
    else:
        if root is not None and args.scope in ("auto", "local"):
            targets.append(("local", root / "output" / "index.db"))
        if args.scope in ("auto", "global"):
            targets.extend((name, p / "output" / "index.db")
                           for name, p in searchable_kbs(exclude=root))
        if not targets:
            if args.scope == "local":
                return _die("no workspace found", hint="run from a topic directory or pass --topic-dir",
                            as_json=args.json)
            return _die("no workspace here and no searchable registered KBs",
                        hint="run inside a topic dir, or 'magi kb register' + 'magi kb enable'",
                        as_json=args.json)

    opened_targets = []
    for name, dbp in targets:
        o = open_db(dbp)
        if o is None:
            if name == "local" and len(targets) == 1:
                return _die("no index at output/index.db", hint="run 'magi index' first", as_json=args.json)
            print(f"note: KB '{name}' has no index — skipping", file=sys.stderr)
            continue
        opened_targets.append((name, *o))
    if not opened_targets:
        return _die("no searchable index found in any target KB",
                    hint="run 'magi index' in the workspace(s)", as_json=args.json)

    n = max(args.k * 3, 20)
    qvec = Embedder().embed(args.query) if args.mode in ("hybrid", "vector") else None

    merged = {}
    conns = {}
    bm25_hits = vector_hits = 0
    vector_available = False
    for name, conn, vec_loaded in opened_targets:
        conns[name] = conn
        ranks, bh, vh, vused = _search_one_db(conn, vec_loaded, args, qvec, n)
        bm25_hits += bh
        vector_hits += vh
        vector_available = vector_available or vused
        for cid, legs in ranks.items():
            merged[(name, cid)] = legs

    if args.mode == "vector" and not vector_available:
        return _die("vector search unavailable (no vectors in index or Ollama down)",
                    hint="start Ollama and re-run 'magi index'", as_json=args.json)

    scores = {
        key: sum(1.0 / (RRF_K + r) for r in legs.values())
        for key, legs in merged.items()
    }
    top = sorted(scores.items(), key=lambda kv: -kv[1])[: args.k]

    results = []
    for (name, cid), score in top:
        row = conns[name].execute(
            "SELECT path, collection, heading, start_line, end_line, content "
            "FROM chunks WHERE id=?", (cid,),
        ).fetchone()
        if not row:
            continue
        path, coll, heading, s, e, content = row
        snippet = " ".join(content.split())[:300]
        results.append({
            "kb": name, "path": path, "collection": coll, "heading": heading,
            "lines": [s, e], "score": round(score, 5),
            "bm25_rank": merged[(name, cid)].get("bm25"),
            "vector_rank": merged[(name, cid)].get("vector"),
            "snippet": snippet,
        })

    payload = {
        "query": args.query, "mode": args.mode, "scope": args.kb or args.scope,
        "kbs_searched": [name for name, *_ in opened_targets],
        "vector_available": vector_available,
        "bm25_hits": bm25_hits, "vector_hits": vector_hits,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
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
        if not vector_available and args.mode == "hybrid":
            print("(BM25-only: vectors unavailable — is Ollama running? re-run 'magi index' after starting it)")
    return 0


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi index|search", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Build/refresh the hybrid retrieval index")
    p_index.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_index.add_argument("--no-vectors", action="store_true", help="Skip embeddings (BM25 only)")
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="Hybrid BM25+vector search with RRF fusion")
    p_search.add_argument("query")
    p_search.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    p_search.add_argument("--collection", choices=["concepts", "references", "topics", "theses", "raw", "drafts", "other"])
    p_search.add_argument("--path", help="Only search chunks whose file path matches this glob, "
                                         "e.g. --path 'raw/papers/2026-*higher-rank*' (applies per KB)")
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
