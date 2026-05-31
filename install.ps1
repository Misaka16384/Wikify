# Allow user to specify target via argument or prompt
param(
    [string]$Target = ""
)

# Gemini Wiki Skills — Automated Installer for Windows PowerShell
# Deploys bin/ and skills/ to a user-specified target directory.
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Gemini Wiki Skills Installer" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

if (-not $Target) {
    $Target = Read-Host "Enter target project directory (e.g. D:\文档\MindPalace\.agents)"
}

if (-not $Target -or -not (Test-Path $Target -IsValid)) {
    Write-Error "Invalid target directory: '$Target'"
    exit 1
}

$Resolved = Resolve-Path -LiteralPath $Target -ErrorAction SilentlyContinue
if ($Resolved) {
    $Target = $Resolved.Path
}
# If not resolved, keep $Target as-is (user-provided path that may not exist yet)

Write-Host "Target Directory: $Target" -ForegroundColor Yellow

# The skills resolve helper scripts as `<BIN>/...`, where `<BIN>` is the `bin/`
# folder *beside* the installed skills (`<SKILL_DIR>/../../bin`). Any target name
# works as long as `skills/` and `bin/` are deployed side by side -- which this
# installer always does. Install into the directory your AI tool scans for skills,
# e.g. `.claude` for Claude Code, or `.agents` / `.gemini` for Gemini.
Write-Host "Skills -> '$Target\skills', helper scripts -> '$Target\bin' (resolved automatically as <BIN>)." -ForegroundColor DarkGray

# Check system dependencies
Write-Host "`n[1/3] Checking system dependencies..." -ForegroundColor Cyan
$missing = @()
if (-not (Get-Command "pandoc" -ErrorAction SilentlyContinue)) { $missing += "pandoc" }
if (-not (Get-Command "pdftoppm" -ErrorAction SilentlyContinue)) { $missing += "poppler" }
if (-not (Get-Command "rg" -ErrorAction SilentlyContinue)) { $missing += "ripgrep" }
if ($missing.Count -gt 0) {
    Write-Host "[!] Missing: $($missing -join ', '). Required for LaTeX (.tex) ingestion." -ForegroundColor Yellow
    $install = Read-Host "Would you like to automatically install them? (Y/n)"
    if ($install -eq "" -or $install.ToLower() -eq "y") {
        if (Get-Command "scoop" -ErrorAction SilentlyContinue) {
            Write-Host "Installing via Scoop..." -ForegroundColor Green
            scoop install @missing
        } elseif (Get-Command "choco" -ErrorAction SilentlyContinue) {
            Write-Host "Scoop not found; installing via Chocolatey..." -ForegroundColor Green
            choco install @missing -y
        } else {
            Write-Host "[!] Neither Scoop nor Chocolatey found. Please install manually (see README section 2.2)." -ForegroundColor Red
        }
    }
} else {
    Write-Host "[OK] System dependencies found." -ForegroundColor Green
}

# pdflatex (a TeX distribution) is optional but recommended: it powers deep
# semantic math validation (double subscripts, unbalanced braces, bad delimiters).
# Without it, validate_math_latex.py silently falls back to structural-only
# checks via pylatexenc, so the advertised pdflatex-backed validation is off.
if (-not (Get-Command "pdflatex" -ErrorAction SilentlyContinue)) {
    Write-Host "[i] pdflatex (TeX) not found - math validation will use the lighter pylatexenc fallback." -ForegroundColor DarkYellow
    Write-Host "    For full pdflatex-backed validation install MiKTeX ('scoop install miktex' / 'choco install miktex') or TeX Live." -ForegroundColor DarkYellow
} else {
    Write-Host "[OK] pdflatex found (deep math validation enabled)." -ForegroundColor Green
}

# Create target folders
New-Item -ItemType Directory -Force -Path "$Target\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "$Target\bin" | Out-Null

# Clean target wiki skills to prevent stale files
$existingSkills = Get-ChildItem "$Target\skills" -Directory -Filter "wiki_*" -ErrorAction SilentlyContinue
if ($existingSkills.Count -gt 0) {
    Write-Host "Clearing existing wiki skills..." -ForegroundColor DarkGray
    $existingSkills | Remove-Item -Recurse -Force
}

# Copy skills (excluding empty __pycache__ and .git artifacts)
Write-Host "`n[2/3] Copying skills..." -ForegroundColor Cyan
Copy-Item -Recurse -Force ".\skills\*" "$Target\skills\" -Exclude "__pycache__","*.pyc"

# Copy bin scripts
Write-Host "`n[3/3] Copying bin scripts..." -ForegroundColor Cyan
Copy-Item -Recurse -Force ".\bin\*" "$Target\bin\" -Exclude "__pycache__","*.pyc"

# Copy requirements.txt and .env.example
Copy-Item -Force ".\requirements.txt" "$Target\"
if (Test-Path ".\.env.example") {
    Copy-Item -Force ".\.env.example" "$Target\"
}

# Copy unified config.yaml (do NOT overwrite existing user config)
if (Test-Path ".\config.yaml") {
    $targetConfig = Join-Path $Target "config.yaml"
    if (Test-Path $targetConfig) {
        Write-Host "[!] config.yaml already exists at target. Skipping to preserve your settings." -ForegroundColor Yellow
        Write-Host "    New template saved as config.yaml.new for reference." -ForegroundColor Yellow
        Copy-Item -Force ".\config.yaml" (Join-Path $Target "config.yaml.new")
    } else {
        Copy-Item -Force ".\config.yaml" $targetConfig
        Write-Host "[OK] Deployed config.yaml" -ForegroundColor Green
    }
}

# Install Python dependencies (use `python -m pip` so it targets the active
# interpreter / venv rather than whatever bare `pip` happens to be on PATH).
Write-Host "`n[*] Installing Python dependencies..." -ForegroundColor Cyan
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    python -m pip install -r "$Target\requirements.txt" -q
} else {
    Write-Host "[!] Python not found on PATH. Install Python 3.10+ and run: python -m pip install -r `"$Target\requirements.txt`"" -ForegroundColor Red
}

# Final Verification
if (Test-Path "$Target\bin\llm-wiki.py") {
    Write-Host "`n[OK] Installation completed successfully!" -ForegroundColor Green
    Write-Host "Skills deployed to: $Target\skills" -ForegroundColor Yellow
    Write-Host "Scripts deployed to: $Target\bin" -ForegroundColor Yellow
    
    # Show summary
    $skillCount = (Get-ChildItem "$Target\skills" -Directory -Filter "wiki_*").Count
    $scriptCount = (Get-ChildItem "$Target\bin\*.py" -File).Count
    Write-Host "  $skillCount skills, $scriptCount scripts" -ForegroundColor Gray
} else {
    Write-Error "Deployment failed. Could not verify target files."
}
