# Releasing MAGI

## Versions live in five places

`pyproject.toml`, `src/magi/__init__.py`, `plugin.json`, `.claude-plugin/plugin.json`,
and the badge in `src/magi/ui/static/index.html`. All five must match before tagging.

## GitHub release (current路线)

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q     # must be green
git commit -am "..." ; git tag -a vX.Y.Z -m "..." ; git push origin main --tags
gh release create vX.Y.Z --title "..." --notes "..."
uv tool install --force git+https://github.com/Misaka16384/magi.git
```

Prepend a dated entry to `ROADMAP.md` — it is the living handoff document.

> If `uv tool install --force` fails with `failed to remove directory ... Lib:
> 拒绝访问`, a `magi ui` process is holding the install. Stop it and retry.

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
