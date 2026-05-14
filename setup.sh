#!/usr/bin/env bash
# App Review Analyzer — macOS / Linux setup
# Run from the project root:  ./setup.sh
#
# This script picks a usable Python (>= 3.10) matching the host architecture,
# then delegates to install.py — which handles the venv, deps, and smoke test.
# Pass extra args through:  ./setup.sh --yes --no-playwright

set -e

# Color helpers
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}App Review Analyzer — setup${NC}"
echo

# Force UTF-8 in the child Python process — protects against UnicodeEncodeError
# in LC_ALL=C / minimal-container environments when printing non-ASCII review text
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# ──────────────────────────────────────────────────────────────────
# Pick a usable Python (>= 3.10, matching arch)
# ──────────────────────────────────────────────────────────────────
MIN_MAJOR=3
MIN_MINOR=10
SYSTEM_ARCH=$(uname -m)   # arm64 on Apple Silicon, x86_64 elsewhere

pick_python() {
    # Candidate Pythons, ordered newest-first
    local candidates=(
        python3.13 python3.12 python3.11 python3.10
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
        /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11
        /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11
        python3
    )
    local py
    for py in "${candidates[@]}"; do
        # For PATH names, command -v resolves them; for absolute paths, check -x directly
        if [[ "$py" == /* ]]; then
            [[ -x "$py" ]] || continue
        else
            command -v "$py" &>/dev/null || continue
        fi
        # Probe version + arch in one call, check against minimums
        if SYSTEM_ARCH_PROBE="$SYSTEM_ARCH" MIN_MAJOR_PROBE="$MIN_MAJOR" MIN_MINOR_PROBE="$MIN_MINOR" \
           "$py" -c '
import os, sys, platform
ok = sys.version_info >= (int(os.environ["MIN_MAJOR_PROBE"]), int(os.environ["MIN_MINOR_PROBE"]))
if sys.platform == "darwin" and os.environ["SYSTEM_ARCH_PROBE"] == "arm64" and platform.machine() != "arm64":
    ok = False
sys.exit(0 if ok else 1)
' 2>/dev/null; then
            echo "$py"
            return 0
        fi
    done
    return 1
}

PY=$(pick_python) || true
if [[ -z "$PY" ]]; then
    echo -e "${RED}ERROR:${NC} Could not find a usable Python."
    echo "  Need Python ${MIN_MAJOR}.${MIN_MINOR}+ matching this machine's architecture (${SYSTEM_ARCH})."
    echo "  Install from https://www.python.org/downloads/ (universal2 installer)"
    echo "  or:  brew install python@3.13"
    exit 1
fi

PY_VERSION=$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
PY_ARCH=$("$PY" -c 'import platform; print(platform.machine())')
echo -e "→ Using Python ${PY_VERSION} (${PY_ARCH})  at  ${PY}"

# ──────────────────────────────────────────────────────────────────
# Delegate to install.py — handles venv (with health check), deps, smoke test
# ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
INSTALL_PY="${SCRIPT_DIR}/install.py"

if [[ ! -f "$INSTALL_PY" ]]; then
    echo -e "${RED}ERROR:${NC} install.py not found at $INSTALL_PY"
    exit 1
fi

# Forward all extra args to install.py
exec "$PY" "$INSTALL_PY" "$@"
