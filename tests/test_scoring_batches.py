"""Candidate scoring asks the embedder in batches, and keeps its own contracts.

`emb.embed(text)` is `embed_many([text])` underneath, so scoring a harvest one
candidate at a time made one request per paper where the embedder's configured
batch size asks for a handful. The connection is pooled by a `requests.Session`
either way — the saving is per-request latency and server-side batching, not
TCP handshakes, and there is no benchmark in this repository, so no speedup
factor is claimed anywhere.

The reason this needs tests rather than just a rewrite: batching moves the
early-exit and the dimension check across a loop boundary, and both of them
matter. An embedder that dies halfway must keep the scores already computed; a
vector of the wrong width means the index was built with a different model and
scoring must refuse rather than produce numbers.
"""

import types

import pytest

np = pytest.importorskip("numpy")

from magi import radar


class _Emb:
    """Records what it was asked for, in the shape it was asked."""

    def __init__(self, dims=4, batch=3, die_after=None):
        self.batch = batch
        self.calls = []
        self._dims = dims
        self._die_after = die_after

    def embed_many(self, texts, timeout=None):
        self.calls.append(list(texts))
        if self._die_after is not None and len(self.calls) > self._die_after:
            return None
        return [[1.0] + [0.0] * (self._dims - 1) for _ in texts]


def _score(monkeypatch, tmp_path, cands, emb, *, index_dims=None):
    """Drive `_score_candidates` with a stubbed index and embedder.

    `Embedder` and `open_db` are imported inside the function from
    `magi.retrieval`, so that is where they have to be replaced.
    """
    from magi import retrieval

    dims = emb._dims if index_dims is None else index_dims
    (tmp_path / "output").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "index.db").write_bytes(b"")

    class _Conn:
        def execute(self, *a, **k):
            vec = np.zeros(dims, dtype=np.float32)
            vec[0] = 1.0
            return types.SimpleNamespace(fetchall=lambda: [("p.md", vec.tobytes())])

        def close(self):
            pass

    monkeypatch.setattr(retrieval, "Embedder", lambda start=None: emb)
    monkeypatch.setattr(retrieval, "open_db", lambda *a, **k: (_Conn(), True))
    return radar._score_candidates(tmp_path, cands)


def _cands(n):
    return [{"title": f"paper {i}", "abstract": "abs " * 10} for i in range(n)]


def test_scoring_asks_in_batches_not_one_at_a_time(monkeypatch, tmp_path):
    emb = _Emb(batch=3)
    cands = _cands(7)
    assert _score(monkeypatch, tmp_path, cands, emb) is True
    assert [len(c) for c in emb.calls] == [3, 3, 1]


def test_every_candidate_gets_its_own_score(monkeypatch, tmp_path):
    emb = _Emb(batch=3)
    cands = _cands(7)
    _score(monkeypatch, tmp_path, cands, emb)
    assert all("score" in c for c in cands)


def test_a_candidate_with_no_text_is_skipped_not_sent(monkeypatch, tmp_path):
    emb = _Emb(batch=10)
    cands = _cands(2) + [{"title": "", "abstract": ""}]
    _score(monkeypatch, tmp_path, cands, emb)
    assert len(emb.calls[0]) == 2
    assert "score" not in cands[-1]


def test_an_embedder_that_dies_keeps_what_was_already_scored(monkeypatch, tmp_path):
    """The early exit used to be inside the per-candidate loop. Across a batch
    boundary it has to mean the same thing."""
    emb = _Emb(batch=2, die_after=1)
    cands = _cands(6)
    assert _score(monkeypatch, tmp_path, cands, emb) is True
    assert [("score" in c) for c in cands] == [True, True, False, False, False, False]


def test_a_vector_of_the_wrong_width_refuses_to_score_anything(monkeypatch, tmp_path):
    """A different embedding model, not a transient failure. Producing numbers
    from it would be worse than producing none."""
    emb = _Emb(dims=4, batch=3)
    cands = _cands(4)
    assert _score(monkeypatch, tmp_path, cands, emb, index_dims=8) is False
    assert not any("score" in c for c in cands)


def test_no_candidates_means_no_requests(monkeypatch, tmp_path):
    emb = _Emb()
    _score(monkeypatch, tmp_path, [], emb)
    assert emb.calls == []
