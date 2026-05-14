# App Review Analyzer — Windows PowerShell installer
# Run from the project root:  .\setup.ps1
#
# If PowerShell blocks the script with "running scripts is disabled":
#   * One-shot:   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#   * Per-user:   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   * Safest:     Unblock-File .\setup.ps1   (after reading it)
#
# This script picks a usable Python (>= 3.10) then delegates to install.py,
# which handles the venv, dependency install, and smoke test. Any extra args
# you pass here are forwarded verbatim (e.g. .\setup.ps1 --yes --no-playwright).

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$UserArgs
)

$ErrorActionPreference = "Stop"

function Write-Info($msg)  { Write-Host "→ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "! $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "ERROR: $msg" -ForegroundColor Red }

Write-Host "App Review Analyzer — setup`n" -ForegroundColor Green

# ──────────────────────────────────────────────────────────────────
# Pick a usable Python (>= 3.10) and verify architecture
# ──────────────────────────────────────────────────────────────────
$candidates = @(
    @{Cmd = "python3.13"; LauncherArgs = @()},
    @{Cmd = "python3.12"; LauncherArgs = @()},
    @{Cmd = "python3.11"; LauncherArgs = @()},
    @{Cmd = "python3.10"; LauncherArgs = @()},
    @{Cmd = "py";         LauncherArgs = @("-3.13")},
    @{Cmd = "py";         LauncherArgs = @("-3.12")},
    @{Cmd = "py";         LauncherArgs = @("-3.11")},
    @{Cmd = "py";         LauncherArgs = @("-3.10")},
    @{Cmd = "python";     LauncherArgs = @()},
    @{Cmd = "python3";    LauncherArgs = @()}
)

$systemArch = $env:PROCESSOR_ARCHITECTURE
if ($systemArch -eq "AMD64" -and $env:PROCESSOR_ARCHITEW6432) {
    # Running 32-bit PowerShell on a 64-bit OS
    $systemArch = $env:PROCESSOR_ARCHITEW6432
}

$pythonExe = $null
$pythonLauncherArgs = @()
$pythonVersion = $null
$pythonArch = $null

foreach ($cand in $candidates) {
    try {
        $exe = $cand.Cmd
        $launcherArgs = $cand.LauncherArgs

        # Probe version + arch in one call
        $probe = & $exe @launcherArgs -c "import sys, platform; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}|{platform.machine()}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { continue }

        $parts = $probe.Trim() -split "\|"
        if ($parts.Length -ne 2) { continue }
        $verStr = $parts[0]
        $archStr = $parts[1]

        $verParts = $verStr -split "\."
        $major = [int]$verParts[0]
        $minor = [int]$verParts[1]

        # Need Python >= 3.10
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) { continue }

        # On Windows-on-ARM hosts, refuse x86/x64 Python (same reason as the Mac arm64 check —
        # native pandas/numpy will fail to build under emulation)
        if ($systemArch -eq "ARM64" -and $archStr -notmatch "^(ARM64|arm64|aarch64)$") {
            Write-Warn "Skipping $exe $($launcherArgs -join ' ') — it's $archStr but this is Windows-on-ARM. Native deps will fail."
            continue
        }

        $pythonExe = $exe
        $pythonLauncherArgs = $launcherArgs
        $pythonVersion = $verStr
        $pythonArch = $archStr
        break
    } catch {
        continue
    }
}

if (-not $pythonExe) {
    Write-Err "Could not find a usable Python (>= 3.10) matching this machine's architecture ($systemArch)."
    Write-Host "  Install Python from https://www.python.org/downloads/ — check 'Add Python to PATH' during install."
    Write-Host "  Or:  winget install Python.Python.3.13"
    if ($systemArch -eq "ARM64") {
        Write-Host "  (You're on Windows-on-ARM — make sure you install the ARM64 build, not x64.)"
    }
    exit 1
}

if ($pythonLauncherArgs.Count -gt 0) {
    Write-Info "Using Python $pythonVersion ($pythonArch)  via:  $pythonExe $($pythonLauncherArgs -join ' ')"
} else {
    Write-Info "Using Python $pythonVersion ($pythonArch)  ($pythonExe)"
}

# ──────────────────────────────────────────────────────────────────
# Delegate to install.py — preserves stdout UTF-8 via PYTHONUTF8
# ──────────────────────────────────────────────────────────────────
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installPy = Join-Path $scriptDir "install.py"

if (-not (Test-Path $installPy)) {
    Write-Err "install.py not found at $installPy"
    exit 1
}

# Force UTF-8 stdout in the child Python process — protects against UnicodeEncodeError
# when printing non-ASCII review text under locales like LC_ALL=C
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Forward the user's args ($UserArgs) verbatim — NOT $args (which is the script's
# automatic var and gets clobbered by foreach-iteration locals in older versions).
if ($null -eq $UserArgs) { $UserArgs = @() }

& $pythonExe @pythonLauncherArgs $installPy @UserArgs

exit $LASTEXITCODE
