# Quick Reference: Model Download SOP

**When adding ANY tool that needs model downloads:**

## 1️⃣ Copy Template

```bash
cp scripts/template_download_models.sh scripts/download_TOOLNAME_models.sh
```

## 2️⃣ Customize (Replace ALL_CAPS)

```bash
TOOL_NAME="mytool"
VENV_PATH="/srv/containers/edq/venv_mytool"
MODELS_DIR="/srv/containers/edq/models/mytool"
HF_REPO="org/repo-name"
ESTIMATED_SIZE="10 GB"
```

## 3️⃣ Make Executable

```bash
chmod +x scripts/download_TOOLNAME_models.sh
```

## 4️⃣ Test Download

```bash
bash scripts/download_TOOLNAME_models.sh
```

## 5️⃣ Add Check to Launch Script

```bash
# In scripts/start_TOOLNAME.sh
MODELS_DIR="/srv/containers/edq/models/TOOLNAME"

if [ ! -d "$MODELS_DIR" ] || [ -z "$(ls -A $MODELS_DIR)" ]; then
    echo "❌ Models not found. Run: bash scripts/download_TOOLNAME_models.sh"
    exit 1
fi
```

## 6️⃣ Document

- Add to tool's README/setup guide
- Update [docs/model-downloads-guide.md](model-downloads-guide.md)
- Mention in dragonsuite.json features

---

**Full SOP:** [docs/sop-model-downloads.md](sop-model-downloads.md)
**Template:** [scripts/template_download_models.sh](../scripts/template_download_models.sh)
**Examples:** [scripts/download_new_models.sh](../scripts/download_new_models.sh)
