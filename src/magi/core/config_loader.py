"""Unified configuration loader for Gemini Wiki Skills.

All scripts share a single project-level ``config.yaml``.  This module
handles discovery, loading, environment-variable overrides, and provides
a convenient dotted-key accessor.

Priority (high → low):
  1. Caller-supplied *config_path*  (e.g. ``agent.py -c custom.yaml``)
  2. Environment variables          (``OLLAMA_HOST``, ``PDFTOPPM_PATH``, …)
  3. Project-level ``config.yaml``  (auto-discovered)
  4. Built-in defaults below
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Built-in defaults — single source of truth
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        # A stopped local server is not an error state — MAGI starts it. Set
        # this false to keep `ollama serve` under your own control.
        "autostart": True,
    },
    "models": {
        "ocr": "glm-ocr:q8_0",
        "embedding": "qwen3-embedding:0.6b",
    },
    "ocr": {
        "timeout": 180,
        "dpi": 150,
    },
    "ingest": {
        # `pymupdf4llm` exports every embedded image *object*, not every
        # figure, and inlines each one into the Markdown. Measured on a real
        # paper with 4 figures: 117 files, 102 of them under 200x200, the
        # smallest 301x24 and 40x24 -- single display-equation strips turned
        # into pictures. Its `image_size_limit` knob does not help: to_markdown
        # is (*args, **kwargs) and silently ignores what it does not use, so
        # 0.05 and 0.25 produce byte-identical output. Off by default; the OCR
        # route crops figures by caption anchor and is the one to use for them.
        "textlayer_images": False,
    },
    "semantic_link": {
        "threshold": 0.75,
        "merge_threshold": 0.85,
        "auto_merge_threshold": 0.95,
    },
    "tools": {
        "pdftoppm_path": "",
        "pdfimages_path": "",
        "pandoc_path": "",
        "pandoc_crossref_path": "",
    },
    "pdf": {
        "image_format": "png",
        "quality": 100,
    },
    "output": {
        "keep_temp_images": False,
        "image_folder": "images",
        "encoding": "utf-8",
    },
}

# Environment variables that override specific config keys.
_ENV_OVERRIDES: list[tuple[str, str]] = [
    ("OLLAMA_HOST",           "ollama.base_url"),
    ("PDFTOPPM_PATH",         "tools.pdftoppm_path"),
    ("PDFIMAGES_PATH",        "tools.pdfimages_path"),
    ("PANDOC_PATH",           "tools.pandoc_path"),
    ("PANDOC_CROSSREF_PATH",  "tools.pandoc_crossref_path"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict with *override* merged into *base* (recursive)."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _set_dotted(d: dict, dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using ``'a.b.c'`` notation."""
    keys = dotted_key.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _find_config_yaml(start: Optional[str] = None) -> Optional[Path]:
    """Locate the effective ``config.yaml``.

    Delegates to :func:`magi.core.workspace.find_config_yaml`: upward walk
    from *start* (default: cwd) so workspace-/hub-level configs win, then
    the user config dir ``~/.config/magi/config.yaml``. The historic
    walk-up-from-``bin/`` behavior is gone — installed packages have no
    meaningful ``__file__`` ancestry.
    """
    from magi.core.workspace import find_config_yaml

    return find_config_yaml(start)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None,
                start: Optional[str | os.PathLike] = None) -> dict[str, Any]:
    """Load the unified configuration.

    Parameters
    ----------
    config_path : str, optional
        Explicit path to a YAML config file.
    start : path-like, optional
        Where to begin the upward search for ``config.yaml``. Defaults to the
        process cwd.

        **Pass the workspace whenever you have one.** Commands that take
        ``--topic-dir`` used to resolve the workspace for their *output* but
        leave config discovery on cwd, so pointing a command at one workspace
        from inside another silently applied the wrong settings. The worst
        case was the scheduler: `radar install-schedule` registers
        ``magi radar harvest --topic-dir <ws>`` with no working directory, so
        the nightly run discovered no config at all and harvested with an
        empty category list — producing a plausible-looking digest that had
        silently lost half its sources.

    Returns
    -------
    dict
        Fully-merged configuration dictionary.
    """
    import copy
    config = copy.deepcopy(_DEFAULTS)

    # --- Layer 1: YAML file ---
    yaml_path: Optional[Path] = None
    if config_path is not None:
        yaml_path = Path(config_path)
        if not yaml_path.is_file():
            raise FileNotFoundError(
                f"Config file not found: {yaml_path}"
            )
        if yaml is not None:
            with open(yaml_path, "r", encoding="utf-8") as fh:
                user_cfg = yaml.safe_load(fh)
            if not isinstance(user_cfg, dict):
                raise ValueError(f"Config file must be a YAML mapping, got {type(user_cfg).__name__}")
            config = _deep_merge(config, user_cfg)
    else:
        # Two layers, not two candidates. The user file used to be reachable
        # only when no workspace config existed anywhere above the cwd — and
        # every `magi init` workspace writes one at its root, so in practice it
        # was never read at all. Anything that belongs to the person rather
        # than to a topic had to be copied into every workspace: measured on
        # one machine, the same MinerU token stored three times, with no single
        # place to change it.
        #
        # Now the user file is the base and the workspace file overrides it,
        # key by key, so a token can live in one place and a topic can still
        # differ where it means to.
        from magi.core.workspace import find_workspace_config_yaml, user_config_yaml

        for layer in (user_config_yaml(), find_workspace_config_yaml(start)):
            if layer is None or yaml is None:
                continue
            yaml_path = layer
            try:
                with open(layer, "r", encoding="utf-8") as fh:
                    user_cfg = yaml.safe_load(fh)
            except Exception as exc:
                # Silently falling back to defaults here is how a one-character
                # YAML typo turns into "radar found nothing today" with an exit
                # code of 0. The defaults still apply — but say so.
                print(f"warning: could not read {layer} ({exc}); ignoring it",
                      file=sys.stderr)
                continue
            if user_cfg is None:
                continue
            if not isinstance(user_cfg, dict):
                print(f"warning: {layer} is not a YAML mapping "
                      f"({type(user_cfg).__name__}); ignoring it", file=sys.stderr)
                continue
            config = _deep_merge(config, user_cfg)

    # --- Layer 2: Environment variable overrides ---
    for env_var, dotted_key in _ENV_OVERRIDES:
        env_val = os.environ.get(env_var)
        if env_val:
            _set_dotted(config, dotted_key, env_val)

    return config


def get(config: dict, dotted_key: str, default: Any = None) -> Any:
    """Retrieve a value from a nested dict using ``'a.b.c'`` notation.

    >>> cfg = load_config()
    >>> get(cfg, 'models.ocr')
    'glm-ocr:q8_0'
    >>> get(cfg, 'ocr.timeout')
    180
    """
    keys = dotted_key.split(".")
    current: Any = config
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current
