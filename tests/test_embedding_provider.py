"""The second embedding provider: any OpenAI-compatible /v1/embeddings.

Ollama is a local install, and plenty of people do not want one. One code
path covers every service that speaks OpenAI's embeddings schema —
SiliconFlow, Jina, Gemini's compatibility layer, DeepInfra, OpenAI itself.
Providers with a bespoke schema (Cohere, Voyage, Zhipu) are deliberately out.

Nothing here touches the network: the HTTP session is stubbed at the seam.
"""

from __future__ import annotations

import pytest

from magi import retrieval


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Records every request so the test can assert on what went out."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        return FakeResponse(self.payload)


@pytest.fixture
def cloud(monkeypatch):
    """An Embedder configured for a cloud endpoint, with no network."""
    cfg = {
        "embedding": {
            "provider": "openai",
            "base_url": "https://api.siliconflow.com/v1",
            "model": "BAAI/bge-m3",
            "api_key": "sk-test-key",
        }
    }
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: cfg)
    monkeypatch.delenv("MAGI_EMBEDDING_API_KEY", raising=False)
    return retrieval.Embedder()


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

def test_the_default_provider_is_still_ollama(monkeypatch):
    """Nobody's working setup may change because a second option appeared."""
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: {})
    e = retrieval.Embedder()
    assert e.provider == "ollama"
    assert e.base_url == "http://127.0.0.1:11434"
    assert e.model == "qwen3-embedding:0.6b"


def test_cloud_settings_are_read(cloud):
    assert cloud.provider == "openai"
    assert cloud.base_url == "https://api.siliconflow.com/v1"
    assert cloud.model == "BAAI/bge-m3"
    assert cloud.api_key == "sk-test-key"


def test_the_env_var_beats_the_config_file(monkeypatch):
    """A key in config.yaml is a secret in a file people commit. The env var
    is offered first and has to win, or setting it would look ignored."""
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: {
        "embedding": {"provider": "openai", "api_key": "from-file"}})
    monkeypatch.setenv("MAGI_EMBEDDING_API_KEY", "from-env")
    assert retrieval.Embedder().api_key == "from-env"


def test_a_blank_env_var_does_not_shadow_the_file(monkeypatch):
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: {
        "embedding": {"provider": "openai", "api_key": "from-file"}})
    monkeypatch.setenv("MAGI_EMBEDDING_API_KEY", "   ")
    assert retrieval.Embedder().api_key == "from-file"


def test_the_model_falls_back_to_the_shared_setting(monkeypatch):
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: {
        "embedding": {"provider": "openai", "api_key": "k"},
        "models": {"embedding": "text-embedding-3-small"}})
    assert retrieval.Embedder().model == "text-embedding-3-small"


# --------------------------------------------------------------------------
# the request
# --------------------------------------------------------------------------

def test_it_calls_the_openai_route_with_a_bearer_token(cloud, monkeypatch):
    session = FakeSession({"data": [
        {"index": 0, "embedding": [0.1, 0.2]},
        {"index": 1, "embedding": [0.3, 0.4]},
    ]})
    monkeypatch.setattr(cloud, "_http", lambda: session)

    out = cloud._post_batch(["a", "b"])

    assert out == [[0.1, 0.2], [0.3, 0.4]]
    call = session.calls[0]
    assert call["url"] == "https://api.siliconflow.com/v1/embeddings"
    assert call["headers"]["Authorization"] == "Bearer sk-test-key"
    assert call["json"] == {"model": "BAAI/bge-m3", "input": ["a", "b"]}
    # /api/embed is Ollama's route and must never be used for a cloud call.
    assert "/api/embed" not in call["url"]


def test_rows_are_reordered_by_index(cloud, monkeypatch):
    """OpenAI does not guarantee response order and gives each row an index.

    Trusting arrival order would attach every vector to the wrong chunk —
    silently, since the shapes still line up.
    """
    session = FakeSession({"data": [
        {"index": 2, "embedding": [3.0]},
        {"index": 0, "embedding": [1.0]},
        {"index": 1, "embedding": [2.0]},
    ]})
    monkeypatch.setattr(cloud, "_http", lambda: session)
    assert cloud._post_batch(["a", "b", "c"]) == [[1.0], [2.0], [3.0]]


def test_a_short_batch_raises_rather_than_misaligning(cloud, monkeypatch):
    session = FakeSession({"data": [{"index": 0, "embedding": [1.0]}]})
    monkeypatch.setattr(cloud, "_http", lambda: session)
    with pytest.raises(ValueError, match="asked for 2"):
        cloud._post_batch(["a", "b"])


def test_an_empty_vector_raises(cloud, monkeypatch):
    session = FakeSession({"data": [
        {"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": []}]})
    monkeypatch.setattr(cloud, "_http", lambda: session)
    with pytest.raises(ValueError, match="empty embedding"):
        cloud._post_batch(["a", "b"])


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------

def test_a_cloud_provider_never_tries_to_start_ollama(cloud, monkeypatch):
    """Autostart exists for a local install. Reaching for it on a cloud
    provider would spawn `ollama serve` on a machine that has no Ollama."""
    from magi.core import ollama as ollama_svc

    def boom(*a, **k):
        raise AssertionError("tried to touch Ollama for a cloud provider")

    monkeypatch.setattr(ollama_svc, "ensure_model", boom)
    assert cloud._preflight() is True


def test_a_missing_key_is_reported_once_not_per_batch(monkeypatch, capsys):
    monkeypatch.setattr(retrieval, "load_config", lambda *a, **k: {
        "embedding": {"provider": "openai", "base_url": "https://x/v1"}})
    monkeypatch.delenv("MAGI_EMBEDDING_API_KEY", raising=False)
    e = retrieval.Embedder()

    assert e._preflight() is False
    assert e.available is False
    err = capsys.readouterr().err
    assert "no API key" in err
    # Second call is silent — the flag is already set.
    assert e._preflight() is False
    assert "no API key" not in capsys.readouterr().err


# --------------------------------------------------------------------------
# the index that already exists
# --------------------------------------------------------------------------

def test_changing_model_width_refuses_instead_of_corrupting(tmp_path):
    """The vector table is created at a fixed width and cannot be widened.

    Without this the switch keeps the old table and starts writing rows that
    do not fit it — search then returns nonsense rather than an error.
    """
    db = tmp_path / "index.db"
    opened = retrieval.open_db(db, create=True)
    assert opened is not None
    conn, vec_loaded = opened
    if not vec_loaded:
        pytest.skip("sqlite-vec is not loadable here")

    retrieval.ensure_schema(conn, 1024, vec_loaded)
    with pytest.raises(retrieval.SearchError) as exc:
        retrieval.ensure_schema(conn, 1536, vec_loaded)
    assert "1024" in exc.value.msg and "1536" in exc.value.msg
    assert "--rebuild" in (exc.value.hint or "")


def test_the_rebuild_flag_the_hint_names_exists():
    """A remediation hint naming a flag that does not exist is worse than
    none: the reader tries it, argparse exits 2, and they are stuck.

    The parser is built inside main(), so `--help` is what there is to ask.
    """
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-m", "magi.cli", "index", "--help"],
                         capture_output=True, text=True, timeout=60)
    assert "--rebuild" in out.stdout, out.stdout[-400:]
