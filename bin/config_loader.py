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
    },
    "models": {
        "ocr": "glm-ocr",
        "embedding": "qwen3-embedding:0.6b",
    },
    "ocr": {
        "timeout": 180,
        "dpi": 150,
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
    """Walk upward from *start* looking for ``config.yaml``.

    Search order:
      1. *start* directory itself
      2. Parent directories up to 3 levels
    """
    if start is None:
        start = str(Path(__file__).parent)  # bin/

    current = Path(start).resolve()
    for _ in range(4):  # self + 3 parents
        candidate = current / "config.yaml"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> dict[str, Any]:
    """Load the unified configuration.

    Parameters
    ----------
    config_path : str, optional
        Explicit path to a YAML config file.  When *None*, the loader
        auto-discovers ``config.yaml`` by walking up from ``bin/``.

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
        yaml_path = _find_config_yaml()
        if yaml_path is not None and yaml is not None:
            try:
                with open(yaml_path, "r", encoding="utf-8") as fh:
                    user_cfg = yaml.safe_load(fh)
                if isinstance(user_cfg, dict):
                    config = _deep_merge(config, user_cfg)
            except Exception:
                pass  # Fall through to defaults on any parse error

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
    'glm-ocr'
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
