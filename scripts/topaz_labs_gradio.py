#!/usr/bin/env python3
"""
Topaz Labs Gradio Interface
Provides web UI for Topaz Labs AI image enhancement APIs
"""

import os
import gradio as gr
import httpx
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import time

# Load API key
load_dotenv('/srv/containers/edq/.env')
API_KEY = os.getenv('TOPAZ_API_KEY')
TOPAZ_API_BASE = "https://api.topazlabs.com"  # Correct base URL (no /v1)
OUTPUT_DIR = Path.home() / "ai_generated" / "topaz-labs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Check API key
if not API_KEY:
    print("❌ TOPAZ_API_KEY not found in .env file")
    print("Get your API key from: https://developer.topazlabs.com/")
    exit(1)


async def check_credits():
    """Check available Topaz Labs credits."""
    headers = {
        "X-API-Key": API_KEY  # Correct auth header
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{TOPAZ_API_BASE}/image/v1/user/credits",  # Correct endpoint
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            # API returns: {"credits": number}
            credits = data.get("credits", "N/A")

            return f"""📊 **Topaz Labs Credits**

✓ Available Credits: {credits}
"""
        except httpx.HTTPStatusError as e:
            return f"❌ HTTP Error {e.response.status_code}: {e.response.text}"
        except Exception as e:
            return f"❌ Error checking credits: {str(e)}"


async def process_image(operation, image_path, mode="v2", scale=2, strength=0.5):
    """Process image with Topaz Labs API using multipart/form-data."""
    if not image_path:
        return None, "❌ Please upload an image first"

    headers = {
        "X-API-Key": API_KEY  # Correct auth header (no Content-Type for multipart)
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            # Map operations to models
            # Enhance: V2 Standard or Recover 3 Generative
            # Note: Currently only enhance is available in the actual API
            if operation == "enhance":
                # For synchronous processing (V2 Standard model)
                if mode == "v2":
                    endpoint = "/image/v1/enhance"

                    # Read image file
                    with open(image_path, "rb") as f:
                        files = {"image": (Path(image_path).name, f, "image/png")}
                        data = {
                            "model": "V2 Standard",
                            "scale": str(scale)
                        }

                        response = await client.post(
                            f"{TOPAZ_API_BASE}{endpoint}",
                            headers=headers,
                            files=files,
                            data=data
                        )
                        response.raise_for_status()
                        result = response.json()

                    # Download result
                    output_url = result.get("output_url")
                    if not output_url:
                        return None, f"❌ No output URL in response: {result}"

                    download_response = await client.get(output_url)
                    download_response.raise_for_status()

                    # Save to output directory
                    timestamp = int(time.time())
                    output_path = OUTPUT_DIR / f"topaz_enhance_v2_{timestamp}.png"
                    output_path.write_bytes(download_response.content)

                    return str(output_path), f"""✓ **Enhanced with V2 Standard!**

Output: {output_path.name}
Scale: {scale}x
"""

                # For async processing (Recover 3 Generative model)
                elif mode == "recover3":
                    endpoint = "/image/v1/enhance-gen/async"

                    # Read image file
                    with open(image_path, "rb") as f:
                        files = {"image": (Path(image_path).name, f, "image/png")}
                        data = {
                            "model": "Recover 3 Generative",
                            "scale": str(scale)
                        }

                        response = await client.post(
                            f"{TOPAZ_API_BASE}{endpoint}",
                            headers=headers,
                            files=files,
                            data=data
                        )
                        response.raise_for_status()
                        result = response.json()

                    # Get job ID and poll for completion
                    job_id = result.get("job_id")
                    if not job_id:
                        return None, f"❌ No job_id in response: {result}"

                    # Poll for completion
                    max_wait = 300
                    poll_interval = 5
                    elapsed = 0

                    status_endpoint = f"/image/v1/enhance-gen/async/{job_id}"

                    while elapsed < max_wait:
                        status_response = await client.get(
                            f"{TOPAZ_API_BASE}{status_endpoint}",
                            headers=headers
                        )
                        status_response.raise_for_status()
                        status_data = status_response.json()

                        status = status_data.get("status")

                        if status == "completed":
                            output_url = status_data.get("output_url")

                            # Download result
                            download_response = await client.get(output_url)
                            download_response.raise_for_status()

                            # Save to output directory
                            timestamp = int(time.time())
                            output_path = OUTPUT_DIR / f"topaz_enhance_recover3_{timestamp}.png"
                            output_path.write_bytes(download_response.content)

                            return str(output_path), f"""✓ **Enhanced with Recover 3!**

Output: {output_path.name}
Scale: {scale}x
Processing time: ~{elapsed}s
"""

                        elif status == "failed":
                            error = status_data.get("error", "Unknown error")
                            return None, f"❌ Processing failed: {error}"

                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval

                    return None, f"❌ Processing timed out after {max_wait}s"

                else:
                    return None, f"❌ Unknown mode: {mode}. Use 'v2' or 'recover3'"

            else:
                return None, f"""❌ Operation '{operation}' not yet implemented.

The Topaz Labs API currently supports:
- enhance (v2): V2 Standard model (synchronous, fast)
- enhance (recover3): Recover 3 Generative model (async, slower, better quality)

Other operations (sharpen, denoise, restore) may be available in future API versions."""

        except httpx.HTTPStatusError as e:
            return None, f"❌ HTTP Error {e.response.status_code}: {e.response.text}"
        except Exception as e:
            return None, f"❌ Error: {str(e)}"


def create_ui():
    """Create Gradio interface with dark mode support."""

    # Use dark theme by default (per web development standards)
    with gr.Blocks(
        title="Topaz Labs AI Enhancement",
        theme=gr.themes.Soft(primary_hue="blue").set(
            body_background_fill="*neutral_950",
            body_background_fill_dark="*neutral_950",
            button_primary_background_fill="*primary_600",
            button_primary_background_fill_hover="*primary_700",
        )
    ) as app:
        gr.Markdown("""
        # ⭐ Topaz Labs AI Enhancement

        Professional image upscaling and restoration using Topaz Labs AI

        **Models Available:**
        - **V2 Standard**: Fast synchronous processing (recommended for most images)
        - **Recover 3 Generative**: Async processing with advanced restoration (best quality)

        **Note:** Supports 2x, 3x, or 4x upscaling. Direct file upload - no external URLs needed!
        """)

        # Credits section
        with gr.Row():
            credits_btn = gr.Button("📊 Check Credits", size="sm")
            credits_output = gr.Markdown()

        credits_btn.click(
            fn=lambda: asyncio.run(check_credits()),
            outputs=credits_output
        )

        gr.Markdown("---")

        # Main interface
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Input")
                enhance_input = gr.Image(type="filepath", label="Upload Image")

                gr.Markdown("### Settings")
                enhance_mode = gr.Radio(
                    choices=["v2", "recover3"],
                    value="v2",
                    label="Enhancement Model",
                    info="v2=V2 Standard (fast), recover3=Recover 3 Generative (best quality)"
                )
                enhance_scale = gr.Slider(
                    minimum=2,
                    maximum=4,
                    value=2,
                    step=1,
                    label="Upscale Factor",
                    info="2x, 3x, or 4x resolution increase"
                )
                enhance_btn = gr.Button("🚀 Enhance Image", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### Output")
                enhance_output = gr.Image(label="Enhanced Image", show_download_button=True)
                enhance_status = gr.Markdown()

        enhance_btn.click(
            fn=lambda img, mode, scale: asyncio.run(
                process_image("enhance", img, mode=mode, scale=scale)
            ),
            inputs=[enhance_input, enhance_mode, enhance_scale],
            outputs=[enhance_output, enhance_status]
        )

        gr.Markdown(f"""
        ---
        **Output Directory:** `{OUTPUT_DIR}`

        **Get your API key:** [developer.topazlabs.com](https://developer.topazlabs.com/)
        """)

    return app


if __name__ == "__main__":
    print("🎨 Starting Topaz Labs Gradio Interface...")
    print(f"📍 Output directory: {OUTPUT_DIR}")

    app = create_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=8019,
        share=False
    )
