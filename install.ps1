# MAGI one-line installer (Windows)
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
#
# Bootstraps uv, installs the magi CLI from GitHub, then hands over to
# `magi setup` (Beads, Ollama models, Claude Code plugin, doctor).
# Idempotent — re-run any time to upgrade. For setup flags
# (--no-beads / --no-models / --no-plugin / --remove-legacy), run
# `magi setup <flags>` yourself afterwards.

$ErrorActionPreference = "Stop"
Write-Host "== MAGI installer ==" -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git is required (winget install Git.Git). Aborting." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[1/3] Installing uv (Python toolchain manager)..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
} else {
    Write-Host "[1/3] uv already installed"
}

Write-Host "[2/3] Installing the magi CLI from GitHub..."
uv tool install --force --python 3.12 magi-research
try { uv tool update-shell | Out-Null } catch {}
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

Write-Host "[3/3] Provisioning the environment (magi setup)..."
try { magi setup } catch { Write-Host "magi setup reported issues - run 'magi setup' again later." -ForegroundColor Yellow }

Write-Host ""
Write-Host "MAGI installed. If 'magi' is not found, open a NEW terminal (PATH refresh)." -ForegroundColor Green
Write-Host "Migrating from Wikify? Run 'magi migrate' at your hub root."
