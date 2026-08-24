"""The registry is the one file here that nothing can rebuild.

`registry.json` and `settings.json` are not derived data. They hold what a
person set up by hand — which libraries exist, which are searchable, which
optional tools they said they would install. `output/` can be deleted and
regenerated; these cannot.

They were written with a plain `write_text` over the target, read back with a
`except json.JSONDecodeError: pass` that returned an empty registry, and
mutated by unlocked load/modify/save pairs in seven places. Three failures
follow from that, in increasing order of how quiet they are:

* a crash or a full disk mid-write leaves a half-written file;
* that half-written file then parses as "no libraries at all", and the next
  save writes the emptiness over the original — a truncated file becomes **no**
  file, with nothing printed;
* two processes changing different keys at once, and the second writing back a
  picture taken before the first one's change. `magi index` registers a
  workspace at the end of every run, so two indexes finishing together is the
  ordinary case, not an exotic one.
"""

import json
import pathlib
import re

import pytest

from magi import kb_registry


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path))
    return tmp_path


# --------------------------------------------------------------------------
# a file that will not parse is kept, not overwritten
# --------------------------------------------------------------------------

def test_a_truncated_registry_is_quarantined_not_erased(home, capsys):
    path = kb_registry.registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"kbs": {"physics": {"path": "D:/phys", "enab', encoding="utf-8")

    assert kb_registry.load_registry() == {"kbs": {}}

    kept = list(home.glob("registry.json.corrupt-*"))
    assert len(kept) == 1, "the unreadable original was not kept"
    assert "enab" in kept[0].read_text(encoding="utf-8")
    assert "could not be parsed" in capsys.readouterr().err


def test_the_next_write_does_not_land_on_the_quarantined_copy(home):
    path = kb_registry.registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")

    kb_registry.register_kb(home / "ws", name="ws", quiet=True)

    assert "ws" in kb_registry.load_registry()["kbs"]
    assert list(home.glob("registry.json.corrupt-*"))


def test_a_json_document_that_is_not_an_object_is_also_quarantined(home):
    path = kb_registry.registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert kb_registry.load_registry() == {"kbs": {}}
    assert list(home.glob("registry.json.corrupt-*"))


def test_an_absent_registry_is_not_a_corrupt_one(home):
    assert kb_registry.load_registry() == {"kbs": {}}
    assert not list(home.glob("registry.json.corrupt-*"))


# --------------------------------------------------------------------------
# writes are all-or-nothing
# --------------------------------------------------------------------------

def test_a_failed_write_leaves_the_previous_file_intact(home, monkeypatch):
    kb_registry.register_kb(home / "ws", name="ws", quiet=True)
    before = kb_registry.registry_path().read_text(encoding="utf-8")

    from magi.core import wiki_common

    def boom(*a, **k):
        raise OSError("no space left on device")

    monkeypatch.setattr(wiki_common, "atomic_write", boom)
    with pytest.raises(OSError):
        kb_registry.save_registry({"kbs": {"other": {}}})

    assert kb_registry.registry_path().read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# read-modify-write happens once
# --------------------------------------------------------------------------

def test_an_edit_that_raises_does_not_write_a_partial_change(home):
    kb_registry.register_kb(home / "ws", name="ws", quiet=True)

    with pytest.raises(RuntimeError):
        with kb_registry.edit_registry() as data:
            del data["kbs"]["ws"]
            raise RuntimeError("changed my mind")

    assert "ws" in kb_registry.load_registry()["kbs"], \
        "the deletion was saved even though the block did not finish"


def test_an_early_return_inside_an_edit_still_saves(home):
    """`_set_enabled` returns from inside the block on the success path."""
    kb_registry.register_kb(home / "ws", name="ws", quiet=True)
    kb_registry._set_enabled("ws", False)
    assert kb_registry.load_registry()["kbs"]["ws"]["enabled"] is False


def test_an_unknown_name_changes_nothing(home, capsys):
    kb_registry.register_kb(home / "ws", name="ws", quiet=True)
    assert kb_registry._set_enabled("nope", False) == 1
    assert set(kb_registry.load_registry()["kbs"]) == {"ws"}


def test_registering_the_same_path_twice_keeps_one_entry(home):
    a = kb_registry.register_kb(home / "ws", name="ws", quiet=True)
    b = kb_registry.register_kb(home / "ws", name="ws", quiet=True)
    assert a == b
    assert len(kb_registry.load_registry()["kbs"]) == 1


def test_a_feature_write_lands_atomically_and_completely(home):
    """`set_feature` rewrites the whole block under one lock — it sets the key
    it was asked for and drops the dead `profile` spelling in the same write,
    so no reader can ever see half of that."""
    from magi import features

    kb_registry.save_settings({"profile": "kb-only", "keep_me": 1})
    features.set_feature("tasks", True)

    data = json.loads(kb_registry.settings_path().read_text(encoding="utf-8"))
    assert data["optional_features"]["tasks"] is True
    assert "profile" not in data
    assert data["keep_me"] == 1


# --------------------------------------------------------------------------
# structural: nobody goes back to the unlocked pair
# --------------------------------------------------------------------------

def test_nothing_pairs_a_load_with_a_save_outside_the_transaction():
    """`load_settings()` … `save_settings(data)` is the lost-update pattern
    written out. Reading alone is fine; it is the pair that is the bug."""
    src = pathlib.Path(kb_registry.__file__).resolve().parent
    saver = re.compile(r"\bsave_(?:registry|settings)\s*\(")

    offenders = []
    for path in sorted(src.rglob("*.py")):
        if path.name == "kb_registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            if saver.search(code):
                offenders.append(f"{path.relative_to(src)}:{n}: {line.strip()}")

    assert not offenders, (
        "these save the whole file directly; use edit_registry() / "
        "edit_settings(), which hold a lock across the read and the write:\n  "
        + "\n  ".join(offenders))
