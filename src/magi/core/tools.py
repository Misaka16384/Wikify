"""Locating the external binaries MAGI shells out to.

Pandoc is not a pip dependency — it is a native binary the user installs — so
every route that needs it has to go looking. The search order was written once
inside tex2md and would have been copied into the next route that needed it.
"""

from __future__ import annotations

import os
import shutil

from magi.core.config_loader import load_config, get as cfg_get


def _from_env(var: str) -> str | None:
    path = os.environ.get(var)
    return path if path and os.path.exists(path) else None


def _from_config(cfg: dict, key: str) -> str | None:
    path = cfg_get(cfg, key, "") or None
    return path if path and os.path.exists(path) else None


def find_pandoc(cfg: dict | None = None) -> str:
    """Path to pandoc.

    Environment, then config.yaml, then PATH, then the default Windows install
    location — pandoc's own installer puts it under LOCALAPPDATA and does not
    always add it to PATH, which is a common way for this to look missing when
    it is not.

    Returns the bare name ``"pandoc"`` as a last resort so the caller fails at
    the subprocess with a legible message rather than here with a stack trace.
    """
    cfg = load_config() if cfg is None else cfg
    found = (_from_env("PANDOC_PATH")
             or _from_config(cfg, "tools.pandoc_path")
             or shutil.which("pandoc"))
    if found:
        return found
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        fallback = os.path.join(local_appdata, "Pandoc", "pandoc.exe")
        if os.path.exists(fallback):
            return fallback
    return "pandoc"


def find_pandoc_crossref(cfg: dict | None = None) -> str | None:
    """Path to pandoc-crossref, or None. Optional: without it cross-references
    degrade, which is a quality loss, not a failure."""
    cfg = load_config() if cfg is None else cfg
    return (_from_env("PANDOC_CROSSREF_PATH")
            or _from_config(cfg, "tools.pandoc_crossref_path")
            or shutil.which("pandoc-crossref"))


def have_pandoc(cfg: dict | None = None) -> bool:
    """Whether pandoc is really callable, as opposed to a last-resort guess."""
    cfg = load_config() if cfg is None else cfg
    return bool(_from_env("PANDOC_PATH")
                or _from_config(cfg, "tools.pandoc_path")
                or shutil.which("pandoc")
                or os.path.exists(os.path.join(
                    os.environ.get("LOCALAPPDATA", ""), "Pandoc", "pandoc.exe")))
