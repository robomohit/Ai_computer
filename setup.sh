#!/usr/bin/env bash
set -e

echo ""
echo " ============================================"
echo "   AI Computer - Setup"
echo " ============================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Using Python $PYTHON_VERSION"

echo ""
echo "[1/3] Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "[2/3] Installing Playwright browser (Chromium)..."
playwright install chromium || echo "[WARN] Playwright install failed — browser mode won't work. Retry: playwright install chromium"

echo ""
echo "[3/3] Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from .env.example"
    echo "  >> Open .env and add at least one API key before launching."
else
    echo "  .env already exists, skipping."
fi

echo ""
echo " ============================================"
echo "   Setup complete!"
echo ""
echo "   Next steps:"
echo "     1. Edit .env and add your API key"
echo "        (free: get OPENROUTER_API_KEY at openrouter.ai)"
echo "     2. Run: ./start.sh"
echo " ============================================"
echo ""
