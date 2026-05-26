# Gemini Wiki Skills — Automated Installer for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Gemini Wiki Skills Installer" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$ConfigRoot = "$HOME\.gemini\config"
Write-Host "Target Configuration Directory: $ConfigRoot" -ForegroundColor Yellow

# Create config folders if they don't exist
New-Item -ItemType Directory -Force -Path "$ConfigRoot\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigRoot\bin" | Out-Null

# Clean target directories if pre-existing to prevent stale file issues
if (Test-Path "$ConfigRoot\skills\wiki_*") {
    Write-Host "Clearing existing wiki skills..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force "$ConfigRoot\skills\wiki_*"
}

# Copy skills
Write-Host "Copying skills..." -ForegroundColor Green
Copy-Item -Recurse -Force ".\skills\*" "$ConfigRoot\skills\"

# Copy bin
Write-Host "Copying bin scripts..." -ForegroundColor Green
Copy-Item -Recurse -Force ".\bin\*" "$ConfigRoot\bin\"

# Final Check
if (Test-Path "$ConfigRoot\bin\llm-wiki.py") {
    Write-Host "`n✓ Installation completed successfully!" -ForegroundColor Green
    Write-Host "Skills are deployed to: $ConfigRoot\skills" -ForegroundColor Yellow
    Write-Host "Scripts are deployed to: $ConfigRoot\bin" -ForegroundColor Yellow
} else {
    Write-Error "Deployment failed. Could not verify target files."
}
