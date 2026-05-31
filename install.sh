#!/usr/bin/env bash
# Agentic Wiki Skills — Automated Installer for Linux / macOS
# Deploys skills/ and bin/ (side by side) into a target directory your AI tool
# scans for skills, plus requirements.txt, .env.example and config.yaml.
set -euo pipefail

# Resolve the repo root from this script's location so it works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "  Agentic Wiki Skills Installer"
echo "========================================="

# --- Target directory ---------------------------------------------------------
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    read -r -p "Enter target directory (e.g. ~/.claude or <project>/.agents): " TARGET
fi
TARGET="${TARGET/#\~/$HOME}"   # expand a leading ~
if [ -z "$TARGET" ]; then
    echo "[ERROR] No target directory provided." >&2
    exit 1
fi

# The skills resolve helper scripts as <BIN>/..., where <BIN> is the bin/ folder
# *beside* the installed skills (<SKILL_DIR>/../../bin). Any target name works as
# long as skills/ and bin/ are deployed side by side -- which this installer does.
# Install into the directory your AI tool scans for skills, e.g. ~/.claude for
# Claude Code, or .agents / .gemini for Gemini.
echo "Skills -> '$TARGET/skills', helper scripts -> '$TARGET/bin' (resolved automatically as <BIN>)."

# --- System dependency check --------------------------------------------------
echo ""
echo "[1/3] Checking system dependencies..."
missing=()
command -v pandoc   >/dev/null 2>&1 || missing+=("pandoc")
command -v pdftoppm >/dev/null 2>&1 || missing+=("poppler")    # binary: pdftoppm
command -v rg       >/dev/null 2>&1 || missing+=("ripgrep")

if [ "${#missing[@]}" -gt 0 ]; then
    echo "[!] Missing: ${missing[*]}"
    if command -v brew >/dev/null 2>&1; then
        read -r -p "Install via Homebrew? (Y/n): " ans
        if [ -z "$ans" ] || [ "${ans,,}" = "y" ]; then
            brew install "${missing[@]}"   # brew names: pandoc poppler ripgrep
        fi
    elif command -v apt-get >/dev/null 2>&1; then
        # apt package names differ slightly (poppler -> poppler-utils).
        echo "    Run: sudo apt-get install -y ${missing[*]/poppler/poppler-utils}"
    else
        echo "    Install manually (see README section 2.2)."
    fi
else
    echo "[OK] System dependencies found."
fi

# pdflatex (a TeX distribution) is optional but recommended: it powers deep
# semantic math validation. Without it, validate_math_latex.py silently falls
# back to structural-only checks via pylatexenc.
if ! command -v pdflatex >/dev/null 2>&1; then
    echo "[i] pdflatex (TeX) not found - math validation will use the lighter pylatexenc fallback."
    echo "    For full validation: 'brew install --cask mactex-no-gui' (macOS) or 'sudo apt-get install texlive-latex-extra' (Linux)."
else
    echo "[OK] pdflatex found (deep math validation enabled)."
fi

# --- Copy skills + scripts ----------------------------------------------------
mkdir -p "$TARGET/skills" "$TARGET/bin"

# Clear existing wiki_* skills so renamed/removed files don't go stale.
shopt -s nullglob
existing=("$TARGET"/skills/wiki_*)
shopt -u nullglob
if [ "${#existing[@]}" -gt 0 ]; then
    echo "Clearing existing wiki skills..."
    rm -rf "${existing[@]}"
fi

echo ""
echo "[2/3] Copying skills..."
cp -R "$SCRIPT_DIR"/skills/. "$TARGET/skills/"

echo "[3/3] Copying bin scripts..."
cp -R "$SCRIPT_DIR"/bin/. "$TARGET/bin/"

# Strip Python caches that may have been copied.
find "$TARGET/skills" "$TARGET/bin" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$TARGET/skills" "$TARGET/bin" -type f -name '*.pyc' -delete 2>/dev/null || true

# requirements.txt + .env.example
cp -f "$SCRIPT_DIR/requirements.txt" "$TARGET/"
[ -f "$SCRIPT_DIR/.env.example" ] && cp -f "$SCRIPT_DIR/.env.example" "$TARGET/"

# config.yaml — never overwrite an existing user config.
if [ -f "$SCRIPT_DIR/config.yaml" ]; then
    if [ -f "$TARGET/config.yaml" ]; then
        echo "[!] config.yaml already exists at target. Saving template as config.yaml.new to preserve your settings."
        cp -f "$SCRIPT_DIR/config.yaml" "$TARGET/config.yaml.new"
    else
        cp -f "$SCRIPT_DIR/config.yaml" "$TARGET/config.yaml"
        echo "[OK] Deployed config.yaml"
    fi
fi

# --- Python dependencies ------------------------------------------------------
echo ""
echo "[*] Installing Python dependencies..."
PY="python3"
command -v python3 >/dev/null 2>&1 || PY="python"
if command -v "$PY" >/dev/null 2>&1; then
    "$PY" -m pip install -r "$TARGET/requirements.txt" -q
else
    echo "[!] Python not found on PATH. Install Python 3.10+ and run: python3 -m pip install -r \"$TARGET/requirements.txt\""
fi

# --- Verify -------------------------------------------------------------------
if [ -f "$TARGET/bin/llm-wiki.py" ]; then
    skills_n="$(find "$TARGET/skills" -maxdepth 1 -type d -name 'wiki_*' | wc -l | tr -d ' ')"
    scripts_n="$(find "$TARGET/bin" -maxdepth 1 -type f -name '*.py' | wc -l | tr -d ' ')"
    echo ""
    echo "[OK] Installation completed successfully!"
    echo "  $skills_n skills, $scripts_n scripts deployed to $TARGET"
else
    echo "[ERROR] Deployment failed: '$TARGET/bin/llm-wiki.py' not found." >&2
    exit 1
fi
