#!/usr/bin/env bash
# App Review Analyzer — setup
# Run from the project root:  ./setup.sh

set -e

# Color helpers
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}App Review Analyzer — setup${NC}"
echo

# Python version check
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR:${NC} Python 3 is required but not found."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "→ Python ${PY_VERSION} detected"

# Determine pip install flags
PIP_FLAGS=""
if [[ "$1" == "--user" ]]; then
    PIP_FLAGS="--user"
elif [[ "$1" == "--system" ]]; then
    PIP_FLAGS="--break-system-packages"
fi

# Core deps
echo -e "→ Installing core dependencies..."
python3 -m pip install $PIP_FLAGS --quiet \
    google-play-scraper requests pandas openpyxl

# Optional deps
echo
echo -e "${YELLOW}Optional dependencies:${NC}"
echo

read -p "  Install playwright for PDF output? [Y/n] " -n 1 -r REPLY
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    python3 -m pip install $PIP_FLAGS --quiet playwright
    echo "  → Installing Chromium for headless rendering..."
    python3 -m playwright install chromium --with-deps 2>/dev/null || \
        python3 -m playwright install chromium
    echo "  → PDF generation ready"
else
    echo "  → Skipped (PDF generation will not work)"
fi

read -p "  Install anthropic for LLM-powered theme tagging? [y/N] " -n 1 -r REPLY
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -m pip install $PIP_FLAGS --quiet anthropic
    echo "  → Anthropic SDK installed. Set ANTHROPIC_API_KEY before using --llm-tagging"
else
    echo "  → Skipped (keyword tagging still works fine)"
fi

# Smoke test
echo
echo -e "${GREEN}→ Running smoke test...${NC}"
python3 -c "
from scripts.theme_tagger import load_taxonomy, list_available_taxonomies
tax = load_taxonomy('general')
print(f'  Loaded \"{tax[\"label\"]}\": {len(tax[\"negative_themes\"])} negative + {len(tax[\"positive_themes\"])} positive themes')
print(f'  Available taxonomies: {len(list_available_taxonomies())}')
"

echo
echo -e "${GREEN}✓ Setup complete.${NC}"
echo
echo "Try it:"
echo
echo "  python3 -m scripts.run_pipeline \\"
echo "      --play com.duolingo \\"
echo "      --appstore 570060128 \\"
echo "      --formats html,excel,csv \\"
echo "      --output ./output/duolingo"
echo
echo "Or in Claude:  \"Analyze reviews for Duolingo on both stores\""
echo
