# Releasing MAGI

## Versions live in five places

`pyproject.toml`, `src/magi/__init__.py`, `plugin.json`, `.claude-plugin/plugin.json`,
and the badge in `src/magi/ui/static/index.html`. All five must match before tagging.

## Cutting a release

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q     # must be green
git commit -am "..."
git tag -a vX.Y.Z -m "vX.Y.Z — one line

Whatever the release notes should say."
git push origin main
git push origin vX.Y.Z
```

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

Then upgrade the local install and restart any dashboards:

```powershell
uv tool install --force --refresh "magi-research==X.Y.Z"
```

> Pin the exact version. `--refresh` alone sometimes still resolves the previous
> release from the index cache right after publishing.

> If `uv tool install --force` fails with `failed to remove directory ... Lib:
> 拒绝访问`, a `magi ui` process is holding the install. Stop every one of them
> first — a half-failed install leaves the CLI broken.

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
- 100 MB per file; the wheel is ~3.9 MB (mostly MAGI MODE artwork).
- README images must be absolute URLs — relative paths 404 on PyPI.
- The install instructions in `README.md`, `README_en.md`,
  `src/magi/docs/guide.*.md`, `install.ps1`, `install.sh` and both
  `plugin.json` descriptions now name `magi-research`; the `git+https://…`
  form is kept only as the "try unreleased changes" line.
- The test job installs the `[test]` extra: `starlette.testclient` needs
  `httpx2`, which a fresh environment does not have.
