# Releasing MAGI

## Versions live in five places

`pyproject.toml`, `src/magi/__init__.py`, `plugin.json`, `.claude-plugin/plugin.json`,
and the badge in `src/magi/ui/static/index.html`. All five must match before tagging.

## Before cutting: the three-host smoke

`pytest -q` being green does not mean the product works. Every host adapter
stubs its subprocess, because a suite that really calls three vendors' CLIs is
a suite nobody runs — so the thing the whole v2 loop turns on, that another
vendor's CLI can be asked a question and give an answer we can parse, is
exactly what "green" does not cover.

Tier 1 is Claude Code, Codex and Antigravity: smoke tested against a real
install each release. Tier 2 (qwen, opencode) is declared from vendor docs and
fails soft; that difference is the whole meaning of the tiers.

```powershell
# a throwaway workspace with one claim deliberately too broad for its evidence
magi init --topic-dir $env:TEMP\magi-smoke --name Smoke
# ... add raw/papers/<source>.md, a drafts/<derivation>.md, and a proposition
#     whose `derivation:` points at it, then:
magi thread status p-x supported --text "claimed" --host claude

magi review --topic-dir $env:TEMP\magi-smoke --host claude       --dry-run
magi review --topic-dir $env:TEMP\magi-smoke --host codex        --dry-run
magi review --topic-dir $env:TEMP\magi-smoke --host antigravity  --dry-run
magi review --topic-dir $env:TEMP\magi-smoke --host antigravity  --json   # one real call
```

**The claim must be one a correct reviewer has to refute.** A claim that
*stands* is also what a rubber stamp produces, so a smoke test built on one
cannot tell a working reviewer from a broken adapter that answers "yes". Make
the proposition broader than the source it cites — the source measuring one
case and the claim asserting all of them — and the pass condition is that the
reviewer says so, naming the line.

What each step has to show:

| Step | What proves it worked |
|---|---|
| `installed_hosts()` | all three, probed by **binary** — Antigravity's is `agy`, and probing for the key answered "not installed" for a CLI sitting on PATH |
| Each `--dry-run` | the host, and the model it would use: `haiku`, `its own default` (Codex declares no cheap tier), `gemini-3.7-flash-low` |
| The real call | `refuted`, with the reviewer naming the file and line that contradicts the claim |
| `threads/<slug>.md` | `status: disputed` — a rejection is a question for a person, never `refuted` and never silently back to `supported` |
| `output/llm-ledger.jsonl` | one line, with `host`, `model`, `effort`, `seconds` and `ok` |
| `magi next` | the human decision above the agent work |
| `magi sync --close` | the gate runs and the MAP is written |

**Last run:** 2026-08-29, on Windows 11. `agy -p` with
`gemini-3.7-flash-low`, 21.3 s, verdict `refuted`, citing all three files by
line. It also found a bug the suite could not: the reason was being cut at 600
characters, mid-URL, and the post is the record — `raw` survives only in
`--json`.

**macOS: CI green, never smoke tested.** There is no Mac to run it on, so
`.github/workflows/tests.yml` runs the suite on `macos-latest` alongside Linux
and Windows on every push. That covers path separators, file locking and the
platform-only branches. It does not cover any of the table above: no runner has
an agent CLI or an Ollama on it, so the reviewer, the transcript readers and
the model calls are stubbed there exactly as they are here. Stated rather than
implied by its absence.

## Cutting a release

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q     # must be green
git commit -am "..."
git tag -a vX.Y.Z --cleanup=verbatim --file=notes.md
git push origin main
git push origin vX.Y.Z
```

> **`--cleanup=verbatim` is not optional.** Tag messages default to
> `--cleanup=strip`, which deletes every line beginning with `#` as a comment —
> so `### Section` headings vanish out of your release notes without a word.
> v1.9.2 shipped with its three headings eaten before anyone noticed.
> First line of `notes.md` is the release title; the rest is the body.

Pushing the tag is the whole release. `.github/workflows/release.yml` tests,
builds, `twine check`s, publishes to PyPI, **and creates the GitHub Release**
with the wheel and sdist attached.

**Write the tag annotation as the release notes.** The workflow takes its title
from the tag's subject line and its body from the rest, so what you type in
`git tag -a` is what appears on the Releases page. A one-line tag message falls
back to the commit body.

> Between v1.8.0 and v1.9.1 five tags shipped to PyPI with no GitHub Release at
> all — invisible to anyone not watching PyPI, with no changelog and nothing to
> link to. That is why this is a workflow job now and not a step in this list.
> The job skips a tag that already has a release, so re-running is safe.

Prepend a dated entry to `ROADMAP.md` — it is the living handoff document.
It is deliberately **not** tracked in git (see `.gitignore`): it is a working
log for whoever picks the project up next, not a published document. The
release notes on GitHub are what users read.

**Wait for the simple index before upgrading anything.** `pypi.org/pypi/<pkg>/json`
shows the new version within seconds of publishing; `pypi.org/simple/<pkg>/`,
which is what every resolver actually reads, lags it by a few minutes. Until it
catches up, `pipx upgrade` correctly reports "already at latest version" — the
previous one really is the latest as far as the index is concerned:

```powershell
curl -s https://pypi.org/simple/magi-research/ | Select-String "X.Y.Z"
```

Then upgrade the local install and restart any dashboards:

```powershell
pipx upgrade magi-research                           # or, with uv:
uv tool install --force --refresh "magi-research==X.Y.Z"
```

> [!WARN]
> **Do not use `pipx install --force`.** Under pipx's uv backend it fails with
> `A virtual environment already exists ... Use --clear to replace it`, then
> `Not removing existing venv ... because it was not created in this session`,
> prints `Installing to existing venv` and **leaves the old version in place**.
> It exits 1, but the message reads like success. Verified on v1.12.0 and
> reproduced in an isolated `PIPX_HOME`: `pipx install --force "cowsay==6.1"`
> over an existing 6.0 left 6.0 installed.
>
> To pin an exact version with pipx, uninstall first:
> `pipx uninstall magi-research; pipx install "magi-research==X.Y.Z"`.
> To simply take the newest, `pipx upgrade magi-research` works.
> `uv tool install --force --refresh` has no such problem.

> If the install fails with `failed to remove directory ... Lib: 拒绝访问`, a
> `magi ui` process is holding it. Stop every one of them first — a half-failed
> install leaves the CLI broken. On Windows the holders are easy to miss: the
> shim, the venv's python, and any python that launched it all keep the file
> open, so kill the tree (`taskkill /PID <pid> /T /F`), not just the one you see
> listening on the port.

> Do not verify a release by installing it with the *other* manager. pipx and
> uv share `~/.local/bin`, so uninstalling the one you tested with deletes the
> shim the other still needs, and `magi` vanishes from PATH while the surviving
> manager still lists it as installed.

## PyPI (`pip install magi-research`)

Live since **v1.6.2** (2026-08-20). Publishing runs on **Trusted Publishing** —
no API token is stored anywhere. Push a `v*` tag and
`.github/workflows/release.yml` tests, builds, checks and publishes.

<details>
<summary>One-time setup, already done — kept for reference</summary>

1. Sign in at <https://pypi.org> → *Your account* → *Publishing* → *Add a new
   pending publisher* → **GitHub**.
2. Fill in exactly:
   - PyPI project name: `magi-research`
   - Owner / repository: `Misaka16384` / `magi`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo, *Settings → Environments → New environment* named `pypi`
   (optional but recommended; the workflow references it).

A pending publisher does **not** reserve the name — it is claimed by the first
successful upload.

</details>

**Every release after that:** push a `v*` tag. `.github/workflows/release.yml`
runs the tests, builds sdist + wheel with `uv build`, checks the rendered README
with `twine check`, and publishes. `workflow_dispatch` can trigger it manually
for the first run.

**Dry run on TestPyPI** (separate account and publisher registration):

```powershell
uv build
uv publish --index testpypi        # index preconfigured in pyproject.toml
```

**Manual publish without CI** (the token stays with whoever runs it):

```powershell
uv build
uvx twine check dist/*
uv publish --token pypi-<your-token>
```

### Things that bite

- A version number can never be reused on PyPI, even after deleting the file.
- `pip install magi-research` over an existing copy prints `Requirement
  already satisfied` and **exits 0** without upgrading anything — the same
  shape of trap as `pipx install --force`, and the one users installing with
  pip actually hit. The command to give them is `python -m pip install
  --upgrade magi-research`. Since v1.14.4 `magi update` detects pip installs
  (user site and interpreter-wide) and runs it; before that they detected as
  `unknown` and got a notice naming no command at all.
- On Windows, whether `magi update` can upgrade a pipx install depends on
  something pipx does not promise: if `~/.local/bin/magi.exe` is a **copy**
  the upgrade works inline, and if it is a **symlink** into the venv the
  running image *is* `Scripts/magi.exe` and uv dies with `os error 5`. Both
  shapes have been seen on the same machine days apart. Since v1.14.5 that
  failure is handed to the detached helper instead of reported, so do not
  treat an inline success as proof the recovery path still works — test it
  by running the venv's `Scripts/magi.exe` directly.
- 100 MB per file; the wheel is ~5.4 MB as of v1.15.0. Nearly all of it is
  `ui/static/` (7.1 MB before compression): `vendor/mermaid.min.js` at 2.6 MB
  and the MAGI MODE backgrounds. The figure said 3.9 MB for several releases
  after it stopped being true — check it against `uv build`'s output rather
  than against this line.
- README images must be absolute URLs — relative paths 404 on PyPI.
- The install instructions in `README.md`, `README_en.md`,
  `src/magi/docs/guide.*.md`, `install.ps1`, `install.sh` and both
  `plugin.json` descriptions now name `magi-research`; the `git+https://…`
  form is kept only as the "try unreleased changes" line.
- The test job installs the `[test]` extra: `starlette.testclient` needs
  `httpx2`, which a fresh environment does not have.
