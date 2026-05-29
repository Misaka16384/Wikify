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

# The skills invoke scripts via the hardcoded prefix `.agents/bin/...`, resolved
# relative to the agent's working directory (the project root). That only works
# if the install target is a folder named `.agents` at the project root.
if ((Split-Path $Target -Leaf) -ne ".agents") {
    Write-Host "[!] Target is not named '.agents'. The skills call scripts as '.agents/bin/...'" -ForegroundColor Yellow
    Write-Host "    relative to the project root, so they will not resolve unless you install into" -ForegroundColor Yellow
    Write-Host "    a '.agents' folder (e.g. <your-project>\.agents) and run the agent from that root." -ForegroundColor Yellow
}

# Check system dependencies
Write-Host "`n[1/3] Checking system dependencies..." -ForegroundColor Cyan
$missing = @()
if (-not (Get-Command "pandoc" -ErrorAction SilentlyContinue)) { $missing += "pandoc" }
if (-not (Get-Command "pdftoppm" -ErrorAction SilentlyContinue)) { $missing += "poppler" }
if (-not (Get-Command "rg" -ErrorAction SilentlyContinue)) { $missing += "ripgrep" }
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
    Write-Host "✓ System dependencies found." -ForegroundColor Green
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
        Write-Host "✓ Deployed config.yaml" -ForegroundColor Green
    }
}

# Install Python dependencies
Write-Host "`n[*] Installing Python dependencies..." -ForegroundColor Cyan
pip install -r "$Target\requirements.txt" -q

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
