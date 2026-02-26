#!/bin/bash
set -e

BASE_DIR="/srv/containers/edq"
VENV_DIR="$BASE_DIR/venv_dragonsuite"

echo "🐉 Dragonclawd — Personal AI Agent"
echo "   Telegram bot powered by Claude Haiku + Dragonsuite"
echo ""

# Activate venv (shared with dragonsuite)
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ venv_dragonsuite not found at $VENV_DIR"
    echo "   Run: bash scripts/start_dragonsuite.sh first to create it"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Ensure Telegram/Anthropic packages are present
pip install --quiet "python-telegram-bot[all]" anthropic gradio_client python-dotenv mcp 2>/dev/null

# Check .env has required tokens
source "$BASE_DIR/.env" 2>/dev/null || true

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  TELEGRAM_BOT_TOKEN not set in .env"
    echo ""
    echo "   Setup steps:"
    echo "   1. Open Telegram → message @BotFather → /newbot"
    echo "   2. Copy the token it gives you"
    echo "   3. Open Telegram → message @userinfobot → note your user ID"
    echo "   4. Edit /srv/containers/edq/.env and add:"
    echo "      TELEGRAM_BOT_TOKEN=<your-token>"
    echo "      TELEGRAM_ALLOWED_USERS=<your-user-id>"
    echo ""
    echo "   Then re-run this script."
    exit 1
fi

echo "   Token: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "   Allowed users: ${TELEGRAM_ALLOWED_USERS:-'(not set!)'}"
echo ""

cd "$BASE_DIR"
exec python scripts/dragonclawd_server.py
