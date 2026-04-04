#!/bin/bash
# Dragonclawd — Personal AI Agent (Telegram bot)
# No port  |  venv_dragonsuite
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Dragonclawd"

service_header "$SERVICE_NAME" ""

activate_venv "venv_dragonsuite"

# Ensure required packages are present
pip install --quiet "python-telegram-bot[all]" anthropic gradio_client python-dotenv mcp 2>/dev/null

# Check .env for required tokens
source /srv/containers/edq/.env 2>/dev/null || true

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

echo "🚀 Starting $SERVICE_NAME..."
exec python scripts/dragonclawd_server.py
