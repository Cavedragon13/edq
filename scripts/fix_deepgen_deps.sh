#!/bin/bash
# DeepGen dependency resolution workaround
# This downgrades transformers if needed

set -e

echo "🔧 DeepGen Dependency Fix"
echo ""

source /srv/containers/edq/venv_deepgen/bin/activate

echo "Current status:"
pip list | grep -E "transformers|xtuner|mmengine|bitsandbytes"

echo ""
echo "Options:"
echo "  1. Try with current versions (transformers 5.1.0) - RECOMMENDED FIRST"
echo "  2. Downgrade transformers to 4.48.0 (may break other tools)"
echo ""
read -p "Choose option (1 or 2): " choice

if [ "$choice" = "2" ]; then
    echo ""
    echo "⚠️  Downgrading transformers to 4.48.0..."
    echo "This may break compatibility with other installed packages."
    pip install transformers==4.48.0 --force-reinstall
    echo "✓ Downgrade complete"
else
    echo ""
    echo "✓ Keeping current versions - testing recommended"
    echo ""
    echo "If DeepGen fails to load, run this script again and choose option 2."
fi

echo ""
echo "Final versions:"
pip list | grep -E "transformers|xtuner|mmengine|bitsandbytes"

echo ""
echo "✓ Ready to test DeepGen!"
echo "Launch with: bash scripts/start_deepgen.sh"
