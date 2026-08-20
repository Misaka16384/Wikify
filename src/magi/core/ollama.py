#!/usr/bin/env python3
"""Ollama liveness — probe first, and wake the server when it is only asleep.

"Ollama is not running" is not news the user needs: the binary is on PATH,
starting it costs a second, and every vector path in MAGI silently degrades to
BM25 without it. Two states *do* need a human — Ollama is not installed, and
the model is not pulled — so those are the only ones this module reports.

Every vector-shaped call site goes through :func:`ensure`, which starts the
server at most once per process: on a machine without Ollama the alternative
is paying a spawn plus a connect timeout on each of them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "http://127.0.0.1:11434"

# Hosts where "start the server" is a meaningful response to a refused
# connection. Waking a local daemon cannot fix a remote endpoint being down.
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0", ""}

# base_url -> OllamaState for bases we already tried to start. The WebUI calls
# ensure() from FastAPI's thread pool, so two requests can arrive together;
# without the lock they would each pay the spawn and the timeout.
_attempts: dict[str, "OllamaState"] = {}
_attempts_lock = threading.Lock()


@dataclass
class OllamaState:
    """What we know about one Ollama endpoint, after trying to reach it."""

    base_url: str
    running: bool
    models: list[str] = field(default_factory=list)
    started: bool = False   # this process spawned the server
    reason: str = ""        # "" | not-installed | remote | start-failed | start-timeout

    def has_model(self, model: str) -> bool:
        """Is exactly this tag pulled?

        Exact, not base-name: ``/api/embeddings`` 404s on a tag it does not
        have, so "qwen3-embedding:0.6b is close enough to :latest" would just
        move the failure later. A bare name means ``:latest``, which is how
        Ollama itself resolves it.
        """
        if not model:
            return False
        want = model if ":" in model else f"{model}:latest"
        return want in self.models

    def matching(self, model: str) -> list[str]:
        """Tags installed for *model*'s base name — the "did you mean" list."""
        base = model.split(":")[0]
        return [m for m in self.models if m.split(":")[0] == base]


# --------------------------------------------------------------------------
# probing
# --------------------------------------------------------------------------

def normalize(base_url: str | None) -> str:
    return (base_url or DEFAULT_BASE_URL).rstrip("/")


def is_local(base_url: str | None) -> bool:
    host = urllib.parse.urlsplit(normalize(base_url)).hostname
    return (host or "") in _LOCAL_HOSTS


def probe(base_url: str | None = None, timeout: float = 2.0) -> list[str] | None:
    """Installed model tags, or ``None`` when nothing answers.

    An empty list means "server up, no models pulled" — check ``is None``,
    not falsiness.
    """
    url = f"{normalize(base_url)}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


# --------------------------------------------------------------------------
# starting
# --------------------------------------------------------------------------

def _serve_env(base_url: str) -> dict[str, str]:
    env = dict(os.environ)
    parts = urllib.parse.urlsplit(normalize(base_url))
    if parts.netloc and parts.netloc != "127.0.0.1:11434":
        # `ollama serve` binds OLLAMA_HOST, not whatever we happen to poll —
        # a config pointing at :11500 would otherwise start a server we never
        # talk to.
        env["OLLAMA_HOST"] = parts.netloc
    return env


def start(base_url: str | None = None, wait: float = 30.0) -> bool:
    """Spawn a detached ``ollama serve`` and wait for it to answer.

    Returns False if the binary is missing, the spawn fails, or the server
    does not come up inside *wait* seconds.
    """
    exe = shutil.which("ollama")
    if not exe:
        return False

    kwargs: dict = {}
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: no console window, and
        # the server outlives the magi command that woke it.
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=_serve_env(base_url or DEFAULT_BASE_URL),
            **kwargs,
        )
    except Exception:
        return False

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(0.4)
        if probe(base_url, timeout=1.5) is not None:
            return True
    return False


# --------------------------------------------------------------------------
# the one entry point
# --------------------------------------------------------------------------

def ensure(
    base_url: str | None = None,
    *,
    autostart: bool | None = None,
    wait: float = 30.0,
) -> OllamaState:
    """Reach Ollama, starting it if that is all it takes.

    *autostart* defaults to ``ollama.autostart`` in config.yaml (on). Set it
    False to probe only — ``magi doctor`` reports state, it does not change it.
    """
    base = normalize(base_url or _configured_base())
    if autostart is None:
        autostart = _configured_autostart()

    models = probe(base, timeout=2.0)
    if models is not None:
        return OllamaState(base, True, models)

    if not autostart:
        return OllamaState(base, False, reason="stopped")
    if not is_local(base):
        return OllamaState(base, False, reason="remote")
    with _attempts_lock:
        if base in _attempts:
            # One attempt per process; a second caller gets the same verdict
            # without paying the spawn and the timeout again.
            return _attempts[base]
        if not shutil.which("ollama"):
            state = OllamaState(base, False, reason="not-installed")
            _attempts[base] = state
            return state

        ok = start(base, wait=wait)
        models = probe(base, timeout=2.0) if ok else None
        if models is None:
            state = OllamaState(base, False, reason="start-timeout" if ok else "start-failed")
        else:
            state = OllamaState(base, True, models, started=True)
        _attempts[base] = state
        return state


def hint(state: OllamaState, model: str | None = None) -> str | None:
    """One actionable line, or ``None`` when nothing needs a human.

    A server we just started is not worth a line; a missing install or a
    missing model is.
    """
    if not state.running:
        if state.reason == "not-installed":
            return ("Ollama is not installed — retrieval stays BM25-only "
                    "(install from https://ollama.com to enable vectors)")
        if state.reason == "remote":
            return (f"Ollama at {state.base_url} is unreachable — it is not a local "
                    f"server, so MAGI cannot start it for you")
        if state.reason == "stopped":
            return f"Ollama at {state.base_url} is not running (autostart is off)"
        return (f"Ollama would not start (`ollama serve` at {state.base_url}) — "
                f"try running it in a terminal to see why")
    if model and not state.has_model(model):
        near = state.matching(model)
        if near:
            return (f"Embedding model '{model}' is not pulled; you do have "
                    f"{', '.join(near)} — set models.embedding in config.yaml, "
                    f"or run: ollama pull {model}")
        return f"Embedding model '{model}' is not pulled — run: ollama pull {model}"
    return None


def ensure_model(
    base_url: str | None = None,
    model: str | None = None,
    *,
    autostart: bool | None = None,
    quiet: bool = False,
) -> tuple[OllamaState, str | None]:
    """:func:`ensure` plus the model check, with the hint printed once.

    Returns the state and the hint, so callers can decide between degrading
    (retrieval) and exiting (`magi link`).
    """
    state = ensure(base_url, autostart=autostart)
    msg = hint(state, model)
    if msg and not quiet:
        print(f"note: {msg}", file=sys.stderr)
    return state, msg


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def _configured_base() -> str:
    try:
        from magi.core.config_loader import get as cfg_get, load_config

        return cfg_get(load_config(), "ollama.base_url", DEFAULT_BASE_URL)
    except Exception:
        return DEFAULT_BASE_URL


def _configured_autostart() -> bool:
    if os.environ.get("MAGI_NO_OLLAMA_AUTOSTART"):
        return False
    try:
        from magi.core.config_loader import get as cfg_get, load_config

        return bool(cfg_get(load_config(), "ollama.autostart", True))
    except Exception:
        return True


def reset_cache() -> None:
    """Forget start attempts — for tests, and for long-lived servers."""
    with _attempts_lock:
        _attempts.clear()
