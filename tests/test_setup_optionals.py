"""The doctor must not call a working machine broken.

Every tool in OPTIONAL_TOOLS is something MAGI runs fine without. Painting them
red told people to go fix an environment that had nothing wrong with it, and
the single most common shape of that complaint was a fresh pipx install on a
machine with no Ollama.
"""

import pytest

import magi.setup_cmd as setup


@pytest.fixture
def bare(monkeypatch):
    """A machine with none of the optional tools installed."""
    monkeypatch.setattr(setup, "_which", lambda name: None)
    monkeypatch.setattr(setup, "agent_cli_rows", lambda _ws=None: [])
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {})


@pytest.fixture
def loaded(monkeypatch):
    """A machine with everything installed."""
    monkeypatch.setattr(setup, "_which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(setup, "agent_cli_rows", lambda _ws=None: [])
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {})
    monkeypatch.setattr(setup, "_ollama_server_note", lambda: "server stopped")


# --------------------------------------------------------------------------
# Nothing optional is ever a problem
# --------------------------------------------------------------------------

def test_a_bare_machine_reports_no_problems(bare):
    assert [r.name for r in setup.doctor_rows() if r.is_problem] == []


def test_every_optional_tool_is_marked_optional_not_missing(bare):
    rows = {r.name: r for r in setup.doctor_rows()}
    for tool in setup.OPTIONAL_TOOLS:
        assert rows[tool.binary].status == "optional", tool.binary


def test_an_uninstalled_optional_says_what_it_would_unlock(bare):
    rows = {r.name: r for r in setup.doctor_rows()}
    assert "vector" in rows["ollama"].detail
    assert "LaTeX" in rows["pandoc"].detail or "arXiv" in rows["pandoc"].detail


def test_an_uninstalled_optional_carries_its_official_download_url(bare):
    rows = {r.name: r for r in setup.doctor_rows()}
    for tool in setup.OPTIONAL_TOOLS:
        assert rows[tool.binary].url == tool.url, tool.binary
    assert rows["ollama"].url.startswith("https://ollama.com")


def test_an_installed_tool_carries_no_url(loaded):
    """The link is guidance for someone who needs it, not decoration."""
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["pandoc"].url is None


# --------------------------------------------------------------------------
# A declined tool stops being mentioned
# --------------------------------------------------------------------------

def test_a_declined_tool_is_not_advertised_again(bare, monkeypatch):
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {"ollama": False})
    rows = {r.name: r for r in setup.doctor_rows()}

    assert rows["ollama"].status == "declined"
    assert rows["ollama"].url is None
    assert "chose to skip" in rows["ollama"].detail


def test_declining_one_tool_does_not_silence_the_others(bare, monkeypatch):
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {"ollama": False})
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["pandoc"].status == "optional"


def test_wanting_a_tool_still_shows_it_as_installable(bare, monkeypatch):
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {"ollama": True})
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["ollama"].status == "optional"
    assert rows["ollama"].url


# --------------------------------------------------------------------------
# uv and bd
# --------------------------------------------------------------------------

def test_neither_installer_is_ever_a_problem(bare):
    """pipx and uv install magi and are never executed afterwards.

    Either one is sufficient, so a machine missing one of them is not a machine
    with a fault. pipx is the one the docs lead with; uv is there for a machine
    with no Python 3.10+ of its own.
    """
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["pipx"].status == "ok"
    assert rows["uv"].status == "ok"
    # The recommended command has to be in the row that recommends it —
    # a bare "not installed" leaves the reader to find it elsewhere.
    assert "pipx upgrade --install magi-research" in rows["pipx"].detail


def test_bd_missing_is_optional_because_setup_installs_it(bare):
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["bd"].status == "optional"


# --------------------------------------------------------------------------
# pandoc-crossref only matters once pandoc exists
# --------------------------------------------------------------------------

def test_pandoc_crossref_is_not_mentioned_without_pandoc(bare):
    """Nagging about a pandoc filter on a machine with no pandoc is noise."""
    assert "pandoc-crossref" not in {r.name for r in setup.doctor_rows()}


def test_pandoc_crossref_is_mentioned_once_pandoc_is_present(monkeypatch):
    monkeypatch.setattr(setup, "_which",
                        lambda name: None if name == "pandoc-crossref" else f"/usr/bin/{name}")
    monkeypatch.setattr(setup, "agent_cli_rows", lambda _ws=None: [])
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {})
    monkeypatch.setattr(setup, "_ollama_server_note", lambda: "n/a")

    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["pandoc-crossref"].status == "optional"


# --------------------------------------------------------------------------
# The row type keeps its old shape for existing readers
# --------------------------------------------------------------------------

def test_ok_is_true_only_for_installed(bare):
    rows = {r.name: r for r in setup.doctor_rows()}
    assert rows["magi"].ok is True
    assert rows["ollama"].ok is False


def test_printing_a_bare_machine_says_nothing_is_broken(bare, capsys):
    setup.print_doctor()
    out = capsys.readouterr().out
    assert "Nothing is broken" in out
    assert "need attention" not in out


# --------------------------------------------------------------------------
# Prompting
# --------------------------------------------------------------------------

def test_the_chooser_never_prompts_when_not_interactive(bare, monkeypatch):
    """A CI run, a subprocess, or a WebUI job would hang on input()."""
    def explode(*a, **k):
        raise AssertionError("must not prompt")

    monkeypatch.setattr("builtins.input", explode)
    assert setup.choose_optionals(interactive=False) == {}


def test_a_skipped_prompt_says_so_rather_than_going_quiet(bare, monkeypatch, capsys):
    """`curl … | sh` hands the installer script to the shell on stdin, so every
    child inherits a pipe at EOF and the questions cannot be asked — in exactly
    the situation where a fresh machine most needs them. The user is watching;
    tell them how to answer later instead of silently taking defaults.
    """
    monkeypatch.setattr("builtins.input", lambda *a, **k: pytest.fail("must not prompt"))
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)

    class Tty:
        def __init__(self, inner): self._inner = inner
        def isatty(self): return True
        def __getattr__(self, name): return getattr(self._inner, name)

    import sys as _sys
    monkeypatch.setattr(_sys, "stdout", Tty(_sys.stdout))
    setup.choose_optionals(interactive=False)

    assert "magi setup --optionals" in capsys.readouterr().out


def test_nothing_is_said_when_there_is_nothing_to_install(loaded, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a, **k: pytest.fail("must not prompt"))
    setup.choose_optionals(interactive=False)
    assert "--optionals" not in capsys.readouterr().out


def test_declining_at_the_prompt_is_remembered(bare, monkeypatch, tmp_path):
    saved = {}
    monkeypatch.setattr(setup, "_which", lambda name: None)
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.kb_registry.save_settings", lambda s: saved.update(s))
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    chosen = setup.choose_optionals(interactive=True)

    assert chosen["ollama"] is False
    assert saved["optional_features"]["ollama"] is False


def test_accepting_at_the_prompt_is_remembered(bare, monkeypatch):
    saved = {}
    monkeypatch.setattr(setup, "_which", lambda name: None)
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.kb_registry.save_settings", lambda s: saved.update(s))
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    chosen = setup.choose_optionals(interactive=True)
    assert chosen["ollama"] is True
    assert chosen["mineru"] is True


def test_an_empty_answer_takes_the_default(bare, monkeypatch):
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.kb_registry.save_settings", lambda s: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    chosen = setup.choose_optionals(interactive=True)
    # Default for a tool is yes; for MinerU (a paid cloud service) it is no.
    assert chosen["ollama"] is True
    assert chosen["mineru"] is False


def test_ctrl_c_at_the_prompt_does_not_crash_setup(bare, monkeypatch):
    def interrupted(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.kb_registry.save_settings", lambda s: None)
    monkeypatch.setattr("builtins.input", interrupted)

    chosen = setup.choose_optionals(interactive=True)
    assert isinstance(chosen, dict)


def test_the_prompt_shows_the_official_url(bare, monkeypatch, capsys):
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.kb_registry.save_settings", lambda s: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    setup.choose_optionals(interactive=True)
    out = capsys.readouterr().out

    assert "https://ollama.com/download" in out
    assert "https://pandoc.org/installing.html" in out
    assert setup.MINERU_URL in out


def test_nothing_to_ask_when_everything_is_installed(loaded, monkeypatch, capsys):
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("builtins.input",
                        lambda prompt="": pytest.fail("must not prompt"))

    setup.choose_optionals(interactive=True)
    assert "already installed" in capsys.readouterr().out
