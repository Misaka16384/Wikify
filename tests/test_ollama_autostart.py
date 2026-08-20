"""A stopped Ollama is not an error state — MAGI starts it.

Only two things need a human: it is not installed, or the model is not
pulled. These tests pin that split, and pin the guards that keep the
autostart from being stupid (remote endpoints, retry storms).
"""

from __future__ import annotations

import pytest

from magi.core import ollama as ol


@pytest.fixture(autouse=True)
def fresh_attempts():
    ol.reset_cache()
    yield
    ol.reset_cache()


# --------------------------------------------------------------------------
# model matching
# --------------------------------------------------------------------------

@pytest.mark.parametrize("installed,wanted,expected", [
    (["qwen3-embedding:0.6b"], "qwen3-embedding:0.6b", True),
    # /api/embeddings 404s on a tag Ollama does not have, so "close enough"
    # would only move the failure later.
    (["qwen3-embedding:4b"], "qwen3-embedding:0.6b", False),
    (["glm-ocr:latest"], "glm-ocr", True),          # bare name means :latest
    (["glm-ocr:v2"], "glm-ocr", False),
    ([], "anything", False),
])
def test_has_model_is_exact_about_tags(installed, wanted, expected):
    assert ol.OllamaState("", True, installed).has_model(wanted) is expected


def test_matching_offers_the_tags_you_do_have():
    state = ol.OllamaState("", True, ["qwen3-embedding:4b", "bge-m3:latest"])
    assert state.matching("qwen3-embedding:0.6b") == ["qwen3-embedding:4b"]


# --------------------------------------------------------------------------
# probing and locality
# --------------------------------------------------------------------------

def test_probe_returns_none_when_nothing_answers(monkeypatch):
    monkeypatch.setattr(ol.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("refused")))
    assert ol.probe("http://127.0.0.1:11434") is None


@pytest.mark.parametrize("url,local", [
    ("http://127.0.0.1:11434", True),
    ("http://localhost:11434", True),
    ("http://192.168.1.50:11434", False),
    ("https://ollama.example.com", False),
])
def test_is_local_decides_whether_starting_could_possibly_help(url, local):
    assert ol.is_local(url) is local


# --------------------------------------------------------------------------
# ensure()
# --------------------------------------------------------------------------

def test_running_server_is_reported_without_touching_the_binary(monkeypatch):
    monkeypatch.setattr(ol, "probe", lambda *a, **k: ["qwen3-embedding:0.6b"])
    monkeypatch.setattr(ol.shutil, "which",
                        lambda name: pytest.fail("must not look for the binary"))
    state = ol.ensure("http://127.0.0.1:11434", autostart=True)
    assert state.running and not state.started and state.reason == ""


def test_a_stopped_local_server_gets_started(monkeypatch):
    calls = {"start": 0}
    monkeypatch.setattr(ol.shutil, "which", lambda name: "/usr/bin/ollama")

    def fake_start(base_url=None, wait=30.0):
        calls["start"] += 1
        return True

    answers = iter([None, ["bge-m3:latest"]])
    monkeypatch.setattr(ol, "probe", lambda *a, **k: next(answers))
    monkeypatch.setattr(ol, "start", fake_start)

    state = ol.ensure("http://127.0.0.1:11434", autostart=True)
    assert state.running and state.started and calls["start"] == 1
    assert ol.hint(state, "bge-m3") is None   # nothing here needs a human


def test_a_missing_install_is_the_thing_worth_saying(monkeypatch):
    monkeypatch.setattr(ol, "probe", lambda *a, **k: None)
    monkeypatch.setattr(ol.shutil, "which", lambda name: None)
    monkeypatch.setattr(ol, "start", lambda *a, **k: pytest.fail("nothing to start"))

    state = ol.ensure("http://127.0.0.1:11434", autostart=True)
    assert not state.running and state.reason == "not-installed"
    assert "ollama.com" in ol.hint(state)


def test_a_remote_endpoint_is_never_started_locally(monkeypatch):
    monkeypatch.setattr(ol, "probe", lambda *a, **k: None)
    monkeypatch.setattr(ol, "start", lambda *a, **k: pytest.fail("not ours to start"))
    state = ol.ensure("http://192.168.1.50:11434", autostart=True)
    assert state.reason == "remote"
    assert "cannot start it" in ol.hint(state)


def test_one_start_attempt_per_process(monkeypatch):
    """Without the cache every vector call site pays a spawn plus a timeout."""
    calls = {"start": 0}
    monkeypatch.setattr(ol, "probe", lambda *a, **k: None)
    monkeypatch.setattr(ol.shutil, "which", lambda name: "/usr/bin/ollama")

    def fake_start(base_url=None, wait=30.0):
        calls["start"] += 1
        return False

    monkeypatch.setattr(ol, "start", fake_start)
    for _ in range(4):
        state = ol.ensure("http://127.0.0.1:11434", autostart=True)
    assert calls["start"] == 1
    assert state.reason == "start-failed"


def test_autostart_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(ol, "probe", lambda *a, **k: None)
    monkeypatch.setattr(ol, "start", lambda *a, **k: pytest.fail("autostart is off"))
    state = ol.ensure("http://127.0.0.1:11434", autostart=False)
    assert state.reason == "stopped"


def test_env_switch_turns_autostart_off(monkeypatch):
    monkeypatch.setenv("MAGI_NO_OLLAMA_AUTOSTART", "1")
    assert ol._configured_autostart() is False


def test_config_default_is_on():
    from magi.core.config_loader import get as cfg_get, load_config

    assert cfg_get(load_config(), "ollama.autostart", None) is True


# --------------------------------------------------------------------------
# hints
# --------------------------------------------------------------------------

def test_an_unpulled_model_names_the_pull_command():
    state = ol.OllamaState("http://127.0.0.1:11434", True, ["bge-m3:latest"])
    msg = ol.hint(state, "qwen3-embedding:0.6b")
    assert "ollama pull qwen3-embedding:0.6b" in msg


def test_a_near_miss_points_at_the_tag_you_have():
    state = ol.OllamaState("http://127.0.0.1:11434", True, ["qwen3-embedding:4b"])
    msg = ol.hint(state, "qwen3-embedding:0.6b")
    assert "qwen3-embedding:4b" in msg and "models.embedding" in msg


def test_a_custom_port_is_passed_to_the_server_it_starts():
    env = ol._serve_env("http://127.0.0.1:11500")
    assert env["OLLAMA_HOST"] == "127.0.0.1:11500"
    assert "OLLAMA_HOST" not in ol._serve_env("http://127.0.0.1:11434")


def test_the_embedder_degrades_quietly_when_ollama_is_absent(monkeypatch):
    """`magi index` must still build BM25 with no Ollama anywhere."""
    from magi import retrieval

    monkeypatch.setattr(ol, "probe", lambda *a, **k: None)
    monkeypatch.setattr(ol.shutil, "which", lambda name: None)
    emb = retrieval.Embedder()
    assert emb.embed("anything") is None
    assert emb.available is False
