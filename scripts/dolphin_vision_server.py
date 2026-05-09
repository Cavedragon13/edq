#!/usr/bin/env python3
"""
Dolphin Vision 7B - Native UI Server
Port: 8025

Preserves the existing /analyze JSON endpoint (used by Dragonsight 4).

API:
  GET  /              → serves dolphin_vision.html
  POST /api/query     → multipart: file (image), prompt, temperature, max_tokens
                      → returns JSON: {response, model_loaded}
  POST /analyze       → JSON: {image_base64, prompt} → {result}  [Dragonsight compat]
"""

import base64
import warnings
from io import BytesIO
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request
from PIL import Image as PILImage

warnings.filterwarnings('ignore')

MODEL_PATH = "/srv/containers/edq/models/dolphin-vision-7b"
VISION_TOWER_PATH = "/srv/containers/edq/models/siglip-so400m-patch14-384"
MEDIA_DIR  = Path("/srv/containers/edq/media")

model     = None
tokenizer = None


def patch_transformers_cache_compat():
    from transformers.cache_utils import DynamicCache

    if not hasattr(DynamicCache, "seen_tokens"):
        DynamicCache.seen_tokens = property(lambda self: self.get_seq_length())
    if not hasattr(DynamicCache, "get_max_length"):
        DynamicCache.get_max_length = DynamicCache.get_max_cache_shape


def load_model():
    global model, tokenizer
    if model is not None:
        return True, "ready"
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    import transformers
    transformers.logging.set_verbosity_error()
    transformers.logging.disable_progress_bar()
    patch_transformers_cache_compat()
    print("Loading Dolphin Vision 7B…")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH, trust_remote_code=True, local_files_only=True
        )
        config = AutoConfig.from_pretrained(
            MODEL_PATH, trust_remote_code=True, local_files_only=True
        )
        if getattr(config, "pad_token_id", None) is None:
            config.pad_token_id = tokenizer.pad_token_id or tokenizer.eos_token_id
        if Path(VISION_TOWER_PATH).exists():
            config.mm_vision_tower = VISION_TOWER_PATH
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH, torch_dtype=torch.float16,
            device_map='auto', trust_remote_code=True, local_files_only=True,
            config=config
        )
        print("Model loaded.")
        return True, "loaded"
    except Exception as e:
        return False, str(e)


def run_inference(image: PILImage.Image, prompt: str,
                  temperature: float = 0.1, max_tokens: int = 512) -> str:
    ok, msg = load_model()
    if not ok:
        return f"Error loading model: {msg}"
    try:
        messages = [{"role": "user", "content": f'<image>\n{prompt}'}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        chunks = [tokenizer(c).input_ids for c in text.split('<image>')]
        input_ids = torch.tensor(chunks[0] + [-200] + chunks[1], dtype=torch.long).unsqueeze(0)
        device = next(model.parameters()).device
        input_ids = input_ids.to(device)
        image_tensor = model.process_images([image.convert('RGB')], model.config).to(dtype=model.dtype)
        with torch.no_grad():
            out = model.generate(
                input_ids, images=image_tensor,
                max_new_tokens=int(max_tokens),
                temperature=float(temperature),
                do_sample=temperature > 0.01, use_cache=True
            )[0]
        return tokenizer.decode(out[input_ids.shape[1]:], skip_special_tokens=True).strip()
    except Exception as e:
        import traceback
        return f"Error: {e}\n\n{traceback.format_exc()}"


app = FastAPI(title="Dolphin Vision 7B")


@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "dolphin_vision.html")


@app.post("/api/query")
async def api_query(
    file:        UploadFile = File(...),
    prompt:      str        = Form("Describe this image in detail."),
    temperature: float      = Form(0.1),
    max_tokens:  int        = Form(512),
):
    raw   = await file.read()
    image = PILImage.open(BytesIO(raw)).convert("RGB")
    result = run_inference(image, prompt, temperature, max_tokens)
    return JSONResponse({"response": result, "model": "dolphin-vision-7b"})


# ── Dragonsight 4 compatibility endpoint (unchanged) ──────────────
@app.post("/analyze")
async def analyze_compat(request: Request):
    try:
        data      = await request.json()
        img_b64   = data.get("image_base64", "")
        prompt    = data.get("prompt", "Describe this image in detail.")
        if not img_b64:
            return JSONResponse({"error": "No image_base64 provided"}, status_code=400)
        image = PILImage.open(BytesIO(base64.b64decode(img_b64))).convert("RGB")
        result = run_inference(image, prompt, temperature=0.1, max_tokens=512)
        return JSONResponse({"result": result})
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


if __name__ == "__main__":
    port = 8025
    print(f"🐬 Dolphin Vision 7B (native UI) → http://0.0.0.0:{port}")
    print(f"   /analyze preserved for Dragonsight 4 integration")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
