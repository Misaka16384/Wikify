# MAGI one-line installer (Windows)
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
#
# One command for both install and upgrade - run it as often as you like.
# Prefers pipx; falls back to uv when there is no usable Python to put pipx on.
# Then hands over to `magi setup`, which asks which optional features you want.
# For setup flags (--no-beads / --no-models / --no-plugin / --remove-legacy),
# run `magi setup <flags>` yourself afterwards.

$ErrorActionPreference = "Stop"
$Pkg = "magi-research"

Write-Host "== MAGI installer ==" -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "note: git not found. MAGI installs fine without it, but the Claude Code" -ForegroundColor Yellow
    Write-Host "      plugin and 'magi pm init' need it later (winget install Git.Git)." -ForegroundColor Yellow
}

# Python 3.10 is the floor (pyproject requires-python). A machine with 3.9 can
# still run MAGI - via uv, which brings its own interpreter - so this only
# decides whether pipx is a candidate, never whether the install can proceed.
# The Microsoft Store stub `python.exe` resolves but does not run, so this
# tests by execution rather than by presence.
function Find-UsablePython {
    foreach ($cand in @("python", "python3", "py")) {
        if (-not (Get-Command $cand -ErrorAction SilentlyContinue)) { continue }
        try {
            & $cand -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $cand }
        } catch { }
    }
    return $null
}

# ---------------------------------------------------------------- 1/3: manager
$Manager = $null
$ManagerPy = $null
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    $Manager = "pipx"
    Write-Host "[1/3] pipx already installed"
} else {
    $py = Find-UsablePython
    if ($py) {
        Write-Host "[1/3] Installing pipx (via $py)..."
        & $py -m pip install --user --upgrade pipx | Out-Null
        try { & $py -m pipx ensurepath | Out-Null } catch { }
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        if (Get-Command pipx -ErrorAction SilentlyContinue) {
            $Manager = "pipx"
        } else {
            # On PATH only after a shell restart; call it through the
            # interpreter that just installed it rather than asking the user to
            # open a new terminal mid-install.
            $Manager = "python-m-pipx"
            $ManagerPy = $py
        }
    } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
        $Manager = "uv"
        Write-Host "[1/3] no Python 3.10+ for pipx; using uv, which is already installed"
    } else {
        Write-Host "[1/3] no Python 3.10+ for pipx; installing uv, which brings its own..."
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        $Manager = "uv"
    }
}

# ------------------------------------------------------------------ 2/3: magi
Write-Host "[2/3] Installing or upgrading $Pkg from PyPI..."
# A non-zero exit from a native command is not a PowerShell error, so these
# would sail past $ErrorActionPreference; each branch checks $LASTEXITCODE.
if ($Manager -eq "uv") {
    uv tool install --force --python 3.12 $Pkg
    if ($LASTEXITCODE -ne 0) { throw "uv tool install failed ($LASTEXITCODE)" }
    try { uv tool update-shell | Out-Null } catch { }
} else {
    # `upgrade --install` is the idempotent form: it installs when missing and
    # is a no-op when already current. It landed in pipx 1.5; older pipx exits
    # non-zero on the unknown flag, so fall back to the two-step it replaces.
    $run = {
        param($argv)
        if ($Manager -eq "python-m-pipx") { & $ManagerPy -m pipx @argv } else { & pipx @argv }
    }
    & $run @("upgrade", "--install", $Pkg) 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $run @("install", $Pkg) 2>$null
        if ($LASTEXITCODE -ne 0) {
            & $run @("upgrade", $Pkg)
            if ($LASTEXITCODE -ne 0) { throw "pipx could not install or upgrade $Pkg" }
        }
    }
}
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

# ----------------------------------------------------------------- 3/3: setup
Write-Host "[3/3] Provisioning the environment (magi setup)..."
# Unlike `curl | sh`, `irm | iex` runs in the current console session, so child
# processes inherit the real console handles and `magi setup` can ask its
# optional-feature questions normally. Nothing to reconnect here.
try { magi setup } catch { Write-Host "magi setup reported issues - run 'magi setup' again later." -ForegroundColor Yellow }

Write-Host ""
Write-Host "MAGI installed. If 'magi' is not found, open a NEW terminal (PATH refresh)." -ForegroundColor Green
Write-Host "Re-run this same command any time to upgrade." -ForegroundColor Green
Write-Host "Migrating from Wikify? Run 'magi migrate' at your hub root."
