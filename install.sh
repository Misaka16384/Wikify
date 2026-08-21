#!/bin/sh
# MAGI one-line installer (macOS / Linux)
#   curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
#
# Bootstraps uv, installs magi-research from PyPI, then hands over to
# `magi setup` (Beads, Ollama models, Claude Code plugin, doctor).
# Idempotent — re-run any time to upgrade. For setup flags
# (--no-beads / --no-models / --no-plugin / --remove-legacy), run
# `magi setup <flags>` yourself afterwards.
set -e

echo "== MAGI installer =="

if ! command -v git >/dev/null 2>&1; then
    echo "note: git not found. MAGI installs fine without it, but the Claude Code" >&2
    echo "      plugin and 'magi pm init' need it later." >&2
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "[1/3] Installing uv (Python toolchain manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/3] uv already installed"
fi

echo "[2/3] Installing magi-research from PyPI..."
uv tool install --force --python 3.12 magi-research
uv tool update-shell >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

echo "[3/3] Provisioning the environment (magi setup)..."
# `curl … | sh` hands this script to the shell on stdin, so every child process
# inherits a pipe that is already at EOF. `magi setup` asks which optional
# components you want, and with no terminal to ask on it silently takes the
# defaults — in exactly the situation where a fresh machine most needs the
# questions. Reconnect stdin to the controlling terminal when there is one.
if [ -r /dev/tty ]; then
    magi setup < /dev/tty || echo "magi setup reported issues - run 'magi setup' again later."
else
    # No terminal at all (CI, a container, a provisioning script). Take the
    # defaults quietly and say how to answer the questions later.
    magi setup --yes || echo "magi setup reported issues - run 'magi setup' again later."
    echo "note: no terminal available, so the optional-components questions were"
    echo "      skipped. Run 'magi setup --optionals' to answer them."
fi

echo ""
echo "MAGI installed. If 'magi' is not found, open a new shell (PATH refresh)."
echo "Migrating from Wikify? Run 'magi migrate' at your hub root."
