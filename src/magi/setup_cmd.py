"""magi setup — one-command environment provisioning and doctor.

The install scripts (install.ps1 / install.sh) bootstrap uv + the magi
CLI, then hand over to this command, which:

1. installs Beads (bd) when missing (Windows: GitHub release binary;
   elsewhere: the official installer via curl|sh)
2. pulls the Ollama embedding model when Ollama is present
3. registers the Claude Code plugin when the claude CLI is present
4. reports which other agent CLIs are installed (skills go in per
   workspace via `magi skills install`, never machine-wide)
5. detects legacy Wikify installations (old copied skills/ + bin/)
6. prints a doctor table + quick-start

Safe to re-run any time (idempotent). `magi setup --check` only reports.
Legacy copies are only DELETED with the explicit --remove-legacy flag.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import NamedTuple

EMBED_MODEL = "qwen3-embedding:0.6b"
BEADS_REPO = "gastownhall/beads"
PLUGIN_SOURCE = "Misaka16384/magi"


class DoctorRow(NamedTuple):
    """One line of the environment report.

    ``status`` rather than a bool because "missing" and "optional and not
    installed" are different facts and only one of them is a problem. Painting
    an optional tool red told people their setup was broken when they had
    simply chosen not to install something they do not need.
    """

    name: str
    status: str          # "ok" | "missing" | "optional" | "declined"
    detail: str
    url: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def is_problem(self) -> bool:
        return self.status == "missing"


class Optional_(NamedTuple):
    """An external tool MAGI can use but cannot install for you."""

    key: str
    binary: str
    label: str
    unlocks: str
    url: str
    install_hint: str = ""


# Everything here is genuinely optional: MAGI runs without any of it, with a
# smaller feature set. Each carries the official download page, because
# "install pandoc" is unhelpful and "here is where" is not.
OPTIONAL_TOOLS: tuple[Optional_, ...] = (
    Optional_(
        key="ollama",
        binary="ollama",
        label="Ollama",
        unlocks="semantic (vector) search, and local offline OCR for PDFs",
        url="https://ollama.com/download",
        install_hint="after installing: magi setup pulls the embedding model for you",
    ),
    Optional_(
        key="pandoc",
        binary="pandoc",
        label="Pandoc",
        unlocks="the LaTeX and arXiv-HTML ingest routes — the best-fidelity way in",
        url="https://pandoc.org/installing.html",
    ),
    Optional_(
        key="poppler",
        binary="pdftoppm",
        label="Poppler",
        unlocks="local OCR page rendering (needed alongside Ollama)",
        url="https://poppler.freedesktop.org/",
        install_hint="Windows builds: https://github.com/oschwartz10612/poppler-windows/releases",
    ),
    Optional_(
        key="latex",
        binary="pdflatex",
        label="LaTeX (TeX Live / MiKTeX)",
        unlocks="deep math validation — checks a formula actually compiles",
        url="https://www.tug.org/texlive/",
    ),
)

# Not a binary, so it is not in the table above, but it belongs in the same
# conversation: it is the other way to get good PDF conversion.
MINERU_URL = "https://mineru.net/"


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None


def _local_bin() -> Path:
    return Path.home() / ".local" / "bin"


# --------------------------------------------------------------------------
# component: beads
# --------------------------------------------------------------------------

def install_beads() -> str:
    if _which("bd"):
        v = _run(["bd", "version"], timeout=20)
        return f"already installed ({(v.stdout.strip().splitlines() or ['?'])[0]})" if v else "already installed"
    print("[setup] installing Beads (bd)...")
    if sys.platform == "win32":
        try:
            api = f"https://api.github.com/repos/{BEADS_REPO}/releases/latest"
            with urllib.request.urlopen(api, timeout=30) as r:
                release = json.load(r)
            asset = next(a for a in release["assets"] if a["name"].endswith("windows_amd64.zip"))
            dest_dir = _local_bin()
            dest_dir.mkdir(parents=True, exist_ok=True)
            zip_path = dest_dir / "beads_tmp.zip"
            print(f"[setup]   downloading {asset['name']}...")
            urllib.request.urlretrieve(asset["browser_download_url"], zip_path)
            import zipfile

            with zipfile.ZipFile(zip_path) as z:
                with z.open("bd.exe") as src, open(dest_dir / "bd.exe", "wb") as dst:
                    shutil.copyfileobj(src, dst)
            zip_path.unlink(missing_ok=True)
            if not _which("bd") and str(dest_dir) not in os.environ.get("PATH", ""):
                return f"installed to {dest_dir} — ADD IT TO PATH (uv tool update-shell usually covers it)"
            return f"installed ({release.get('tag_name', '')})"
        except Exception as exc:
            return (f"FAILED ({type(exc).__name__}) — install manually: "
                    f"https://github.com/{BEADS_REPO}#installation")
    else:
        if _which("curl"):
            # scripts/install.sh, not install.sh: the repo root has no
            # install.sh, so this fetched a GitHub 404 page and piped the HTML
            # into bash. `bd` never installed on macOS or Linux.
            proc = _run(["bash", "-c",
                         f"curl -fsSL https://raw.githubusercontent.com/{BEADS_REPO}"
                         "/main/scripts/install.sh | bash"],
                        timeout=600)
            if proc and proc.returncode == 0 and _which("bd"):
                return "installed"
            return (f"FAILED — install manually (brew/npm/go): "
                    f"https://github.com/{BEADS_REPO}#installation")
        return f"curl not found — install manually: https://github.com/{BEADS_REPO}#installation"


# --------------------------------------------------------------------------
# component: ollama models
# --------------------------------------------------------------------------

def setup_ollama_models() -> str:
    from magi.core import ollama as ollama_svc

    if not _which("ollama"):
        return "Ollama not installed — vectors degrade to BM25-only (https://ollama.com to enable)"
    # Setup is allowed to start things; a stopped server is not a report.
    state = ollama_svc.ensure()
    if not state.running:
        return f"Ollama present but would not start — try 'ollama serve': {state.reason}"
    if state.has_model(EMBED_MODEL):
        return f"ready ({EMBED_MODEL} present{', server started' if state.started else ''})"
    print(f"[setup] pulling {EMBED_MODEL} (~640 MB, one-time)...")
    proc = _run(["ollama", "pull", EMBED_MODEL], timeout=1800)
    if proc and proc.returncode == 0:
        return f"pulled {EMBED_MODEL}"
    return f"pull failed — run manually: ollama pull {EMBED_MODEL}"


# --------------------------------------------------------------------------
# component: Claude Code plugin
# --------------------------------------------------------------------------

def setup_claude_plugin() -> str:
    if not _which("claude"):
        return "claude CLI not found — skills go in per host, see 'magi skills install'"
    add = _run(["claude", "plugin", "marketplace", "add", PLUGIN_SOURCE], timeout=120)
    inst = _run(["claude", "plugin", "install", "magi"], timeout=180)
    if inst and inst.returncode == 0:
        return "plugin installed (skills appear as /magi:wiki_*)"
    detail = ""
    for proc in (inst, add):
        if proc and (proc.stderr or proc.stdout):
            detail = (proc.stderr or proc.stdout).strip().splitlines()[-1][:100]
            break
    return (f"could not auto-install ({detail or 'no output'}) — run manually: "
            f"claude plugin marketplace add {PLUGIN_SOURCE} && claude plugin install magi")


# --------------------------------------------------------------------------
# component: skills for every other agent CLI
# --------------------------------------------------------------------------

def report_agent_skills() -> str:
    """Say which agent CLIs are present — do not install into them.

    The skills are workspace-specific (they ingest into raw/, compile into
    wiki/, query that workspace's graph), so a machine-wide install would put
    18 irrelevant skills in front of every unrelated project. The install is
    one command, run inside the workspace where it means something.
    """
    try:
        from magi.skills_cmd import detected_hosts
    except Exception as exc:  # pragma: no cover - defensive
        return f"unavailable ({type(exc).__name__})"

    hosts = detected_hosts()
    if not hosts:
        return "no agent CLI detected"
    names = ", ".join(h.key for h in hosts)
    return f"{names} detected — install per workspace: cd <topic> && magi skills install"


# --------------------------------------------------------------------------
# legacy Wikify detection
# --------------------------------------------------------------------------

def find_legacy_copies() -> list[Path]:
    """Old install.ps1-era copies: skills/wiki_* + bin/ inside agent dirs."""
    hits: list[Path] = []
    for base in (Path.home() / ".claude", Path.home() / ".gemini"):
        skills = base / "skills"
        if skills.is_dir():
            for d in skills.glob("wiki_*"):
                text = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace") \
                    if (d / "SKILL.md").is_file() else ""
                # old copies referenced <BIN>/ script paths; new skills call `magi`
                if "<BIN>" in text or "bin/llm-wiki.py" in text:
                    hits.append(d)
        legacy_bin = base / "bin"
        if (legacy_bin / "llm-wiki.py").is_file():
            hits.append(legacy_bin)
    return hits


def handle_legacy(remove: bool) -> str:
    hits = find_legacy_copies()
    if not hits:
        return "no legacy Wikify copies found"
    if remove:
        for h in hits:
            shutil.rmtree(h, ignore_errors=True)
        return f"removed {len(hits)} legacy item(s)"
    listing = "; ".join(str(h) for h in hits[:6])
    return (f"LEGACY Wikify copies found ({len(hits)}): {listing} — these mislead agents. "
            "Remove them with: magi setup --remove-legacy")


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------

def _ollama_server_note() -> str:
    """Server state for the doctor row, without starting anything."""
    from magi.core import ollama as ollama_svc

    models = ollama_svc.probe()
    if models is None:
        return "server stopped (MAGI starts it when it needs vectors)"
    if not models:
        return f"server up, no models pulled — run: ollama pull {EMBED_MODEL}"
    if ollama_svc.OllamaState("", True, models).has_model(EMBED_MODEL):
        return f"server up, {EMBED_MODEL} ready"
    return f"server up, but {EMBED_MODEL} is not pulled — run: ollama pull {EMBED_MODEL}"


def _ask_yes_no(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"  {question} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def choose_optionals(interactive: bool) -> dict:
    """Ask which optional capabilities the user wants, and remember the answer.

    MAGI cannot install any of these — they are other people's installers — so
    the useful thing setup can do is explain what each one buys, hand over the
    official link, and record a "no" so the doctor stops raising it forever
    after. A tool you decided not to install is not a fault in your machine.
    """
    from magi.kb_registry import load_settings, save_settings

    settings = load_settings()
    chosen = dict(settings.get("optional_features") or {})

    if not interactive:
        return chosen

    missing = [t for t in OPTIONAL_TOOLS if not _which(t.binary)]
    if not missing:
        print("[setup] every optional component is already installed.")
        return chosen

    print("\n=== Optional components ===")
    print("  MAGI runs without all of these. Each one turns on a specific feature.")
    print("  Say no to anything you do not want and it stops being mentioned.\n")

    for tool in missing:
        print(f"  {tool.label} — {tool.unlocks}")
        print(f"    download: {tool.url}")
        if tool.install_hint:
            print(f"    note: {tool.install_hint}")
        previous = chosen.get(tool.key)
        default = True if previous is None else bool(previous)
        chosen[tool.key] = _ask_yes_no(f"Do you want {tool.label}?", default=default)
        print()

    # MinerU is a hosted service, not a binary, so it is not in OPTIONAL_TOOLS —
    # but it belongs in this conversation, because it is the other way to get
    # good PDF conversion when you do not want a local model.
    print("  MinerU — cloud PDF conversion, strong on formulas and layout.")
    print(f"    sign up: {MINERU_URL}")
    print("    then put the token in your workspace's config.yaml under "
          "ocr.mineru_api_token")
    chosen["mineru"] = _ask_yes_no("Do you plan to use MinerU?",
                                   default=bool(chosen.get("mineru", False)))

    settings["optional_features"] = chosen
    save_settings(settings)

    wanted = [t.label for t in OPTIONAL_TOOLS if chosen.get(t.key)]
    if wanted:
        print(f"\n[setup] noted. Install when you are ready: {', '.join(wanted)}")
    declined = [t.label for t in OPTIONAL_TOOLS if chosen.get(t.key) is False]
    if declined:
        print(f"[setup] skipping for good: {', '.join(declined)} "
              "(change your mind with 'magi setup --optionals')")
    return chosen


def wanted_optionals() -> dict:
    """Which optional tools the user said they wanted, from `magi setup`.

    An absent key means "never asked", which is reported the same as "wanted":
    we show what it would unlock. An explicit false means they declined, and we
    stop bringing it up.
    """
    from magi.kb_registry import load_settings
    return dict(load_settings().get("optional_features") or {})


def doctor_rows() -> list[DoctorRow]:
    wanted = wanted_optionals()
    rows: list[DoctorRow] = [
        DoctorRow("magi", "ok", f"v{__import__('magi').__version__}"),
        DoctorRow("python", "ok", sys.version.split()[0]),
    ]
    # uv is an *installer*, not a dependency: nothing in MAGI ever executes it.
    # `pipx install magi-research` is equally supported, so a machine without uv
    # is not a machine with a problem.
    uv_path = _which("uv")
    rows.append(DoctorRow("uv", "ok", uv_path or
                          "not installed — only ever used to install magi (pipx works too)"))

    bd_path = _which("bd")
    rows.append(DoctorRow(
        "bd", "ok" if bd_path else "optional",
        bd_path or "work-state tracking — 'magi setup' installs it for you"))

    for tool in OPTIONAL_TOOLS:
        path = _which(tool.binary)
        if path and tool.key == "ollama":
            # "installed" is the least useful thing to say about Ollama — every
            # vector question is really about the server. Doctor reports; it
            # does not start anything.
            rows.append(DoctorRow(tool.binary, "ok", f"{path} — {_ollama_server_note()}"))
            continue
        if path:
            rows.append(DoctorRow(tool.binary, "ok", path))
            continue
        if wanted.get(tool.key) is False:
            rows.append(DoctorRow(tool.binary, "declined",
                                  f"not installed — you chose to skip {tool.label}"))
            continue
        rows.append(DoctorRow(tool.binary, "optional",
                              f"not installed — unlocks {tool.unlocks}", tool.url))

    if _which("pandoc") and not _which("pandoc-crossref"):
        rows.append(DoctorRow(
            "pandoc-crossref", "optional",
            "not installed — cross-references degrade; Windows binary is vendored "
            "in the repo's vendor/windows/"))
    rows.extend(agent_cli_rows())
    return rows


def agent_cli_rows() -> list[tuple[str, bool, str]]:
    """One row per supported agent CLI, with its skill-install state.

    All of them or none: reporting only Claude Code would imply the others
    are unsupported, which is exactly backwards — the skills install into
    every one of them.
    """
    try:
        from magi.skills_cmd import HOSTS, installed_state, load_skills
    except Exception:
        return []

    skills = load_skills()
    # Report the scope that matters here: inside a workspace that is the
    # workspace's own copy, anywhere else it is whatever is installed globally.
    from magi.skills_cmd import _is_workspace, workspace_anchor

    anchor = workspace_anchor()
    scope = "project" if _is_workspace(anchor) else "global"

    state = {}
    for row in installed_state(skills):
        if row["scope"] != scope:
            continue
        # A host can read from more than one directory; the best count wins.
        prev = state.get(row["host"])
        if prev is None or row["installed"] > prev["installed"]:
            state[row["host"]] = row

    rows: list[tuple[str, bool, str]] = []
    for host in HOSTS.values():
        path = _which(host.binary)
        found = host.detected()
        row = state.get(host.key)
        if not found:
            rows.append(DoctorRow(host.binary, "optional",
                                  f"{host.label} not installed"))
            continue
        where = path or "config dir present"
        if row and row["installed"]:
            extra = f"{scope} skills {row['installed']}/{row['total']}"
            if row["outdated"]:
                extra += f" ({row['outdated']} outdated — 'magi skills install')"
        elif scope == "project":
            extra = "no skills in this workspace — 'magi skills install'"
        else:
            extra = "installed; skills go in per workspace ('magi skills install')"
        rows.append(DoctorRow(host.binary, "ok", f"{where} · {extra}"))
    return rows


_MARKS = {"ok": "+", "missing": "-", "optional": " ", "declined": "."}


def print_doctor() -> None:
    print("\n=== MAGI environment ===")
    rows = doctor_rows()
    for row in rows:
        print(f"  [{_MARKS.get(row.status, '?')}] {row.name:<16} {row.detail}")
        if row.url:
            print(f"      {'':<16} -> {row.url}")
    problems = [r for r in rows if r.is_problem]
    if problems:
        print(f"\n  {len(problems)} thing(s) need attention.")
    else:
        # Blank marks are not failures and the table should say so out loud,
        # because a column of them still reads as a wall of red to a new user.
        skipped = [r for r in rows if r.status in ("optional", "declined")]
        if skipped:
            print(f"\n  Nothing is broken. {len(skipped)} optional component(s) "
                  "are not installed — MAGI works without them.")


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi setup", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Doctor only: report, change nothing")
    parser.add_argument("--optionals", action="store_true",
                        help="Just re-run the optional-components questions")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Never prompt; keep whatever was chosen before")
    parser.add_argument("--no-beads", action="store_true", help="Skip Beads installation")
    parser.add_argument("--no-models", action="store_true", help="Skip Ollama model pulls")
    parser.add_argument("--no-plugin", action="store_true", help="Skip Claude Code plugin registration")
    parser.add_argument("--no-skills", action="store_true",
                        help="Skip the agent-CLI skills report")
    parser.add_argument("--kb-only", action="store_true",
                        help="Knowledge-base-only profile (the classic Wikify experience): "
                             "skip Beads, and magi sync stops suggesting task tracking. "
                             "Revert with --full.")
    parser.add_argument("--full", action="store_true", help="Restore the full profile (undo --kb-only)")
    parser.add_argument("--remove-legacy", action="store_true",
                        help="DELETE detected legacy Wikify skill/bin copies")
    args = parser.parse_args(argv)

    from magi.kb_registry import load_settings, save_settings

    settings = load_settings()
    if args.kb_only:
        settings["profile"] = "kb-only"
        save_settings(settings)
        print("[setup] profile set to kb-only (task tracking disabled; revert with 'magi setup --full')")
    elif args.full:
        settings["profile"] = "full"
        save_settings(settings)
        print("[setup] profile set to full")
    kb_only = settings.get("profile") == "kb-only"

    # Prompting is for a person at a terminal. A CI run, a subprocess, or a
    # WebUI job would hang on input(), so those keep whatever was chosen before.
    interactive = (not args.yes) and sys.stdin.isatty() and sys.stdout.isatty()

    if args.optionals:
        choose_optionals(interactive)
        print_doctor()
        return 0

    results: list[tuple[str, str]] = []
    if args.check:
        results.append(("profile", settings.get("profile", "full")))
        results.append(("legacy", handle_legacy(remove=False)))
    else:
        choose_optionals(interactive)
        if not args.no_beads and not kb_only:
            results.append(("beads", install_beads()))
        elif kb_only:
            results.append(("beads", "skipped (kb-only profile)"))
        if not args.no_models:
            results.append(("ollama", setup_ollama_models()))
        plugin_outcome = ""
        if not args.no_plugin:
            plugin_outcome = setup_claude_plugin()
            results.append(("claude plugin", plugin_outcome))
        if not args.no_skills:
            results.append(("agent skills", report_agent_skills()))
        results.append(("legacy", handle_legacy(remove=args.remove_legacy)))

    print_doctor()
    print("\n=== setup results ===")
    for name, outcome in results:
        print(f"  {name:<14} {outcome}")

    print("\nQuick start:")
    print("  mkdir KnowledgeHub && cd KnowledgeHub && magi hub init && magi pm init")
    print("  mkdir -p topics/my-topic && cd topics/my-topic")
    print('  magi init --name "My Topic" --scope "..." && magi sync')
    print("Migrating from Wikify? Run 'magi migrate' at your hub root (migrates every topic).")
    print("Stuck at any point?  magi guide --search \"<the error>\"   (manual: magi guide)")
    print("Agent skills:         cd <your topic workspace> && magi skills install")
    return 0


if __name__ == "__main__":
    sys.exit(main())
