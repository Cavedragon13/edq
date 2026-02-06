#!/bin/bash
# Qwen3 Audiobook Converter - Document to Audiobook
# Port 8014, LAN accessible
# Requires Qwen3-TTS running on port 8009

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv_qwen3_tts"  # Share venv with Qwen3-TTS

echo "Qwen3 Audiobook Converter"
echo "========================="
echo "Convert Documents to Audiobooks with AI Voice"
echo ""

# Check if Qwen3-TTS is running
check_tts_service() {
    if curl -s --head http://localhost:8009 > /dev/null 2>&1; then
        echo "Qwen3-TTS service: Running on port 8009"
        return 0
    else
        echo "Qwen3-TTS service: NOT RUNNING"
        echo ""
        echo "Please start Qwen3-TTS first:"
        echo "  bash scripts/start_qwen3_tts.sh"
        echo ""
        echo "The audiobook converter requires the TTS service as a backend."
        return 1
    fi
}

check_tts_service || true
echo ""

# Check if shared venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Qwen3-TTS venv not found at $VENV_DIR"
    echo "Please install Qwen3-TTS first:"
    echo "  bash scripts/start_qwen3_tts.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

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

echo ""
echo "Starting Qwen3 Audiobook Converter..."
echo "Local:   http://localhost:8014"
echo "LAN:     http://192.168.7.226:8014"
echo ""
echo "Supported formats:"
echo "  - PDF (text-based)"
echo "  - EPUB (e-books)"
echo "  - DOCX/DOC (Word documents)"
echo "  - TXT (plain text)"
echo ""
echo "Output directory: ~/ai_generated/qwen3-audiobook/"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_DIR"
python scripts/qwen3_audiobook_gradio.py
