#!/bin/bash
# AI Toolkit (Ostris) LoRA Trainer Launcher
# Port: 8012

set -e

cd /srv/containers/edq

echo "AI Toolkit - LoRA Training Suite"
echo "================================="
echo ""

# Check if venv exists
if [ ! -d "venv_ai_toolkit" ]; then
    echo "ERROR: venv_ai_toolkit not found. Run setup first."
    exit 1
fi

source venv_ai_toolkit/bin/activate

# Check torch
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}')"

echo ""
echo "Starting AI Toolkit UI on port 8012..."
echo "Web UI: http://192.168.7.226:8012"
echo ""

cd projects/ai-toolkit

# Run with custom port (override the default share=True behavior)
python -c "
import sys
sys.path.insert(0, '.')
from flux_train_ui import demo
demo.launch(
    server_name='0.0.0.0',
    server_port=8012,
    share=False,
    show_error=True
)
"
