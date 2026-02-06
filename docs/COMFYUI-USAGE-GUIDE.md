# ComfyUI + Wan2.2-Animate-14B Usage Guide

## ✅ Installation Complete!

You now have a fully functional Wan2.2-Animate-14B setup optimized for your RTX 5070 Ti (16GB VRAM).

**Installed Models:**
- **Main Model:** Wan2.2-Animate-14B-Q4_K_S.gguf (9.9 GB) - Quantized for 16GB VRAM
- **Text Encoder:** umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.3 GB) - FP8 quantized
- **VAE:** wan2.2_vae.safetensors (1.4 GB)

---

## 🚀 How to Start ComfyUI

### Quick Launch
```bash
bash ~/launch-comfyui.sh
```

### Manual Launch
```bash
cd ~/comfyui-wan/ComfyUI
source ../venv/bin/activate
python main.py
```

**Then open:** http://localhost:8188

---

## 📖 First Time Setup in ComfyUI

### Step 1: Load Example Workflow

1. Open ComfyUI in your browser (http://localhost:8188)
2. Click **"Load"** button (top right)
3. Navigate to: `user/default/workflows/wan_animate_example.json`
4. Click to load the workflow

### Step 2: Understanding the Workflow

ComfyUI uses a **node-based interface**. Each box (node) performs a specific task:

- **Load Video** node: Upload your input video
- **Load Image** node: Upload your character image
- **GGUF Model Loader** node: Loads the quantized model
- **Text Encoder** node: Encodes text/prompts
- **VAE** node: Encodes/decodes images
- **Sampler** node: Generates the animation
- **Save Video** node: Exports the result

### Step 3: Upload Your Content

1. Find the **"Load Video"** node
2. Click **"Upload Video"** button
3. Select your video file (MP4, MOV, etc.)

4. Find the **"Load Image"** node
5. Click **"Upload Image"** button
6. Select your character image (PNG, JPG, etc.)

### Step 4: Generate Animation

1. Click **"Queue Prompt"** button (top right)
2. Wait for generation to complete (3-10 minutes for 10-second video)
3. Progress shows in the bottom status bar
4. Output video saves automatically

---

## 🎬 Animation Modes

### Animation Mode (Character Mimics Motion)
**Use Case:** Make a character image mimic motion from a video

**Inputs:**
- **Video:** Person dancing, gesturing, moving (any human motion)
- **Image:** Character you want to animate

**Output:** Character performs the same motions as the person in the video

**Example:**
- Video: Someone doing a dance
- Image: Anime character
- Result: Anime character doing the same dance

### Replacement Mode (Replace Character in Video)
**Use Case:** Replace a character in a video with a different character

**Inputs:**
- **Video:** Video containing a character
- **Image:** New character to replace with

**Output:** Original character replaced with your image

**Example:**
- Video: Cartoon character walking
- Image: Your custom character design
- Result: Your character walking instead

---

## 💡 Tips for Best Results

### Video Guidelines
✅ **DO:**
- Use short videos (5-15 seconds)
- Use 720p or lower resolution
- Use well-lit, clear videos
- Use videos with visible motion/expressions
- Use stable, non-shaky footage

❌ **AVOID:**
- Very long videos (>30 seconds) - may run out of memory
- 4K or very high resolution
- Dark or low-quality videos
- Videos with occlusions or camera cuts

### Image Guidelines
✅ **DO:**
- Use clear, well-lit character images
- Use images with visible face and body
- Use PNG with transparent background (optional but helps)
- Use consistent art style

❌ **AVOID:**
- Blurry or low-quality images
- Images with complex backgrounds (unless that's intended)
- Very small images (<256px)

### Performance Optimization
- **First run** will be slower (model loading into VRAM)
- **Close other GPU applications** (games, browsers with GPU accel)
- **Monitor GPU usage** with `nvidia-smi`
- If you get **out of memory errors**, reduce video resolution or length

---

## 🛠️ ComfyUI Interface Tips

### Navigation
- **Left Click + Drag:** Pan canvas
- **Mouse Wheel:** Zoom in/out
- **Right Click:** Context menu (add nodes, etc.)

### Node Operations
- **Click and drag** title bar to move nodes
- **Click inputs/outputs** (dots on sides) to connect nodes
- **Right-click node** → "Remove" to delete
- **Right-click canvas** → "Add Node" to add new nodes

### Saving Workflows
1. Click **"Save"** button (top)
2. Name your workflow
3. Workflows save to `user/default/workflows/`

---

## 📁 File Locations

| Item | Location |
|------|----------|
| ComfyUI | `~/comfyui-wan/ComfyUI/` |
| Models (GGUF) | `~/comfyui-wan/ComfyUI/models/unet/` |
| Text Encoders | `~/comfyui-wan/ComfyUI/models/text_encoders/` |
| VAE | `~/comfyui-wan/ComfyUI/models/vae/` |
| Workflows | `~/comfyui-wan/ComfyUI/user/default/workflows/` |
| Output Videos | `~/comfyui-wan/ComfyUI/output/` |
| Launcher Script | `~/launch-comfyui.sh` |

---

## 🔧 Troubleshooting

### ComfyUI won't start
```bash
# Check if virtual environment is activated
cd ~/comfyui-wan/ComfyUI
source ../venv/bin/activate
python main.py
```

### "CUDA out of memory" error
1. Reduce video resolution
2. Shorten video length
3. Close other GPU applications
4. Restart ComfyUI

### Model not found
Check models are in correct locations:
```bash
ls ~/comfyui-wan/ComfyUI/models/unet/*.gguf
ls ~/comfyui-wan/ComfyUI/models/text_encoders/*.safetensors
ls ~/comfyui-wan/ComfyUI/models/vae/*.safetensors
```

### Workflow doesn't work
1. Make sure all nodes are connected (no broken connections)
2. Check that video/image are uploaded
3. Look at error messages in terminal
4. Try reloading the example workflow

### Slow generation
- **Expected:** 3-10 minutes for 10-second video on RTX 5070 Ti
- Q4_K_S quantization is slower than full FP16 but enables running on 16GB
- First run is always slower (model loading)

---

## 📊 Performance Expectations

| Video Length | Resolution | Expected Time (Q4_K_S) |
|-------------|------------|------------------------|
| 5 seconds | 480p | 1-3 minutes |
| 10 seconds | 720p | 3-8 minutes |
| 15 seconds | 720p | 5-12 minutes |
| 30 seconds | 720p | 10-20 minutes |

---

## 🎓 Learning Resources

### ComfyUI Basics
- **Official Wiki:** https://github.com/comfyanonymous/ComfyUI/wiki
- **Community Discord:** https://discord.gg/comfyui
- **YouTube Tutorials:** Search "ComfyUI tutorial"

### Wan2.2-Animate
- **Model Card:** https://huggingface.co/QuantStack/Wan2.2-Animate-14B-GGUF
- **Official Repo:** https://github.com/Wan-Video/Wan2.2
- **Documentation:** https://huggingface.co/Wan-AI/Wan2.2-Animate-14B

---

## 🆘 Getting Help

1. **Check terminal output** for error messages
2. **Check GPU memory:** `nvidia-smi`
3. **ComfyUI logs:** Check terminal where ComfyUI is running
4. **Community help:**
   - ComfyUI GitHub Issues: https://github.com/comfyanonymous/ComfyUI/issues
   - Wan2.2 GitHub Issues: https://github.com/Wan-Video/Wan2.2/issues

---

## 🎉 You're Ready!

Run this to get started:
```bash
bash ~/launch-comfyui.sh
```

Then open **http://localhost:8188** and load the example workflow!

Happy animating! 🎬
