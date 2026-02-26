# SOP: Model Download Scripts

**Standard Operating Procedure for AI tools requiring model downloads**

## Principle

**NEVER make the first run of a tool wait for downloads.**

Instead:

1. Create a standalone download script that can run during idle time
2. Make the script resumable and idempotent
3. Document the script in the tool's setup instructions

## Implementation Pattern

### 1. Create Download Script

**Naming convention:** `scripts/download_<toolname>_models.sh`

**Template:**

```bash
#!/bin/bash
# Download models for <ToolName>
# Safe to run multiple times - resumable and idempotent

set -e

MODELS_DIR="/srv/containers/edq/models/<toolname>"
mkdir -p "$MODELS_DIR"

echo "🚀 Downloading <ToolName> models..."
echo "This is safe to interrupt (Ctrl+C) and resume later."

# Activate appropriate venv
source /srv/containers/edq/venv_<toolname>/bin/activate

# Use Python API for reliability
python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models/<toolname>")

print("📦 Downloading <org>/<repo>...")
try:
    snapshot_download(
        repo_id="<org>/<repo>",
        local_dir=str(models_dir),
        ignore_patterns=["*.git*", "README.md"]
    )
    print("✓ Models downloaded to:", models_dir)
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume - partial downloads are saved.")
PYEOF

deactivate

echo ""
echo "✅ Download complete!"
echo "Models location: $MODELS_DIR"
echo "Next: Update model paths in scripts/<toolname>_gradio.py"
```

### 2. Make Script Executable

```bash
chmod +x scripts/download_<toolname>_models.sh
```

### 3. Update Tool Documentation

Add to tool's launch script or README:

````markdown
## Setup

### Download Models (One-Time)

Run this during idle time before first use:

```bash
bash scripts/download_<toolname>_models.sh
```
````

Safe to interrupt and resume. Downloads ~XXX GB.

### Launch Tool

Once models are downloaded:

```bash
bash scripts/start_<toolname>.sh
```

````

### 4. Add to Dragonsuite Config

Include download instructions in the tool's features or description:

```json
{
  "id": "toolname",
  "name": "Tool Name",
  "description": "Tool description",
  "features": [
    "Feature 1",
    "Feature 2",
    "⚙️ Setup: download_toolname_models.sh"
  ]
}
````

## Best Practices

### Use Python API, Not CLI

**Good:**

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="org/repo",
    local_dir="/path/to/models"
)
```

**Avoid:**

```bash
huggingface-cli download org/repo  # CLI syntax varies between versions
hf download org/repo                # May not be available
```

### Why Python API?

- ✅ Consistent across huggingface-hub versions
- ✅ Automatic resume on failure
- ✅ Built-in progress bars
- ✅ Checksum validation
- ✅ Rate limiting handling

### Error Handling

Always use try/except and provide resume instructions:

```python
try:
    snapshot_download(...)
    print("✓ Download complete!")
except Exception as e:
    print(f"⚠️  Download failed: {e}")
    print("Run again to resume - partial downloads are saved.")
    exit(1)
```

### Directory Structure

**Standard model location:**

```
/srv/containers/edq/models/
├── <toolname1>/
│   ├── model.safetensors
│   └── config.json
├── <toolname2>/
│   └── checkpoints/
└── shared/              # For models used by multiple tools
    └── common_model/
```

### Multi-Model Tools

If a tool needs multiple models, download all in one script:

```bash
# Download all models for ToolName
python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models/toolname")

# Model 1
print("📦 Downloading main model...")
snapshot_download("org/model1", local_dir=str(models_dir / "main"))

# Model 2
print("📦 Downloading preprocessing model...")
snapshot_download("org/model2", local_dir=str(models_dir / "preprocess"))

# Model 3
print("📦 Downloading upscaler...")
snapshot_download("org/model3", local_dir=str(models_dir / "upscaler"))

print("✓ All models downloaded!")
PYEOF
```

## Examples

### Simple Single-Model Tool

See: [scripts/download_soulxsinger_models.sh](../scripts/download_new_models.sh) (SoulX-Singer section)

### Complex Multi-Model Tool

See: [scripts/download_new_models.sh](../scripts/download_new_models.sh) (JustDubit section)

### Combined Batch Downloader

See: [scripts/download_new_models.sh](../scripts/download_new_models.sh) (downloads for 3 tools)

## Background Download Patterns

### Run in Background (nohup)

```bash
nohup bash scripts/download_<toolname>_models.sh > /tmp/download_<toolname>.log 2>&1 &

# Check progress:
tail -f /tmp/download_<toolname>.log

# Check status:
jobs
```

### Run in tmux/screen

```bash
tmux new -s downloads
bash scripts/download_<toolname>_models.sh
# Ctrl+B, D to detach

# Reattach later:
tmux attach -t downloads
```

### Add to Cron (Scheduled)

```bash
# Download models during off-peak hours
0 2 * * * /srv/containers/edq/scripts/download_<toolname>_models.sh >> /var/log/model_downloads.log 2>&1
```

## Verification Checklist

When adding a new tool, ensure:

- [ ] Download script created: `scripts/download_<toolname>_models.sh`
- [ ] Script is executable (`chmod +x`)
- [ ] Uses Python `snapshot_download()` API
- [ ] Has error handling with resume instructions
- [ ] Documented in tool's README or setup guide
- [ ] Added to `docs/model-downloads-guide.md` if applicable
- [ ] Tested: Can interrupt and resume successfully
- [ ] Tested: Doesn't re-download existing files
- [ ] Launch script checks if models exist before starting

## Anti-Patterns to Avoid

❌ **Don't download on first run:**

```python
# BAD: User waits 30 minutes on first launch
if not models_exist():
    download_models()  # Blocking!
start_app()
```

✅ **Do separate download from launch:**

```python
# GOOD: User runs download script once, tool launches instantly after
if not models_exist():
    print("⚠️  Models not found. Run: bash scripts/download_models.sh")
    exit(1)
start_app()
```

❌ **Don't use CLI commands:**

```bash
hf download org/repo  # Version-dependent syntax
```

✅ **Do use Python API:**

```python
snapshot_download(repo_id="org/repo", local_dir="...")
```

❌ **Don't block main process:**

```python
app.launch()
download_models_async()  # Still blocks event loop
```

✅ **Do check before launch:**

```python
check_models_exist()  # Fast check
app.launch()           # Immediate start
```

## Template Files

### Minimal Download Script

Create at: `scripts/download_TOOLNAME_models.sh`

```bash
#!/bin/bash
set -e

MODELS_DIR="/srv/containers/edq/models/TOOLNAME"
mkdir -p "$MODELS_DIR"

echo "🚀 Downloading TOOLNAME models (~XX GB)..."

source /srv/containers/edq/venv_TOOLNAME/bin/activate

python << 'PYEOF'
from huggingface_hub import snapshot_download
from pathlib import Path

models_dir = Path("/srv/containers/edq/models/TOOLNAME")

print("📦 Downloading ORG/REPO...")
try:
    snapshot_download(
        repo_id="ORG/REPO",
        local_dir=str(models_dir),
        ignore_patterns=["*.git*", "README.md"]
    )
    print(f"✓ Downloaded to: {models_dir}")
except Exception as e:
    print(f"⚠️  Failed: {e}. Run again to resume.")
    exit(1)
PYEOF

echo "✅ Models ready! Launch with: bash scripts/start_TOOLNAME.sh"
```

### Model Check in Launch Script

Add to `scripts/start_TOOLNAME.sh`:

```bash
#!/bin/bash
set -e

MODELS_DIR="/srv/containers/edq/models/TOOLNAME"

# Check if models exist
if [ ! -d "$MODELS_DIR" ] || [ -z "$(ls -A $MODELS_DIR)" ]; then
    echo "❌ Models not found at $MODELS_DIR"
    echo ""
    echo "Download models first:"
    echo "  bash scripts/download_TOOLNAME_models.sh"
    echo ""
    exit 1
fi

echo "✓ Models found"
# Continue with launch...
```

---

## Summary

**The Rule:** Every tool requiring downloads gets a separate download script.

**Benefits:**

- ✅ Better UX (instant launches after setup)
- ✅ Resumable downloads (network-safe)
- ✅ Parallel setup (download multiple tools)
- ✅ Clear separation of concerns
- ✅ Easy troubleshooting

**When to Apply:** ANY time a tool needs to download:

- Model weights (>100MB)
- Checkpoints
- Large assets
- Pre-trained networks

**When NOT to Apply:**

- Small config files (<10MB)
- Dependencies (use requirements.txt)
- Code repositories (use git clone)

---

**Created:** 2026-02-15
**Status:** Active SOP
**Applies to:** All AI tools requiring model downloads
**Related:** [Model Downloads Guide](model-downloads-guide.md)
