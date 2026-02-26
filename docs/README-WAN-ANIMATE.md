# Wan2.2-Animate-14B Setup Guide

Character animation and replacement model optimized for RTX 5070 Ti (16GB VRAM)

## ⚠️ Important Hardware Notice

This is a **14B parameter model** that typically requires:

- **Single GPU**: 45-75GB VRAM (H100/A100)
- **Multi-GPU (8x RTX 4090)**: ~20GB VRAM per GPU

Your **RTX 5070 Ti (16GB VRAM)** is below the recommended specs. You have two options:

### Option 1: Local Installation (May Be Limited)

- Install locally with heavy optimizations
- Processing will be **slow** and may fail for long/high-res videos
- Best for: Short videos (5-10 sec), lower resolutions
- **Recommended for experimentation only**

### Option 2: Use Cloud Service (Recommended)

- Access the official HuggingFace Gradio space
- Runs on powerful cloud GPUs (free)
- Faster and more reliable
- No local installation needed

---

## 🚀 Quick Start

### Cloud Service (Recommended)

Simply run:

```bash
python3 ~/launch-wan-cloud.py
```

This will open the official HuggingFace Gradio space in your browser.

### Local Installation

1. **Run setup script** (requires sudo password):

```bash
bash ~/setup-wan-animate.sh
```

This will:

- Install Python dependencies (pip, venv)
- Install CUDA toolkit (if needed)
- Clone the Wan2.2 repository
- Download model weights (~50GB+)
- Set up optimized environment

**Note**: Download may take 30-60 minutes depending on your internet speed.

2. **Launch Gradio interface**:

```bash
cd ~/wan-animate
source venv/bin/activate
python ~/gradio_app.py
```

The interface will open at: `http://localhost:7860`

---

## 📖 Usage Guide

### Animation Mode

1. Upload a **video with human motion** (e.g., dancing, gestures)
2. Upload a **character image** you want to animate
3. Click "Generate Animation"
4. The character will mimic the motion from the video

### Replacement Mode

1. Upload a **video with a character**
2. Upload a **new character image** to replace it with
3. Click "Generate Animation"
4. The original character will be replaced with your image

### Tips for Best Results

- ✅ Use **short videos** (5-15 seconds) to avoid memory issues
- ✅ **Lower resolution** (720p or less) if you get errors
- ✅ **Clear, well-lit** character images work best
- ✅ **First run** takes longer due to model loading
- ❌ Avoid very long videos (>30 sec) on 16GB VRAM
- ❌ Avoid 4K resolution

---

## 🛠️ Troubleshooting

### Out of Memory Errors

1. Reduce resolution (try 960x540 or 640x360)
2. Use shorter videos (5-10 seconds)
3. Close other GPU applications
4. Enable "Memory Optimizations" in Advanced Settings

### Slow Processing

- This is expected with 16GB VRAM
- Consider using the cloud service instead
- A 10-second video may take 5-15 minutes locally

### Model Not Found

- Ensure setup script completed successfully
- Check that model was downloaded to: `~/wan-animate/models/Wan2.2-Animate-14B`
- Model is ~50GB+, verify you have disk space

### CUDA Errors

- Verify NVIDIA drivers are up to date:
  ```bash
  nvidia-smi
  ```
- Reinstall CUDA toolkit if needed

---

## 📁 File Structure

```
~/
├── setup-wan-animate.sh      # Installation script
├── gradio_app.py              # Local Gradio interface
├── launch-wan-cloud.py        # Cloud launcher
└── wan-animate/               # Created after setup
    ├── venv/                  # Python virtual environment
    ├── Wan2.2/                # Source repository
    └── models/                # Downloaded models (~50GB+)
        └── Wan2.2-Animate-14B/
```

---

## 🔗 Resources

- **Model Card**: https://huggingface.co/Wan-AI/Wan2.2-Animate-14B
- **GitHub**: https://github.com/Wan-Video/Wan2.2
- **Official Website**: https://wan.video/
- **HuggingFace Space**: https://huggingface.co/spaces/Wan-AI/Wan2.2-Animate
- **ModelScope**: https://www.modelscope.cn/studios/Wan-AI/Wan2.2-Animate

---

## 📊 Performance Expectations

| Hardware           | Mode  | Resolution | Expected Time (10s video) |
| ------------------ | ----- | ---------- | ------------------------- |
| RTX 5070 Ti (16GB) | Local | 720p       | 5-15 min (may fail)       |
| RTX 5070 Ti (16GB) | Local | 540p       | 3-10 min                  |
| Cloud (H100/A100)  | Cloud | 1080p      | 30-60 sec                 |

---

## 🆘 Support

If you encounter issues:

1. Check GPU usage: `nvidia-smi`
2. Check logs in terminal
3. Try cloud service instead
4. Open issue on GitHub: https://github.com/Wan-Video/Wan2.2/issues

---

## 📝 License

Apache 2.0 License - See model card for details

## 🙏 Citation

```bibtex
@article{wan2025,
  title={Wan: Open and Advanced Large-Scale Video Generative Models},
  author={Team Wan and others},
  journal={arXiv preprint arXiv:2503.20314},
  year={2025}
}
```
