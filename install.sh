#!/bin/sh
# MAGI one-line installer (macOS / Linux)
#   curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
#
# Bootstraps uv, installs the magi CLI from GitHub, then hands over to
# `magi setup` (Beads, Ollama models, Claude Code plugin, doctor).
# Idempotent — re-run any time to upgrade. For setup flags
# (--no-beads / --no-models / --no-plugin / --remove-legacy), run
# `magi setup <flags>` yourself afterwards.
set -e

echo "== MAGI installer =="

if ! command -v git >/dev/null 2>&1; then
    echo "git is required (install it via your package manager). Aborting." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "[1/3] Installing uv (Python toolchain manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/3] uv already installed"
fi

echo "[2/3] Installing the magi CLI from GitHub..."
uv tool install --force --python 3.12 magi-research
uv tool update-shell >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

echo "[3/3] Provisioning the environment (magi setup)..."
magi setup || echo "magi setup reported issues - run 'magi setup' again later."

echo ""
echo "MAGI installed. If 'magi' is not found, open a new shell (PATH refresh)."
echo "Migrating from Wikify? Run 'magi migrate' at your hub root."
