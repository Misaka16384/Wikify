"""magi setup — one-command environment provisioning and doctor.

The install scripts (install.ps1 / install.sh) bootstrap uv + the magi
CLI, then hand over to this command, which:

1. installs Beads (bd) when missing (Windows: GitHub release binary;
   elsewhere: the official installer via curl|sh)
2. pulls the Ollama embedding model when Ollama is present
3. registers the Claude Code plugin when the claude CLI is present
4. installs the skills into every OTHER agent CLI it finds (Codex,
   Antigravity, opencode ...) so they are slash-triggerable there too
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

EMBED_MODEL = "qwen3-embedding:0.6b"
BEADS_REPO = "gastownhall/beads"
PLUGIN_SOURCE = "Misaka16384/magi"


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
            proc = _run(["bash", "-c",
                         f"curl -fsSL https://raw.githubusercontent.com/{BEADS_REPO}/main/install.sh | bash"],
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
    if not _which("ollama"):
        return "Ollama not installed — vectors degrade to BM25-only (https://ollama.com to enable)"
    listed = _run(["ollama", "list"], timeout=30)
    if listed is None:
        return "Ollama present but not responding — start it with 'ollama serve'"
    if EMBED_MODEL.split(":")[0] in (listed.stdout or ""):
        return f"ready ({EMBED_MODEL} present)"
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

def setup_agent_skills(skip: tuple[str, ...] = ()) -> str:
    """Install the bundled skills into each detected agent CLI.

    Claude Code is normally served by the plugin (namespaced /magi:<skill>),
    so it is skipped when that succeeded — installing both would give the
    user two copies of every skill.
    """
    try:
        from magi.skills_cmd import detected_hosts, install_host, load_skills
    except Exception as exc:  # pragma: no cover - defensive
        return f"unavailable ({type(exc).__name__})"

    skills = load_skills()
    if not skills:
        return "no skills bundled in this installation"

    hosts = [h for h in detected_hosts() if h.key not in skip]
    if not hosts:
        return "no other agent CLI detected"

    parts = []
    for host in hosts:
        try:
            rep = install_host(host, skills, "global", force=False, dry_run=False)
        except OSError as exc:
            parts.append(f"{host.key}: failed ({exc.__class__.__name__})")
            continue
        c = rep["counts"]
        changed = c["created"] + c["updated"]
        parts.append(f"{host.key}: {'up to date' if not changed else str(changed) + ' installed'}")
    return "; ".join(parts)


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

def doctor_rows() -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    rows.append(("magi", True, f"v{__import__('magi').__version__}"))
    rows.append(("python", True, sys.version.split()[0]))
    for tool, hint in (
        ("uv", "https://docs.astral.sh/uv/"),
        ("bd", "work-state tracking (magi setup installs it)"),
        ("ollama", "vector search + local OCR (optional)"),
        ("pandoc", "needed for 'magi ingest tex'"),
        ("pdftoppm", "poppler; needed for local OCR"),
        ("pdflatex", "optional deep math validation"),
    ):
        path = _which(tool)
        rows.append((tool, path is not None, path or hint))
    if not _which("pandoc-crossref"):
        rows.append(("pandoc-crossref", False,
                     "optional; Windows binary vendored in the repo's vendor/windows/"))
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
    state = {}
    for row in installed_state(skills):
        if row["scope"] != "global":
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
            rows.append((host.binary, False, f"{host.label} not installed (optional)"))
            continue
        where = path or "config dir present"
        if row and row["installed"]:
            extra = f"skills {row['installed']}/{row['total']}"
            if row["outdated"]:
                extra += f" ({row['outdated']} outdated — 'magi skills install')"
        else:
            extra = "no skills yet — run 'magi skills install'"
        rows.append((host.binary, True, f"{where} · {extra}"))
    return rows


def print_doctor() -> None:
    print("\n=== MAGI environment ===")
    for name, ok, detail in doctor_rows():
        mark = "+" if ok else "-"
        print(f"  [{mark}] {name:<16} {detail}")


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi setup", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Doctor only: report, change nothing")
    parser.add_argument("--no-beads", action="store_true", help="Skip Beads installation")
    parser.add_argument("--no-models", action="store_true", help="Skip Ollama model pulls")
    parser.add_argument("--no-plugin", action="store_true", help="Skip Claude Code plugin registration")
    parser.add_argument("--no-skills", action="store_true",
                        help="Skip installing the skills into other agent CLIs (Codex, agy, opencode ...)")
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

    results: list[tuple[str, str]] = []
    if args.check:
        results.append(("profile", settings.get("profile", "full")))
        results.append(("legacy", handle_legacy(remove=False)))
    else:
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
            # Claude Code gets its skills from the plugin; only fall back to a
            # direct install there when the plugin did not land.
            skip = ("claude",) if plugin_outcome.startswith("plugin installed") else ()
            results.append(("agent skills", setup_agent_skills(skip=skip)))
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
    print("Skills per agent CLI: magi skills where")
    return 0


if __name__ == "__main__":
    sys.exit(main())
