#!/bin/bash
set -e

BASE_DIR="/srv/containers/edq"
PROJECT_DIR="$BASE_DIR/projects/deep-cut-generator"
VENV_DIR="$BASE_DIR/venv_deep_cut_generator"
OUTPUT_DIR="/home/edq/ai_generated/deep-cut-generator"

cd "$PROJECT_DIR"

if [ -f "$BASE_DIR/.env" ]; then
  source "$BASE_DIR/.env"
fi

mkdir -p "$OUTPUT_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "Installing/updating dependencies..."
pip install -q -r requirements.txt

echo ""
echo "Deep Cut Generator"
echo "  http://192.168.7.226:8055"
echo ""

exec python server.py
