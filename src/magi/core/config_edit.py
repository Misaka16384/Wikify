"""Surgical edits to a workspace config.yaml.

Rewrites exactly one `section.key` value in place, preserving every other
line — including comments, ordering, and unknown keys. Scalars replace the
value on the existing line; block lists are collapsed to flow style
(`key: [a, b]`). Missing sections/keys are appended.

The rewritten text is parsed back with yaml.safe_load BEFORE it is written,
so a bug here can never corrupt a workspace config on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


class ConfigEditError(Exception):
    pass


def _fmt_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def set_config_value(config_path: Path, dotted_key: str, value) -> None:
    if "." not in dotted_key:
        raise ConfigEditError(f"expected section.key, got '{dotted_key}'")
    section, key = dotted_key.split(".", 1)
    if "." in key:
        raise ConfigEditError("only one nesting level is supported")

    lines = (config_path.read_text(encoding="utf-8").splitlines()
             if config_path.is_file() else [])
    rendered = _fmt_value(value)

    sec_idx = None
    for i, ln in enumerate(lines):
        if re.match(rf"^{re.escape(section)}:\s*(#.*)?$", ln):
            sec_idx = i
            break

    if sec_idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"{section}:", f"  {key}: {rendered}"]
    else:
        # section block ends at the next non-indented, non-blank line
        end = len(lines)
        for j in range(sec_idx + 1, len(lines)):
            if lines[j].strip() and not lines[j][0].isspace():
                end = j
                break

        key_idx = None
        for j in range(sec_idx + 1, end):
            if re.match(rf"^\s+{re.escape(key)}:", lines[j]):
                key_idx = j
                break

        if key_idx is None:
            lines.insert(sec_idx + 1, f"  {key}: {rendered}")
        else:
            indent = re.match(r"^(\s+)", lines[key_idx]).group(1)
            # swallow any block-style continuation lines (deeper indent)
            k_end = key_idx + 1
            while k_end < end:
                ln = lines[k_end]
                if not ln.strip():
                    break
                cur = len(ln) - len(ln.lstrip())
                if cur <= len(indent):
                    break
                k_end += 1
            lines[key_idx:k_end] = [f"{indent}{key}: {rendered}"]

    text = "\n".join(lines) + "\n"
    try:
        parsed = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ConfigEditError(f"edit would corrupt YAML: {exc}") from exc
    if (parsed.get(section) or {}).get(key) != value:
        raise ConfigEditError("edit verification failed — value did not round-trip")
    config_path.write_text(text, encoding="utf-8")
