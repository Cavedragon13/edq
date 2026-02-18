#!/usr/bin/env python3
"""
Dolphin Vision 7B - Gradio Interface
Uncensored vision-language model for unrestricted image Q&A.

Model: cognitivecomputations/dolphin-vision-7b (BunnyQwen2 architecture)
Based on Qwen2-7B with custom vision integration.
"""

import gradio as gr
import torch
import warnings
from pathlib import Path
from datetime import datetime
import os
import base64
from io import BytesIO
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Suppress noisy warnings
warnings.filterwarnings('ignore')

MODEL_PATH = "/srv/containers/edq/models/dolphin-vision-7b"
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/dolphin-vision"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Global model state (lazy loading)
model = None
tokenizer = None

def load_model():
    """Load model on first use."""
    global model, tokenizer
    if model is not None:
        return True, "Model already loaded"

    from transformers import AutoModelForCausalLM, AutoTokenizer
    import transformers
    transformers.logging.set_verbosity_error()
    transformers.logging.disable_progress_bar()

    print("Loading Dolphin Vision 7B from local path...")
    print(f"  Path: {MODEL_PATH}")

    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16,
            device_map='auto',
            trust_remote_code=True,
            local_files_only=True
        )
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            trust_remote_code=True,
            local_files_only=True
        )
        # LlavaQwen2Config doesn't define pad_token_id - set it explicitly
        if not hasattr(model.config, 'pad_token_id') or model.config.pad_token_id is None:
            model.config.pad_token_id = tokenizer.eos_token_id
        print("Model loaded successfully!")
        return True, "Model loaded"
    except Exception as e:
        return False, f"Error loading model: {e}"


def analyze_image(image, prompt, temperature, max_tokens):
    """Analyze an image with Dolphin Vision."""
    from PIL import Image as PILImage

    if image is None:
        return "Please upload an image first."
    if not prompt or not prompt.strip():
        return "Please enter a prompt."

    # Load model if not already loaded
    ok, msg = load_model()
    if not ok:
        return f"Failed to load model: {msg}"

    try:
        # Prepare chat message with image token
        messages = [
            {"role": "user", "content": f'<image>\n{prompt}'}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Tokenize - split on <image> placeholder
        text_chunks = [tokenizer(chunk).input_ids for chunk in text.split('<image>')]
        input_ids = torch.tensor(
            text_chunks[0] + [-200] + text_chunks[1],
            dtype=torch.long
        ).unsqueeze(0)

        # Move to model device
        device = next(model.parameters()).device
        input_ids = input_ids.to(device)

        # Process image
        if not isinstance(image, PILImage.Image):
            image = PILImage.fromarray(image).convert('RGB')
        else:
            image = image.convert('RGB')
        image_tensor = model.process_images([image], model.config).to(dtype=model.dtype)

        # Generate response
        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                images=image_tensor,
                max_new_tokens=int(max_tokens),
                temperature=float(temperature),
                do_sample=temperature > 0.01,
                use_cache=True
            )[0]

        response = tokenizer.decode(
            output_ids[input_ids.shape[1]:],
            skip_special_tokens=True
        ).strip()

        return response

    except Exception as e:
        import traceback
        return f"Error: {e}\n\n{traceback.format_exc()}"


EXAMPLE_PROMPTS = [
    "Describe this image in detail.",
    "What is happening in this image?",
    "Extract all text visible in this image.",
    "What objects do you see? List them.",
    "Describe the mood and atmosphere of this image.",
    "Are there any people? Describe them.",
    "What style or aesthetic does this image have?",
    "Analyze this image critically.",
]

# Gradio UI
CUSTOM_CSS = """
body { background-color: #1e1e1e; }
.gradio-container { background-color: #1e1e1e !important; }
"""

with gr.Blocks(title="Dolphin Vision 7B") as demo:
    gr.Markdown(
        """
        # 🐬 Dolphin Vision 7B
        **Uncensored vision-language model** - no content filtering, unrestricted image analysis.
        *Based on Qwen2-7B with custom vision integration. First query loads model (~15GB VRAM).*
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(
                label="Upload Image",
                type="pil",
                sources=["upload", "clipboard"],
                height=400
            )
            prompt_input = gr.Textbox(
                label="Prompt",
                placeholder="Describe this image in detail...",
                lines=3,
                value="Describe this image in detail."
            )

            with gr.Row():
                temperature = gr.Slider(
                    label="Temperature",
                    minimum=0.01,
                    maximum=2.0,
                    value=0.1,
                    step=0.05
                )
                max_tokens = gr.Slider(
                    label="Max Tokens",
                    minimum=100,
                    maximum=2000,
                    value=512,
                    step=50
                )

            analyze_btn = gr.Button("🔍 Analyze Image", variant="primary", size="lg")

            gr.Markdown("**Example prompts:**")
            example_btns = []
            for ep in EXAMPLE_PROMPTS[:4]:
                btn = gr.Button(ep, size="sm", variant="secondary")
                example_btns.append((btn, ep))

        with gr.Column(scale=1):
            output_text = gr.Textbox(
                label="Response",
                lines=20,
                interactive=False,
                placeholder="Response will appear here after analysis..."
            )

    # Wire up events
    analyze_btn.click(
        fn=analyze_image,
        inputs=[image_input, prompt_input, temperature, max_tokens],
        outputs=[output_text],
        show_progress=True
    )

    prompt_input.submit(
        fn=analyze_image,
        inputs=[image_input, prompt_input, temperature, max_tokens],
        outputs=[output_text],
        show_progress=True
    )

    for btn, ep_text in example_btns:
        btn.click(fn=lambda t=ep_text: t, outputs=[prompt_input])


# FastAPI app with Gradio mounted + /analyze JSON endpoint
fastapi_app = FastAPI()


@fastapi_app.post("/analyze")
async def analyze_api(request: Request):
    """JSON API endpoint for Dragonsight 4 integration.
    Accepts: {"image_base64": "...", "prompt": "..."}
    Returns: {"result": "..."}
    """
    from PIL import Image as PILImage
    try:
        data = await request.json()
        image_b64 = data.get("image_base64", "")
        prompt = data.get("prompt", "Describe this image in detail.")

        if not image_b64:
            return JSONResponse({"error": "No image_base64 provided"}, status_code=400)

        # Decode base64 image
        img_bytes = base64.b64decode(image_b64)
        image = PILImage.open(BytesIO(img_bytes)).convert("RGB")

        result = analyze_image(image, prompt, temperature=0.1, max_tokens=512)
        return JSONResponse({"result": result})

    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


fastapi_app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("Dolphin Vision 7B")
    print(f"Model path: {MODEL_PATH}")
    print(f"Output dir: {OUTPUT_DIR}")
    print("=" * 50)
    print("")
    print("Endpoints:")
    print("  /         - Gradio web UI")
    print("  /analyze  - JSON API (for Dragonsight integration)")
    print("")
    print("NOTE: Model loads on first query (~30s, uses ~12GB VRAM)")
    print("")

    uvicorn.run(fastapi_app, host="0.0.0.0", port=8025)
