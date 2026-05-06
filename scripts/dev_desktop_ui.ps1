param(
    [ValidateSet("install", "dev", "build", "health")]
    [string]$Task = "dev"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DesktopUi = Join-Path $Root "desktop_ui"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

switch ($Task) {
    "install" {
        Write-Step "Installing desktop UI dependencies"
        Push-Location $DesktopUi
        try { npm install } finally { Pop-Location }
    }
    "dev" {
        Write-Step "Starting Beavis Tauri desktop UI"
        Push-Location $DesktopUi
        try { npm run tauri dev } finally { Pop-Location }
    }
    "build" {
        Write-Step "Building Beavis Tauri desktop UI"
        Push-Location $DesktopUi
        try { npm run tauri build } finally { Pop-Location }
    }
    "health" {
        Write-Step "Checking Python API bridge"
        Push-Location $Root
        try { python -m python_agent.bridge.oneshot system.health } finally { Pop-Location }
    }
}
