# Gemini Wiki Skills — Automated Installer for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Gemini Wiki Skills Installer" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$ConfigRoot = "$HOME\.gemini\config"
Write-Host "Target Configuration Directory: $ConfigRoot" -ForegroundColor Yellow

# Check system dependencies
Write-Host "`n[1/3] Checking system dependencies..." -ForegroundColor Cyan
if (-not (Get-Command "pandoc" -ErrorAction SilentlyContinue) -or -not (Get-Command "pandoc-crossref" -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Pandoc or pandoc-crossref is missing. Required for LaTeX (.tex) ingestion." -ForegroundColor Yellow
    $install = Read-Host "Would you like to automatically install them via Scoop? (Y/n)"
    if ($install -eq "" -or $install.ToLower() -eq "y") {
        if (Get-Command "scoop" -ErrorAction SilentlyContinue) {
            Write-Host "Installing pandoc and pandoc-crossref via scoop..." -ForegroundColor Green
            scoop install pandoc pandoc-crossref
        } else {
            Write-Host "[!] Scoop is not installed. Please install pandoc manually." -ForegroundColor Red
        }
    }
} else {
    Write-Host "✓ Pandoc and pandoc-crossref are installed." -ForegroundColor Green
}

# Create config folders if they don't exist
New-Item -ItemType Directory -Force -Path "$ConfigRoot\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigRoot\bin" | Out-Null

# Clean target directories if pre-existing to prevent stale file issues
if (Test-Path "$ConfigRoot\skills\wiki_*") {
    Write-Host "Clearing existing wiki skills..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force "$ConfigRoot\skills\wiki_*"
}

# Copy skills
Write-Host "`n[2/3] Copying skills..." -ForegroundColor Cyan
Copy-Item -Recurse -Force ".\skills\*" "$ConfigRoot\skills\"

# Copy bin
Write-Host "`n[3/3] Copying bin scripts..." -ForegroundColor Cyan
Copy-Item -Recurse -Force ".\bin\*" "$ConfigRoot\bin\"

# Final Check
if (Test-Path "$ConfigRoot\bin\llm-wiki.py") {
    Write-Host "`n✓ Installation completed successfully!" -ForegroundColor Green
    Write-Host "Skills are deployed to: $ConfigRoot\skills" -ForegroundColor Yellow
    Write-Host "Scripts are deployed to: $ConfigRoot\bin" -ForegroundColor Yellow
} else {
    Write-Error "Deployment failed. Could not verify target files."
}
