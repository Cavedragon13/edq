#!/bin/bash
# Qwen3 Audiobook Converter - Document to Audiobook
# Port 8014, LAN accessible
# Requires Qwen3-TTS running on port 8009
set -e
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh

SERVICE_NAME="Qwen3 Audiobook"
PORT=8014
VENV="venv_qwen3_tts"

service_header "$SERVICE_NAME" "$PORT"

# Check if Qwen3-TTS backend is running
if curl -s --head http://localhost:8009 > /dev/null 2>&1; then
    echo "✓ Qwen3-TTS service: running on port 8009"
else
    echo "⚠️  Qwen3-TTS service: NOT RUNNING"
    echo ""
    echo "   Please start Qwen3-TTS first:"
    echo "   bash scripts/start_qwen3_tts.sh"
    echo ""
    echo "   The audiobook converter requires the TTS service as a backend."
fi
echo ""

clear_port "$PORT"
activate_venv "$VENV"

# Install additional dependencies if needed
if ! python -c "import gradio_client" 2>/dev/null; then
    echo "Installing audiobook converter dependencies..."
    pip install gradio_client
fi
if ! python -c "import PyPDF2" 2>/dev/null; then
    pip install PyPDF2
fi
if ! python -c "import ebooklib" 2>/dev/null; then
    pip install ebooklib beautifulsoup4
fi
if ! python -c "import docx" 2>/dev/null; then
    pip install python-docx
fi
if ! python -c "import pydub" 2>/dev/null; then
    pip install pydub
fi

echo "🚀 Starting $SERVICE_NAME..."
if pgrep -f "qwen3_audiobook_gradio.py" > /dev/null; then
    echo "✓ Already running on port $PORT"
else
    nohup python scripts/qwen3_audiobook_gradio.py > /tmp/qwen3_audiobook.log 2>&1 &
    echo "⏳ Waiting for service..."
    if wait_for_port "$PORT" 30; then
        echo "✅ $SERVICE_NAME ready at http://192.168.7.226:$PORT"
    else
        echo "❌ Service did not start in time — check /tmp/qwen3_audiobook.log"
        tail -10 /tmp/qwen3_audiobook.log
        exit 1
    fi
fi
