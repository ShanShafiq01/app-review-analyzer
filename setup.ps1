# App Review Analyzer - Windows PowerShell installer
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
#
# Encoding note: this file is intentionally ASCII-only. PowerShell 5.1 (the
# default on Windows 10/11) reads .ps1 files as the system codepage (usually
# Windows-1252) unless there is a UTF-8 BOM. Multibyte UTF-8 characters like
# em-dashes get mojibaked and the parser falls over. v0.3.4 shipped with
# Unicode characters in this file and broke on every Windows install.

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$UserArgs
)

$ErrorActionPreference = "Stop"

function Write-Info($msg)  { Write-Host "-> $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "!  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "ERROR: $msg" -ForegroundColor Red }

Write-Host "App Review Analyzer - setup`n" -ForegroundColor Green

# --------------------------------------------------------------------
# Pick a usable Python (>= 3.10) and verify architecture
# --------------------------------------------------------------------
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

        # Probe version + arch in one call. Use a single quote string to avoid
        # PowerShell variable expansion of $sys.* inside the Python -c argument.
        $probeCode = 'import sys, platform; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}|{platform.machine()}")'
        $probe = & $exe @launcherArgs -c $probeCode 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { continue }

        # Parse the "X.Y.Z|arch" probe output. -split takes a regex, so | needs
        # to be escaped. Use a verbatim regex string to keep PS parser happy.
        $probeTrimmed = "$probe".Trim()
        $parts = $probeTrimmed -split '\|'
        if ($parts.Length -ne 2) { continue }
        $verStr = $parts[0]
        $archStr = $parts[1]

        $verParts = $verStr -split '\.'
        $major = [int]$verParts[0]
        $minor = [int]$verParts[1]

        # Need Python >= 3.10
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) { continue }

        # On Windows-on-ARM hosts, refuse x86/x64 Python (same reason as the
        # Mac arm64 check). Native pandas/numpy will fail to build under
        # emulation.
        if ($systemArch -eq "ARM64" -and $archStr -notmatch "^(ARM64|arm64|aarch64)$") {
            Write-Warn "Skipping $exe $($launcherArgs -join ' ') - it is $archStr but this is Windows-on-ARM. Native deps will fail."
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
    Write-Err "Could not find a usable Python (>= 3.10) matching this machine architecture ($systemArch)."
    Write-Host "  Install Python from https://www.python.org/downloads/ - check 'Add Python to PATH' during install."
    Write-Host "  Or:  winget install Python.Python.3.13"
    if ($systemArch -eq "ARM64") {
        Write-Host "  (You are on Windows-on-ARM - make sure you install the ARM64 build, not x64.)"
    }
    exit 1
}

if ($pythonLauncherArgs.Count -gt 0) {
    Write-Info "Using Python $pythonVersion ($pythonArch)  via:  $pythonExe $($pythonLauncherArgs -join ' ')"
} else {
    Write-Info "Using Python $pythonVersion ($pythonArch)  ($pythonExe)"
}

# --------------------------------------------------------------------
# Delegate to install.py - preserves stdout UTF-8 via PYTHONUTF8
# --------------------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installPy = Join-Path $scriptDir "install.py"

if (-not (Test-Path $installPy)) {
    Write-Err "install.py not found at $installPy"
    exit 1
}

# Force UTF-8 stdout in the child Python process - protects against
# UnicodeEncodeError when printing non-ASCII review text in environments where
# Python defaults to a narrower codepage.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Forward the user args ($UserArgs from the param block) verbatim. Do NOT use
# $args - it is an automatic variable that gets clobbered by foreach-iteration
# locals in older PowerShell versions, which silently drops the user flags.
if ($null -eq $UserArgs) { $UserArgs = @() }

& $pythonExe @pythonLauncherArgs $installPy @UserArgs

exit $LASTEXITCODE
