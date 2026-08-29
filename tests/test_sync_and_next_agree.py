"""`magi sync` and `magi next` describe one workspace, so they agree about it.

The MAGI panel exists to be glanceable: three rows, and the numbers on them
are supposed to be the same numbers the router is working from. They were not.
`sync._research_status` called `state.load(topic)` — whose defaults are the
library's — while `magi next` and the close gate both call `state.loaded()`,
which reads the workspace's own `wip_limit`, `stall_days` and `coaching` out
of `config.yaml`.

So any workspace that configured any of the three had a panel disagreeing with
its router, and the panel is the thing a person looks at first. Under
`coaching: strict` the gap is starkest: `next` counts every proposition that
started work with no prediction on record, `sync` counted none of them, and
the close gate then blocked on debt the panel had said was zero.

`state.loaded()` has existed the whole time for exactly this.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
import yaml

from magi import state, sync
from magi.core import vocab
from magi.kb import threads


@pytest.fixture
def strict(tmp_path):
    """A scaffolded workspace that asks for more than the defaults do."""
    subprocess.run([sys.executable, "-m", "magi", "init", "--topic-dir", str(tmp_path),
                    "--name", "T"], capture_output=True, check=True)
    threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC", "Whether.")
    path = threads.create(tmp_path / "threads" / "p-a.md", vocab.PROPOSITION,
                          "A claim", "Because.", lines=["qec"])
    threads.set_status(path, "testing", "started", host="claude")

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    config.setdefault("research", {})["coaching"] = "strict"
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return tmp_path


def test_the_panel_counts_the_debt_the_router_counts(strict):
    """Work started with no prediction on record. `next` sees it, the gate
    blocks on it, and the panel used to report zero."""
    assert len(state.loaded(strict).debt) == 1, "the fixture is not actually strict"

    assert sync._research_status(strict)["debt"] == 1


def test_the_library_defaults_would_have_missed_it(strict):
    """The other half, stated so the test above cannot pass by accident: with
    the defaults there is no debt here at all, which is exactly why reading
    them instead of the workspace's own settings was invisible."""
    assert state.load(strict).debt == []


def test_the_two_readings_agree_on_a_workspace_that_configures_nothing(tmp_path):
    """No config, no divergence — and no test that only proves the fixture."""
    subprocess.run([sys.executable, "-m", "magi", "init", "--topic-dir", str(tmp_path),
                    "--name", "T"], capture_output=True, check=True)
    threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC", "Whether.")

    assert len(state.load(tmp_path).debt) == len(state.loaded(tmp_path).debt)
