param(
    [ValidateSet(
        "help",
        "setup",
        "configure",
        "build",
        "index",
        "test",
        "test-all",
        "train",
        "smoke",
        "voice-test",
        "ui-install",
        "ui-dev",
        "ui-build",
        "ui-health",
        "run",
        "all",
        "clean"
    )]
    [string]$Task = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CppRuntime = Join-Path $Root "cpp_runtime"
$BuildDir = Join-Path $CppRuntime "build"
$DesktopUi = Join-Path $Root "desktop_ui"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-RepoCommand([scriptblock]$Command) {
    Push-Location $Root
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Find-VisualStudioInstall {
    if ($env:BEAVIS_VS_INSTALL -and (Test-Path $env:BEAVIS_VS_INSTALL)) {
        return $env:BEAVIS_VS_INSTALL
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($install -and (Test-Path $install)) {
            return $install
        }
    }

    $candidates = @(
        "$env:ProgramFiles\Microsoft Visual Studio\2022\Professional",
        "$env:ProgramFiles\Microsoft Visual Studio\2022\Community",
        "$env:ProgramFiles\Microsoft Visual Studio\2022\Enterprise",
        "$env:ProgramFiles\Microsoft Visual Studio\2022\BuildTools"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Visual Studio 2022 with C++ tools was not found"
}

function Get-ToolPath([string]$EnvName, [string]$Candidate, [string]$CommandName) {
    $envValue = [Environment]::GetEnvironmentVariable($EnvName)
    if ($envValue -and (Test-Path $envValue)) {
        return $envValue
    }

    if ($Candidate -and (Test-Path $Candidate)) {
        return $Candidate
    }

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "$CommandName was not found"
}

function Get-BuildTools {
    $vsInstall = Find-VisualStudioInstall
    $vsDevCmd = Get-ToolPath `
        -EnvName "BEAVIS_VSDEVCMD" `
        -Candidate (Join-Path $vsInstall "Common7\Tools\VsDevCmd.bat") `
        -CommandName "VsDevCmd.bat"

    $cmake = Get-ToolPath `
        -EnvName "BEAVIS_CMAKE" `
        -Candidate (Join-Path $vsInstall "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe") `
        -CommandName "cmake"

    $ninja = Get-ToolPath `
        -EnvName "BEAVIS_NINJA" `
        -Candidate (Join-Path $vsInstall "Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe") `
        -CommandName "ninja"

    return @{
        VsDevCmd = $vsDevCmd
        CMake = $cmake
        Ninja = $ninja
    }
}

function Invoke-VsCommand([string]$CommandLine) {
    $tools = Get-BuildTools
    $cmdLine = "`"$($tools.VsDevCmd)`" -arch=x64 && $CommandLine"
    & cmd.exe /c $cmdLine
    if ($LASTEXITCODE -ne 0) {
        throw "Build command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Setup {
    Write-Step "Installing Python dependencies"
    Invoke-RepoCommand { python -m pip install -r requirements.txt }
}

function Invoke-Configure {
    Write-Step "Configuring C++ runtime"
    $tools = Get-BuildTools
    $command = "`"$($tools.CMake)`" -S `"$CppRuntime`" -B `"$BuildDir`" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_MAKE_PROGRAM=`"$($tools.Ninja)`""
    Invoke-VsCommand $command
}

function Invoke-Build {
    if (-not (Test-Path (Join-Path $BuildDir "CMakeCache.txt"))) {
        Invoke-Configure
    }

    Write-Step "Building C++ runtime"
    $tools = Get-BuildTools
    Invoke-VsCommand "`"$($tools.CMake)`" --build `"$BuildDir`""
}

function Invoke-Index {
    Write-Step "Indexing installed applications"
    Invoke-RepoCommand { python -m python_agent.resolvers.app_indexer }
}

function Invoke-Test {
    Write-Step "Compiling Python sources"
    Invoke-RepoCommand { python -m compileall python_agent }

    Write-Step "Testing golden command pipeline"
    Invoke-RepoCommand { python python_agent\training\test_golden_commands.py }

    Write-Step "Testing skill classifier"
    Invoke-RepoCommand { python python_agent\training\test_skill_classifier.py }

    Write-Step "Testing open_app argument model"
    Invoke-RepoCommand { python python_agent\training\test_open_app_arg_model.py }

    Write-Step "Testing user app add flow"
    Invoke-RepoCommand { python python_agent\training\test_add_user_app.py }

    Write-Step "Testing window_control argument model"
    Invoke-RepoCommand { python python_agent\training\test_window_control_arg_model.py }

    Write-Step "Testing window_layout argument model"
    Invoke-RepoCommand { python python_agent\training\test_window_layout_arg_model.py }

    Write-Step "Testing voice settings and VAD"
    Invoke-RepoCommand { python python_agent\training\test_voice.py }
}

function Invoke-TestAll {
    Invoke-Test

    Write-Step "Testing volume_set argument model"
    Invoke-RepoCommand { python python_agent\training\test_volume_set_arg_model.py }
}

function Invoke-Train {
    Write-Step "Training window_control argument model"
    Invoke-RepoCommand {
        python python_agent\training\generate_window_control_dataset.py
        python python_agent\training\train_window_control_arg_model.py
        python python_agent\training\test_window_control_arg_model.py
    }

    Write-Step "Training window_layout argument model"
    Invoke-RepoCommand {
        python python_agent\training\generate_window_layout_dataset.py
        python python_agent\training\train_window_layout_arg_model.py
        python python_agent\training\test_window_layout_arg_model.py
    }

    Write-Step "Training skill classifier"
    Invoke-RepoCommand {
        python python_agent\training\generate_skill_classifier_dataset.py
        python python_agent\training\train_skill_classifier.py
        python python_agent\training\test_skill_classifier.py
    }
}

function Invoke-Smoke {
    Write-Step "Pipeline smoke tests without execution"
    Invoke-RepoCommand {
        $commands = @(
            "0L7RgtC60YDQvtC5INGF0YDQvtC8",
            "0YHQstC10YDQvdC4INGC0LXQu9C10LPRgNCw0Lw=",
            "YmF2aXMg0YHQtNC10LvQsNC5INGB0L/RgNCw0LLQviBjb2RleA=="
        ) | ForEach-Object {
            [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_))
        }

        foreach ($command in $commands) {
            python -m python_agent.main $command --no-log
            if ($LASTEXITCODE -ne 0) {
                throw "Smoke command failed: $command"
            }
        }
    }
}

function Invoke-VoiceTest {
    Write-Step "Testing microphone with faster-whisper"
    Invoke-RepoCommand { python -m python_agent.voice.manual_test }
}

function Invoke-DesktopUiInstall {
    Write-Step "Installing desktop UI dependencies"
    Push-Location $DesktopUi
    try { npm install } finally { Pop-Location }
}

function Invoke-DesktopUiDev {
    Write-Step "Starting Beavis Tauri desktop UI"
    Push-Location $DesktopUi
    try { npm run tauri dev } finally { Pop-Location }
}

function Invoke-DesktopUiBuild {
    Write-Step "Building Beavis Tauri desktop UI"
    Push-Location $DesktopUi
    try { npm run tauri build } finally { Pop-Location }
}

function Invoke-DesktopUiHealth {
    Write-Step "Checking Python API bridge"
    Invoke-RepoCommand { python -m python_agent.bridge.oneshot system.health }
}

function Invoke-Run {
    if (-not $Rest -or $Rest.Count -eq 0) {
        throw "Usage: .\scripts\dev.ps1 run `"команда`" [--execute]"
    }

    Invoke-RepoCommand { python -m python_agent.main @Rest }
}



function Invoke-Clean {
    Write-Step "Removing local generated build/cache/log files"

    $targets = @(
        (Join-Path $Root "cpp_runtime\build"),
        (Join-Path $Root "desktop_ui\dist"),
        (Join-Path $Root "desktop_ui\.vite"),
        (Join-Path $Root "desktop_ui\src-tauri\target"),
        (Join-Path $Root "desktop_ui\src-tauri\gen"),
        (Join-Path $Root "python_agent\data\cache"),
        (Join-Path $Root "python_agent\data\logs"),
        (Join-Path $Root "python_agent\data\feedback")
    )

    $targets += Get-ChildItem -Path $DesktopUi -Force -File -Filter ".vite-dev-*.log" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }

    $targets += Get-ChildItem -Path (Join-Path $Root "python_agent") -Directory -Recurse -Force |
        Where-Object { $_.Name -eq "__pycache__" } |
        ForEach-Object { $_.FullName }

    foreach ($target in $targets) {
        if (-not (Test-Path $target)) {
            continue
        }

        $resolved = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolved.StartsWith($Root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove outside repo: $resolved"
        }

        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-Host "removed $resolved"
    }
}

function Show-Help {
    Write-Host @"
Beavis Agent developer commands

Usage:
  .\scripts\dev.ps1 setup       Install Python dependencies
  .\scripts\dev.ps1 build       Configure if needed and build C++ runtime
  .\scripts\dev.ps1 index       Build local apps index
  .\scripts\dev.ps1 test        Run stable Python/model tests
  .\scripts\dev.ps1 test-all    Run stable tests plus volume_set legacy test
  .\scripts\dev.ps1 train       Regenerate/retrain window_control and skill classifier
  .\scripts\dev.ps1 smoke       Build ToolCall JSON for a few commands
  .\scripts\dev.ps1 voice-test  Record 3 seconds and print Whisper transcript
  .\scripts\dev.ps1 ui-install  Install desktop UI dependencies
  .\scripts\dev.ps1 ui-dev      Start Tauri desktop UI
  .\scripts\dev.ps1 ui-build    Build Tauri desktop UI
  .\scripts\dev.ps1 ui-health   Check Python API bridge used by UI
  .\scripts\dev.ps1 run "<command>" [--execute]
  .\scripts\dev.ps1 all         setup + build + index + test + smoke
  .\scripts\dev.ps1 clean       Remove local generated build/cache/log files

Typical first run:
  .\scripts\dev.ps1 all

Daily work:
  .\scripts\dev.ps1 build
  .\scripts\dev.ps1 test
  .\scripts\dev.ps1 ui-dev
  .\scripts\dev.ps1 run "<command>" --execute
"@
}

switch ($Task) {
    "help" { Show-Help }
    "setup" { Invoke-Setup }
    "configure" { Invoke-Configure }
    "build" { Invoke-Build }
    "index" { Invoke-Index }
    "test" { Invoke-Test }
    "test-all" { Invoke-TestAll }
    "train" { Invoke-Train }
    "smoke" { Invoke-Smoke }
    "voice-test" { Invoke-VoiceTest }
    "ui-install" { Invoke-DesktopUiInstall }
    "ui-dev" { Invoke-DesktopUiDev }
    "ui-build" { Invoke-DesktopUiBuild }
    "ui-health" { Invoke-DesktopUiHealth }
    "run" { Invoke-Run }
    "all" {
        Invoke-Setup
        Invoke-Build
        Invoke-Index
        Invoke-Test
        Invoke-Smoke
    }
    "clean" { Invoke-Clean }
}
