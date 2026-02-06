#!/usr/bin/env python3
"""
Florence2 Vision Service - Local, uncensored, technical image description
Runs Microsoft's Florence-2 model for literal, anatomical image analysis
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
import io
import base64
import uvicorn
from typing import Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Florence2 Vision Service", version="1.0.0")

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model cache
MODEL_CACHE = {
    "model": None,
    "processor": None,
    "device": None
}

def load_model():
    """Load Florence2 model into memory"""
    if MODEL_CACHE["model"] is not None:
        return MODEL_CACHE["model"], MODEL_CACHE["processor"], MODEL_CACHE["device"]

    logger.info("Loading Florence-2-large model...")

    # Determine device
    if torch.cuda.is_available():
        device = "cuda"
        torch_dtype = torch.float16
        logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
    else:
        device = "cpu"
        torch_dtype = torch.float32
        logger.warning("CUDA not available, using CPU (will be slower)")

    # Load model and processor
    model_name = "microsoft/Florence-2-large"

    try:
        processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            trust_remote_code=True,
            attn_implementation="eager"  # Use eager attention to avoid SDPA compatibility issues
        ).to(device)

        # Cache for reuse
        MODEL_CACHE["model"] = model
        MODEL_CACHE["processor"] = processor
        MODEL_CACHE["device"] = device

        logger.info(f"✓ Florence-2-large loaded on {device}")
        return model, processor, device

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

def run_florence_task(image: Image.Image, task: str, text_input: Optional[str] = None):
    """Run a Florence2 task on an image"""
    model, processor, device = load_model()

    # Prepare inputs
    if text_input:
        prompt = f"{task} {text_input}"
    else:
        prompt = task

    inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)

    # Generate
    with torch.no_grad():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
            do_sample=False
        )

    # Decode output
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed_answer = processor.post_process_generation(
        generated_text,
        task=task,
        image_size=(image.width, image.height)
    )

    return parsed_answer

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "service": "Florence2 Vision Service",
        "status": "ready",
        "model": "microsoft/Florence-2-large",
        "device": MODEL_CACHE.get("device", "not loaded"),
        "available_tasks": [
            "DETAILED_CAPTION",
            "MORE_DETAILED_CAPTION",
            "CAPTION",
            "OCR",
            "REGION_PROPOSAL"
        ]
    }

@app.get("/health")
def health():
    """Health check"""
    return {"status": "healthy", "model_loaded": MODEL_CACHE["model"] is not None}

@app.post("/analyze")
async def analyze_image(
    image_file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = None,
    task: str = "MORE_DETAILED_CAPTION"
):
    """
    Analyze an image using Florence2

    Supports either file upload or base64 encoded image

    Task types:
    - MORE_DETAILED_CAPTION: Very detailed description
    - DETAILED_CAPTION: Detailed description
    - CAPTION: Concise caption
    - OCR: Extract text
    - REGION_PROPOSAL: Detect objects/regions
    """
    try:
        # Load image from file or base64
        if image_file:
            image_data = await image_file.read()
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        elif image_base64:
            # Handle data URL format
            if "base64," in image_base64:
                image_base64 = image_base64.split("base64,")[1]
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        else:
            raise HTTPException(status_code=400, detail="No image provided")

        # Validate task
        task_map = {
            "DETAILED_CAPTION": "<DETAILED_CAPTION>",
            "MORE_DETAILED_CAPTION": "<MORE_DETAILED_CAPTION>",
            "CAPTION": "<CAPTION>",
            "OCR": "<OCR>",
            "REGION_PROPOSAL": "<REGION_PROPOSAL>"
        }

        florence_task = task_map.get(task.upper(), "<MORE_DETAILED_CAPTION>")

        # Run inference
        logger.info(f"Running task: {florence_task}")
        result = run_florence_task(image, florence_task)

        # Extract text from result
        # Florence2 returns dict with task as key
        if florence_task in result:
            output = result[florence_task]
        else:
            output = str(result)

        return {
            "task": task,
            "result": output,
            "image_size": {"width": image.width, "height": image.height}
        }

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch_analyze")
async def batch_analyze(
    image_base64: str,
    tasks: list[str] = ["MORE_DETAILED_CAPTION", "CAPTION", "OCR"]
):
    """
    Run multiple Florence2 tasks on a single image
    Used by Dragonsight for parallel analysis
    """
    try:
        # Decode image
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        task_map = {
            "DETAILED_CAPTION": "<DETAILED_CAPTION>",
            "MORE_DETAILED_CAPTION": "<MORE_DETAILED_CAPTION>",
            "CAPTION": "<CAPTION>",
            "OCR": "<OCR>",
            "REGION_PROPOSAL": "<REGION_PROPOSAL>"
        }

        results = {}
        for task in tasks:
            florence_task = task_map.get(task.upper(), "<MORE_DETAILED_CAPTION>")
            logger.info(f"Running batch task: {florence_task}")
            result = run_florence_task(image, florence_task)

            # Extract result
            if florence_task in result:
                output = result[florence_task]
            else:
                output = str(result)

            results[task] = output

        return {
            "results": results,
            "image_size": {"width": image.width, "height": image.height}
        }

    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Florence2 Vision Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", default=5000, type=int, help="Port to bind to")
    parser.add_argument("--preload", action="store_true", help="Preload model on startup")

    args = parser.parse_args()

    # Preload model if requested
    if args.preload:
        logger.info("Preloading model...")
        load_model()

    logger.info(f"Starting Florence2 service on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
