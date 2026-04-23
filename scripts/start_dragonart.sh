#!/bin/bash
# DragonArt Studio Launcher
# Gemini 3 Pro AI Image Editor + Veo Video
# Port: 8015

set -e

# Load nvm to ensure Node 20+ is used (required by @google/genai >= 1.33)
export NVM_DIR="/home/edq/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
nvm use 20 --silent 2>/dev/null || true

cd /srv/containers/edq

echo ""
echo "DragonArt Studio"
echo "================"
echo "Gemini 3 Pro AI Image Editor + Veo 3.1 Video"
echo ""

OUTPUT_DIR="$HOME/ai_generated/dragonart-studio"
PROJECT_DIR="/srv/containers/edq/projects/dragonart-studio"
SCRIPT_DIR="/srv/containers/edq/scripts"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is required for building."
    echo "Install with: sudo apt install nodejs npm"
    exit 1
fi

# Check if API keys are set
if [ -f "/srv/containers/edq/.env" ]; then
    GOOGLE_KEY=$(grep -E "^GOOGLE_API_KEY=" /srv/containers/edq/.env | cut -d'=' -f2-)
    OPENAI_KEY=$(grep -E "^OPENAI_API_KEY=" /srv/containers/edq/.env | cut -d'=' -f2-)
    if [ -z "$GOOGLE_KEY" ]; then
        echo "WARNING: GOOGLE_API_KEY not found in /srv/containers/edq/.env"
        echo "DragonArt Studio requires a Google API key for Gemini models."
    fi
    if [ -z "$OPENAI_KEY" ]; then
        echo "NOTE: OPENAI_API_KEY not found - gpt-image-2 will not be available."
    fi
else
    echo "WARNING: /srv/containers/edq/.env not found"
fi

# Use venv_dragonsuite Python for the server — has openai and google-genai SDKs
PYTHON_BIN="/srv/containers/edq/venv_dragonsuite/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    echo "ERROR: venv_dragonsuite not found at $PYTHON_BIN"
    echo "Run: python3 -m venv /srv/containers/edq/venv_dragonsuite && /srv/containers/edq/venv_dragonsuite/bin/pip install openai google-genai"
    exit 1
fi
echo "Checking server-side SDK dependencies..."
"$PYTHON_BIN" -c "import openai; print('  openai:', __import__('openai').__version__)" 2>/dev/null \
    || echo "  WARNING: openai not found in venv_voxtral — gpt-image-2 will return 503"
"$PYTHON_BIN" -c "from google import genai; print('  google-genai: ok')" 2>/dev/null \
    || echo "  WARNING: google-genai not found in venv_voxtral — Gemini proxy will return 503"

# Build if dist doesn't exist or is older than source
BUILD_NEEDED=false
if [ ! -d "$PROJECT_DIR/dist" ]; then
    BUILD_NEEDED=true
    echo "Build directory not found. Building..."
elif [ "$PROJECT_DIR/App.tsx" -nt "$PROJECT_DIR/dist/index.html" ] 2>/dev/null; then
    BUILD_NEEDED=true
    echo "Source files changed. Rebuilding..."
fi

if [ "$BUILD_NEEDED" = true ]; then
    echo ""
    echo "Building React app..."
    cd "$PROJECT_DIR"

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi

    # Create .env.local — only GEMINI_API_KEY goes here (used as a presence check
    # in the browser bundle). OPENAI_API_KEY stays server-side only (proxy pattern).
    echo "# DragonArt Studio — browser-safe config only" > .env.local
    if [ -n "$GOOGLE_KEY" ]; then
        echo "GEMINI_API_KEY=$GOOGLE_KEY" >> .env.local
        echo "Google API key configured"
    fi

    # Build production version
    npm run build

    cd /srv/containers/edq
    echo ""
    echo "Build complete."
fi

# Check if already running
if pgrep -f "dragonart_server.py" > /dev/null; then
    echo "DragonArt Studio already running on port 8015"
    echo ""
    echo "   Local:  http://localhost:8015"
    echo "   LAN:    http://192.168.7.226:8015"
    echo "   Output: $OUTPUT_DIR"
    exit 0
fi

# Start the server
echo ""
echo "Starting server..."
"$PYTHON_BIN" "$SCRIPT_DIR/dragonart_server.py"
