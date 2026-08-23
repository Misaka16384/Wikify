"""The browser extension has its own version, and must actually bump it.

Chrome requires an extension's version to increase for an update to install,
and it is not MAGI's version: the extension can go untouched across three MAGI
patch releases, and can equally need a fix of its own between them. Two lines
that move independently.

What breaks silently is shipping changed extension files under an unchanged
version — Chrome then refuses the update and every user keeps the old popup,
with nothing anywhere saying so. So the rule is checked here rather than
remembered, the same way `test_docs_in_sync.py` catches documentation drift.

The comparison is against the last release tag, because that is the last
version of the extension anyone could have installed.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser-extension"
MANIFEST = EXT / "manifest.json"


def _git(*args) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def test_the_manifest_is_valid_json_with_a_version():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+(\.\d+){0,3}", data["version"]), data["version"]
    # Chrome's own rule: at most four dot-separated integers, each < 65536.
    assert all(int(p) < 65536 for p in data["version"].split("."))


def test_every_locale_named_by_the_manifest_exists():
    """`default_locale` pointing at a missing directory fails the pack, and
    fails it at release time rather than here — which is the wrong end."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    default = data.get("default_locale")
    if default is None:
        pytest.skip("no _locales in use")
    assert (EXT / "_locales" / default / "messages.json").is_file()

    used = set(re.findall(r"__MSG_([A-Za-z0-9_]+)__", MANIFEST.read_text(encoding="utf-8")))
    for locale_dir in (EXT / "_locales").iterdir():
        if not locale_dir.is_dir():
            continue
        messages = json.loads((locale_dir / "messages.json").read_text(encoding="utf-8"))
        missing = used - set(messages)
        assert not missing, f"{locale_dir.name} is missing {sorted(missing)}"


def test_changing_the_extension_bumps_its_version():
    """Files changed since the last release tag => the version moved too."""
    tag = _git("describe", "--tags", "--abbrev=0", "--match", "v*")
    if tag is None:
        pytest.skip("no git history available")

    changed = _git("diff", "--name-only", tag, "--", "browser-extension")
    if changed is None:
        pytest.skip("could not diff against " + tag)
    changed_files = [line for line in changed.split("\n") if line.strip()]
    if not changed_files:
        return  # untouched since the last release: nothing to bump

    old_manifest = _git("show", f"{tag}:browser-extension/manifest.json")
    if old_manifest is None:
        return  # the extension did not exist at that tag

    old = _version_tuple(json.loads(old_manifest)["version"])
    new = _version_tuple(json.loads(MANIFEST.read_text(encoding="utf-8"))["version"])
    assert new > old, (
        f"browser-extension changed since {tag} "
        f"({', '.join(Path(f).name for f in changed_files)}) but manifest.json "
        f"is still {'.'.join(map(str, old))}. Chrome refuses an update that "
        f"does not increase the version, so every user would keep the old one.")
