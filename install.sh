#!/bin/sh
# MAGI one-line installer (macOS / Linux)
#   curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
#
# One command for both install and upgrade — run it as often as you like.
# Prefers pipx; falls back to uv when there is no usable Python to put pipx on.
# Then hands over to `magi setup`, which asks which optional features you want.
# For setup flags (--no-beads / --no-models / --no-plugin / --remove-legacy),
# run `magi setup <flags>` yourself afterwards.
set -e

PKG="magi-research"

echo "== MAGI installer =="

if ! command -v git >/dev/null 2>&1; then
    echo "note: git not found. MAGI installs fine without it, but the Claude Code" >&2
    echo "      plugin and 'magi pm init' need it later." >&2
fi

# Python 3.10 is the floor (pyproject requires-python). A machine with 3.9 can
# still run MAGI — via uv, which brings its own interpreter — so this only
# decides whether pipx is a candidate, never whether the install can proceed.
usable_python() {
    for cand in python3 python; do
        command -v "$cand" >/dev/null 2>&1 || continue
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------------- 1/3: manager
MANAGER=""
if command -v pipx >/dev/null 2>&1; then
    MANAGER="pipx"
    echo "[1/3] pipx already installed"
elif PY=$(usable_python); then
    echo "[1/3] Installing pipx (via $PY)..."
    "$PY" -m pip install --user --upgrade pipx >/dev/null
    "$PY" -m pipx ensurepath >/dev/null 2>&1 || true
    export PATH="$HOME/.local/bin:$PATH"
    if command -v pipx >/dev/null 2>&1; then
        MANAGER="pipx"
    else
        # On PATH only after a shell restart; call it through the interpreter
        # that just installed it rather than asking the user to open a new one.
        MANAGER="$PY -m pipx"
    fi
elif command -v uv >/dev/null 2>&1; then
    MANAGER="uv"
    echo "[1/3] no Python 3.10+ for pipx; using uv, which is already installed"
else
    echo "[1/3] no Python 3.10+ for pipx; installing uv, which brings its own..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    MANAGER="uv"
fi

# ------------------------------------------------------------------ 2/3: magi
echo "[2/3] Installing or upgrading $PKG from PyPI..."
if [ "$MANAGER" = "uv" ]; then
    uv tool install --force --python 3.12 "$PKG"
    uv tool update-shell >/dev/null 2>&1 || true
else
    # `upgrade --install` is the idempotent form: it installs when missing and
    # is a no-op when already current. It landed in pipx 1.5; older pipx exits
    # non-zero on the unknown flag, so fall back to the two-step it replaces.
    if ! $MANAGER upgrade --install "$PKG" 2>/dev/null; then
        $MANAGER install "$PKG" 2>/dev/null || $MANAGER upgrade "$PKG"
    fi
fi
export PATH="$HOME/.local/bin:$PATH"

# ----------------------------------------------------------------- 3/3: setup
echo "[3/3] Provisioning the environment (magi setup)..."
# `curl … | sh` hands this script to the shell on stdin, so every child process
# inherits a pipe that is already at EOF. `magi setup` asks which optional
# features you want, and with no terminal to ask on it silently takes the
# defaults — in exactly the situation where a fresh machine most needs the
# questions. Reconnect stdin to the controlling terminal when there is one.
if [ -r /dev/tty ]; then
    magi setup < /dev/tty || echo "magi setup reported issues - run 'magi setup' again later."
else
    # No terminal at all (CI, a container, a provisioning script). Take the
    # defaults quietly and say how to answer the questions later.
    magi setup --yes || echo "magi setup reported issues - run 'magi setup' again later."
    echo "note: no terminal available, so the optional-feature questions were"
    echo "      skipped. Run 'magi setup --optionals' to answer them."
fi

echo ""
echo "MAGI installed. If 'magi' is not found, open a new shell (PATH refresh)."
echo "Re-run this same command any time to upgrade."
echo "Migrating from Wikify? Run 'magi migrate' at your hub root."
