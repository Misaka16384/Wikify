# Gemini Wiki Skills — Automated Installer for Windows PowerShell
# Deploys bin/ and skills/ to a user-specified target directory.
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Gemini Wiki Skills Installer" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Allow user to specify target via argument or prompt
param(
    [string]$Target = ""
)

if (-not $Target) {
    $Target = Read-Host "Enter target project directory (e.g. D:\文档\MindPalace\.agents)"
}

if (-not $Target -or -not (Test-Path $Target -IsValid)) {
    Write-Error "Invalid target directory: '$Target'"
    exit 1
}

$Target = (Resolve-Path -LiteralPath $Target -ErrorAction SilentlyContinue)?.Path
if (-not $Target) {
    # Target doesn't exist yet, create it
    $Target = $args[0]
}

Write-Host "Target Directory: $Target" -ForegroundColor Yellow

# Check system dependencies
Write-Host "`n[1/3] Checking system dependencies..." -ForegroundColor Cyan
$missing = @()
if (-not (Get-Command "pandoc" -ErrorAction SilentlyContinue)) { $missing += "pandoc" }
if (-not (Get-Command "pandoc-crossref" -ErrorAction SilentlyContinue)) { $missing += "pandoc-crossref" }
if ($missing.Count -gt 0) {
    Write-Host "[!] Missing: $($missing -join ', '). Required for LaTeX (.tex) ingestion." -ForegroundColor Yellow
    $install = Read-Host "Would you like to automatically install them via Scoop? (Y/n)"
    if ($install -eq "" -or $install.ToLower() -eq "y") {
        if (Get-Command "scoop" -ErrorAction SilentlyContinue) {
            Write-Host "Installing via scoop..." -ForegroundColor Green
            scoop install @missing
        } else {
            Write-Host "[!] Scoop is not installed. Please install manually." -ForegroundColor Red
        }
    }
} else {
    Write-Host "✓ Pandoc and pandoc-crossref are installed." -ForegroundColor Green
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

# Final Verification
if (Test-Path "$Target\bin\llm-wiki.py") {
    Write-Host "`n✓ Installation completed successfully!" -ForegroundColor Green
    Write-Host "Skills deployed to: $Target\skills" -ForegroundColor Yellow
    Write-Host "Scripts deployed to: $Target\bin" -ForegroundColor Yellow
    
    # Show summary
    $skillCount = (Get-ChildItem "$Target\skills" -Directory -Filter "wiki_*").Count
    $scriptCount = (Get-ChildItem "$Target\bin\*.py" -File).Count
    Write-Host "  $skillCount skills, $scriptCount scripts" -ForegroundColor Gray
} else {
    Write-Error "Deployment failed. Could not verify target files."
}
