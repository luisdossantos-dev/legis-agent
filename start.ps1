<#
╔═══════════════════════════════════════════════════════════════╗
║        ⚖️  LEGIS AGENT  🚀                                   ║
║  AI Agents for Legal Documents                               ║
║  Quick Start Script (PowerShell)                             ║
╚═══════════════════════════════════════════════════════════════╝
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Tests
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Info  { Write-Host "ℹ  $($args[0])" -ForegroundColor Blue }
function Ok    { Write-Host "✓  $($args[0])" -ForegroundColor Green }
function Warn  { Write-Host "⚠  $($args[0])" -ForegroundColor Yellow }
function Fail  { Write-Host "✗  $($args[0])" -ForegroundColor Red; exit 1 }
function Ask   { param([string]$Prompt) Write-Host "?  $Prompt`: " -ForegroundColor Cyan -NoNewline; return Read-Host }

# ── Banner ───────────────────────────────────────────────────
Clear-Host
@"
    ╔══════════════════════════════════════════╗
    ║        ⚖️  LEGIS AGENT  🚀              ║
    ║  AI Agents for Legal Documents           ║
    ╚══════════════════════════════════════════╝
"@ | Write-Host
""

# ═══════════════════════════════════════════════════════════════
# 1. CHECK SYSTEM DEPENDENCIES
# ═══════════════════════════════════════════════════════════════
Write-Host "`n── 1/6 — Checking system dependencies ──" -ForegroundColor Cyan

$missing = @()

try {
    $pyVersion = python --version 2>&1
    Ok "Python: $pyVersion"
} catch {
    Warn "Python not found — https://python.org"
    $missing += "python"
}

try {
    $nodeVersion = node --version
    Ok "Node.js: $nodeVersion"
} catch {
    Warn "Node.js not found — https://nodejs.org"
    $missing += "nodejs"
}

try {
    $npmVersion = npm --version
    Ok "npm: $npmVersion"
} catch {
    Warn "npm not found"
    $missing += "npm"
}

try {
    $cargoVersion = cargo --version 2>&1 | Select-Object -First 1
    Ok "Cargo: $cargoVersion"
} catch {
    Warn "Rust/Cargo not found (optional — only needed for Tauri desktop GUI)"
}

try {
    $tauriVersion = cargo tauri --version 2>&1 | Select-Object -First 1
    Ok "Tauri CLI: $tauriVersion"
} catch {
    Warn "Tauri CLI not found (optional — install via: cargo install tauri-cli --version ^2)"
}

# ═══════════════════════════════════════════════════════════════
# 2. SET UP PYTHON VIRTUAL ENVIRONMENT
# ═══════════════════════════════════════════════════════════════
Write-Host "`n── 2/6 — Setting up Python virtual environment ──" -ForegroundColor Cyan

Set-Location "$ScriptDir\backend"

if (-not (Test-Path ".venv")) {
    Info "Creating virtual environment..."
    python -m venv .venv
    Ok "Virtual environment created"
} else {
    Ok "Virtual environment exists"
}

Info "Installing backend dependencies..."
& ".venv\Scripts\pip" install -e ".[dev]" 2>&1 | Out-Null
Ok "Backend dependencies installed"

Set-Location $ScriptDir

# ═══════════════════════════════════════════════════════════════
# 3. INSTALL FRONTEND DEPENDENCIES
# ═══════════════════════════════════════════════════════════════
Write-Host "`n── 3/6 — Installing frontend dependencies ──" -ForegroundColor Cyan

Set-Location "$ScriptDir\frontend"

if (-not (Test-Path "node_modules")) {
    Info "Installing frontend dependencies..."
    npm install
    Ok "Frontend dependencies installed"
} else {
    Ok "Frontend dependencies already installed"
}

Set-Location $ScriptDir

# ═══════════════════════════════════════════════════════════════
# 4. CONFIGURE ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════
Write-Host "`n── 4/6 — Configuring environment variables ──" -ForegroundColor Cyan

Set-Location "$ScriptDir\backend"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Info ".env file created from .env.example"

    $configKeys = Ask "Do you want to configure API keys now? (y/N)"
    if ($configKeys -eq "y" -or $configKeys -eq "Y") {
        $openaiKey = Ask "OpenAI API Key (press Enter to skip)"
        if ($openaiKey) {
            (Get-Content ".env") -replace "LITELLM_API_KEY=.*", "LITELLM_API_KEY=$openaiKey" | Set-Content ".env"
            Ok "OpenAI API key configured"
        }

        $anthropicKey = Ask "Anthropic/Claude API Key (press Enter to skip)"
        if ($anthropicKey) {
            Add-Content ".env" "`nANTHROPIC_API_KEY=$anthropicKey"
            Ok "Anthropic API key configured"
        }

        Info "Tip: Without real API keys the agent runs in simulated mode."
    }
} else {
    Ok ".env file exists"
}

Set-Location $ScriptDir

# ═══════════════════════════════════════════════════════════════
# 5. LAUNCH APPLICATION
# ═══════════════════════════════════════════════════════════════
Write-Host "`n── 5/5 — Launching Legis Agent ──" -ForegroundColor Cyan

if ($BackendOnly) {
    Write-Host "`nStarting backend on http://localhost:8000" -ForegroundColor Green
    Write-Host "API docs: http://localhost:8000/docs`n" -ForegroundColor Green
    Set-Location "$ScriptDir\backend"
    & ".venv\Scripts\uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload

} elseif ($FrontendOnly) {
    Write-Host "`nStarting frontend on http://localhost:1420`n" -ForegroundColor Green
    Set-Location "$ScriptDir\frontend"
    npm run dev

} elseif ($Tests) {
    Write-Host "`nRunning tests...`n" -ForegroundColor Cyan
    Set-Location "$ScriptDir\backend"
    & ".venv\Scripts\pytest" tests/ -v --tb=short 2>&1 | Select-Object -First 60
    Write-Host "`nTests completed" -ForegroundColor Green

} else {
    Write-Host "`n  How would you like to run the app?" -ForegroundColor White
    Write-Host "`n    1  ->  Full Desktop GUI (Tauri + Frontend + Backend)" -ForegroundColor Cyan
    Write-Host "    2  ->  Backend only (API on localhost:8000)" -ForegroundColor Cyan
    Write-Host "    3  ->  Frontend only (React on localhost:1420)" -ForegroundColor Cyan
    Write-Host "    4  ->  Run backend tests`n" -ForegroundColor Cyan

    $choice = Ask "Choose an option (1-4)"

    switch ($choice) {
        "1" {
            Write-Host "`nStarting backend in background..." -ForegroundColor Cyan
            Set-Location "$ScriptDir\backend"
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = (Get-Command "uvicorn").Source
            $psi.Arguments = "app.main:app --host 0.0.0.0 --port 8000"
            $psi.WorkingDirectory = "$ScriptDir\backend"
            $psi.UseShellExecute = $false
            $psi.RedirectStandardOutput = $true
            $p = [System.Diagnostics.Process]::Start($psi)
            Ok "Backend started (PID: $($p.Id))"

            Start-Sleep 3

            if (Get-Command "cargo" -ErrorAction SilentlyContinue) {
                try {
                    $tauriVer = cargo tauri --version 2>&1
                    Set-Location $ScriptDir
                    cargo tauri dev
                } catch {
                    Warn "Tauri CLI not available. Installing..."
                    cargo install tauri-cli --version "^2"
                    Set-Location $ScriptDir
                    cargo tauri dev
                }
            } else {
                Warn "Cargo not available. Starting frontend only..."
                Set-Location "$ScriptDir\frontend"
                npm run dev
            }
        }
        "2" {
            Set-Location "$ScriptDir\backend"
            & ".venv\Scripts\uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
        }
        "3" {
            Set-Location "$ScriptDir\frontend"
            npm run dev
        }
        "4" {
            Set-Location "$ScriptDir\backend"
            & ".venv\Scripts\pytest" tests/ -v --tb=short
        }
        default {
            Warn "Invalid option. Starting backend only..."
            Set-Location "$ScriptDir\backend"
            & ".venv\Scripts\uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
        }
    }
}
