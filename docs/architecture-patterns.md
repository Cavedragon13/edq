# Architecture Patterns

## Python Script Structure

- Most scripts use Gradio for web interfaces
- Scripts typically support multiple backends (Ollama, LM Studio)
- Virtual environments stored alongside projects
- Configuration via constants at top of files
- Subprocess calls for external commands with timeout handling

---

## Server Launching Pattern

1. Start server with `subprocess.run()` or `shell.run`
2. Capture URL via regex on stdout
3. Set local variable for UI to display
4. Use `daemon: true` to keep process alive

---

## Video Processing Pattern

For vision models that don't support video:

1. Extract keyframes using OpenCV (`cv2.VideoCapture`)
2. Process each frame individually
3. Combine descriptions/results
4. Clean up temporary frame files

---

## CORS Proxy Pattern (for Local APIs)

When frontend needs to call a local service that doesn't support CORS (e.g., Ollama):

### Problem

Browser blocks cross-port requests (8080 → 11434) due to CORS policy.

### Solution

Proxy through the frontend server to stay same-origin:

```
Frontend (8080) → Server (8080) → Local API (11434)
```

### Implementation

See `scripts/dragonsight_server.py`:

- Use `BaseHTTPRequestHandler` (not `SimpleHTTPRequestHandler` - breaks POST override)
- Add `Access-Control-Allow-Origin: *` to all responses
- Handle OPTIONS for CORS preflight
- Use `SO_REUSEADDR` to avoid binding errors on restart
- Set adequate timeout (300s for model inference)

### Key Rules

- **ALWAYS** use `127.0.0.1` for local services, never external IPs
- **DO NOT** use `window.location.hostname` (returns external IP from LAN)
- Test with: `curl -X POST http://127.0.0.1:8080/api/proxy/endpoint`

---

## Memory Optimization for Large Models (16GB VRAM)

### Environment Variable (REQUIRED)

Add before python command in all GPU launcher scripts:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

Note: `expandable_segments:True` is superior to the older `max_split_size_mb:512` setting.

### CPU Offloading Strategy (for diffusers pipelines)

Choose based on VRAM requirements:

```python
# Option 1: Model CPU offload (best speed/memory balance)
# Moves entire models to GPU one at a time
pipeline.enable_model_cpu_offload()

# Option 2: Sequential CPU offload (maximum memory savings, slower)
# Moves individual layers to GPU during forward pass
pipeline.enable_sequential_cpu_offload()

# CRITICAL: Never call .to("cuda") before offloading methods!
```

### VAE Optimizations

Always enable for image generation:

```python
if hasattr(pipeline, 'vae'):
    pipeline.vae.enable_slicing()  # Batch memory reduction
    pipeline.vae.enable_tiling()   # High-res support
```

### Memory Cleanup Pattern

```python
import gc
import torch

def clear_gpu_memory():
    """Clear GPU memory between operations."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# Call before inference if VRAM is tight
clear_gpu_memory()
```

### Service VRAM Requirements

| Service            | VRAM    | Offload Strategy      |
| ------------------ | ------- | --------------------- |
| Qwen-Image-Layered | 14-16GB | Sequential (required) |
| Z-Image Base       | 13-14GB | Sequential            |
| HeartMuLa          | ~12GB   | Model                 |
| Fish Speech        | ~12GB   | Model                 |
| Hunyuan3D (shape)  | ~6GB    | Model                 |
| SAM 2.1            | ~6GB    | Model                 |
| Real-ESRGAN        | ~4GB    | None needed           |
| LivePortrait       | ~6GB    | Model                 |

### General Guidelines

- Only run ONE GPU-heavy service at a time
- Use 640px resolution when possible (vs 1024px)
- Limit video length for video generation
- Add user-facing warnings about hardware limits in UI

---

## React State Management Pattern (Dragonart Studio)

### CRITICAL: useCallback Dependency Arrays

When creating callbacks that use state variables, **ALL** state variables must be in the dependency array:

```typescript
const handleGenerateClick = useCallback(async () => {
  const prompt = getPromptForMode({
    mode: editMode,
    sport: sportType,
    console: consoleType,
    magazineGenre: magazineGenre,
    nonSportsCardStyle: nonSportsCardStyle, // ← Must be in deps!
  });
  // ...
}, [editMode, sportType, consoleType, magazineGenre, nonSportsCardStyle]);
//  ↑ ALL state variables used in callback MUST be here ↑
```

### Common Bug: Missing state in dependency array causes stale closures

- **Symptom:** Dropdown selection takes 2-3 clicks to apply
- **Cause:** Callback captures old state value, not current
- **Fix:** Add missing state variable to dependency array

### Debugging Pattern

```typescript
const handleGenerateClick = useCallback(async () => {
  console.log("Current state:", { editMode, sportType, nonSportsCardStyle });
  // ↑ Verify all values are current, not stale
}, [editMode, sportType, nonSportsCardStyle]);
```

### State Flow for Dropdowns

```
User changes dropdown
    ↓
onChange={(e) => setState(e.target.value)}
    ↓
Parent state updates (App.tsx)
    ↓
Callback recreated with new state (due to dependency array)
    ↓
Next Generate click uses current state ✓
```

**Without dependency:** Callback keeps old state until something else causes re-render ✗
