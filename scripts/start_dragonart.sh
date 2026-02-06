#!/bin/bash
# DragonArt Studio Launcher
# Gemini 3 Pro AI Image Editor + Veo Video
# Port: 8015

set -e

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
        echo "NOTE: OPENAI_API_KEY not found - OpenAI models will not be available."
    fi
else
    echo "WARNING: /srv/containers/edq/.env not found"
fi

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

    # Create .env.local with API keys from central config
    echo "# API keys for DragonArt Studio" > .env.local
    if [ -n "$GOOGLE_KEY" ]; then
        echo "GEMINI_API_KEY=$GOOGLE_KEY" >> .env.local
        echo "Google API key configured"
    fi
    if [ -n "$OPENAI_KEY" ]; then
        echo "OPENAI_API_KEY=$OPENAI_KEY" >> .env.local
        echo "OpenAI API key configured"
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
python3 "$SCRIPT_DIR/dragonart_server.py"
