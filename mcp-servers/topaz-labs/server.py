#!/usr/bin/env python3
"""
Topaz Labs MCP Server v2.0
Full coverage of the Topaz Labs Image Enhancement API.

Endpoints and models verified against the live API (2026-03-03).
See README.md for model descriptions and usage examples.
"""

import os
import sys
import asyncio
import logging
import httpx
from pathlib import Path
from typing import Optional
from datetime import datetime
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

TOPAZ_API_BASE = "https://api.topazlabs.com"

# Verified endpoint routing (model → endpoint path)
# Tested against live API 2026-03-03
SYNC_ENHANCE_MODELS = [
    # Core enhancement
    "Standard V2",
    "High Fidelity V2",
    "Low Resolution V2",
    "Natural Enhance",
    "Detail",
    # Style / creative
    "Portrait",
    "Wildlife",
    "Redefine",
    "Reimagine",
    "Wonder 2",
    # Bloom variants
    "Bloom",
    "Bloom Precision",
    "Bloom Realism",
    # Restoration
    "Colorize",
    "Dust-Scratch V2",
    # Sharpening (via enhance endpoint)
    "Auto Sharpen",
]

SHARPEN_MODELS = ["Standard", "Strong"]
DENOISE_MODELS = ["Normal", "Strong"]
LIGHTING_MODELS = ["Adjust V2"]

# Async generative models (polling required, longer processing)
ASYNC_MODELS = [
    "Recover 3",
    "Bloom",
    "Bloom Precision",
    "Bloom Realism",
    "Reimagine",
    "Wonder 2",
    "Redefine",
]

ALL_IMAGE_MODELS = (
    SYNC_ENHANCE_MODELS
    + [f"Sharpen: {m}" for m in SHARPEN_MODELS]
    + [f"Denoise: {m}" for m in DENOISE_MODELS]
    + [f"Lighting: {m}" for m in LIGHTING_MODELS]
)

server = Server("topaz-labs")

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"topaz_mcp_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ]
)
logger = logging.getLogger(__name__)
logger.info("Topaz Labs MCP Server v2.0 starting")


def get_api_key() -> Optional[str]:
    return os.getenv("TOPAZ_API_KEY")


def resolve_endpoint_and_model(model: str) -> tuple[str, str]:
    """Map user-facing model name to (endpoint_path, api_model_name)."""
    if model.startswith("Sharpen: "):
        return "/image/v1/sharpen", model[len("Sharpen: "):]
    if model.startswith("Denoise: "):
        return "/image/v1/denoise", model[len("Denoise: "):]
    if model.startswith("Lighting: "):
        return "/image/v1/lighting", model[len("Lighting: "):]
    return "/image/v1/enhance", model


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="topaz_enhance_image",
            description=(
                "Enhance an image using Topaz Labs AI. Supports upscaling, sharpening, "
                "denoising, colorizing, creative reimagining, and restoration. "
                "Results are saved next to the source file with a model-name suffix."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to the source image (JPEG, PNG, or TIFF)"
                    },
                    "model": {
                        "type": "string",
                        "enum": ALL_IMAGE_MODELS,
                        "description": (
                            "Enhancement model. "
                            "Standard V2/High Fidelity V2/Low Resolution V2 = general upscaling. "
                            "Portrait/Wildlife = subject-specific enhancement. "
                            "Bloom/Reimagine/Wonder 2/Redefine = creative/generative. "
                            "Colorize = add color to B&W. "
                            "Dust-Scratch V2 = restore old photos. "
                            "Sharpen: Standard/Strong = sharpening. "
                            "Denoise: Normal/Strong = noise removal. "
                            "Lighting: Adjust V2 = lighting/exposure correction."
                        ),
                        "default": "Standard V2"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory. Defaults to same directory as input."
                    }
                },
                "required": ["image_path"]
            }
        ),
        types.Tool(
            name="topaz_enhance_generative",
            description=(
                "Enhance an image using Topaz generative AI (async processing). "
                "Higher quality than standard enhancement but takes 1-5 minutes. "
                "Best for: Recover 3 (restoration), Bloom variants (creative), "
                "Reimagine/Wonder 2/Redefine (AI reimagining). "
                "Polls until complete and saves result automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to the source image (JPEG, PNG, or TIFF)"
                    },
                    "model": {
                        "type": "string",
                        "enum": ASYNC_MODELS,
                        "description": (
                            "Recover 3 = restore damaged/old photos. "
                            "Bloom/Bloom Precision/Bloom Realism = creative enhancement. "
                            "Reimagine = AI reimagination. "
                            "Wonder 2 = generative enhancement. "
                            "Redefine = AI redefine."
                        ),
                        "default": "Recover 3"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory. Defaults to same directory as input."
                    }
                },
                "required": ["image_path"]
            }
        ),
        types.Tool(
            name="topaz_check_credits",
            description="Check remaining Topaz Labs API credits and account status.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    logger.info(f"Tool called: {name} args={arguments}")
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "TOPAZ_API_KEY not set. Get your key from https://developer.topazlabs.com/"
        )

    headers = {"X-API-Key": api_key, "accept": "image/jpeg"}

    async with httpx.AsyncClient(timeout=300.0) as client:

        if name == "topaz_check_credits":
            try:
                response = await client.get(
                    f"{TOPAZ_API_BASE}/account/credits",
                    headers=headers
                )
                response.raise_for_status()
                return [types.TextContent(type="text", text=f"Credits: {response.json()}")]
            except httpx.HTTPStatusError as e:
                return [types.TextContent(
                    type="text",
                    text=f"Credits endpoint returned {e.response.status_code}. "
                         "Check your account at https://topazlabs.com/my-account/"
                )]

        elif name == "topaz_enhance_image":
            image_path = Path(arguments["image_path"])
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            model = arguments.get("model", "Standard V2")
            endpoint, api_model = resolve_endpoint_and_model(model)

            output_dir = Path(arguments["output_dir"]) if arguments.get("output_dir") else image_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            suffix = model.replace(": ", "_").replace(" ", "_")
            output_path = output_dir / f"{image_path.stem}_{suffix}.jpg"

            logger.info(f"Enhancing {image_path} with model={api_model} via {endpoint}")

            with open(image_path, "rb") as f:
                response = await client.post(
                    f"{TOPAZ_API_BASE}{endpoint}",
                    headers=headers,
                    files={"image": f},
                    data={"model": api_model}
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"API error {response.status_code}: {response.text[:200]}"
                )

            output_path.write_bytes(response.content)
            size_kb = len(response.content) / 1024

            return [types.TextContent(
                type="text",
                text=f"✓ Enhanced successfully\nModel: {model}\nOutput: {output_path}\nSize: {size_kb:.1f} KB"
            )]

        elif name == "topaz_enhance_generative":
            image_path = Path(arguments["image_path"])
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            model = arguments.get("model", "Recover 3")

            output_dir = Path(arguments["output_dir"]) if arguments.get("output_dir") else image_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            suffix = model.replace(" ", "_")
            output_path = output_dir / f"{image_path.stem}_{suffix}.jpg"

            logger.info(f"Submitting generative job: {image_path} model={model}")

            # Submit
            with open(image_path, "rb") as f:
                response = await client.post(
                    f"{TOPAZ_API_BASE}/image/v1/enhance-gen/async",
                    headers=headers,
                    files={"image": f},
                    data={"model": model}
                )
            response.raise_for_status()
            result = response.json()
            request_id = result.get("requestId") or result.get("request_id")
            logger.info(f"Job submitted: requestId={request_id}")

            # Poll
            max_wait, poll_interval, elapsed = 300, 5, 0
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                status_resp = await client.get(
                    f"{TOPAZ_API_BASE}/image/v1/request/{request_id}",
                    headers=headers
                )
                status_resp.raise_for_status()
                status = status_resp.json()
                state = status.get("status")
                logger.info(f"Poll {elapsed}s: status={state}")

                if state in ("complete", "completed"):
                    download_url = status.get("download_url") or status.get("downloadUrl")
                    dl_resp = await client.get(download_url, headers=headers)
                    dl_resp.raise_for_status()
                    output_path.write_bytes(dl_resp.content)
                    size_kb = len(dl_resp.content) / 1024
                    return [types.TextContent(
                        type="text",
                        text=(f"✓ Generative enhancement complete\n"
                              f"Model: {model}\nRequest ID: {request_id}\n"
                              f"Output: {output_path}\nSize: {size_kb:.1f} KB\n"
                              f"Time: {elapsed}s")
                    )]

                if state in ("failed", "error"):
                    raise RuntimeError(f"Job failed: {status.get('error', 'unknown error')}")

            raise TimeoutError(f"Job timed out after {max_wait}s (requestId={request_id})")

        else:
            raise ValueError(f"Unknown tool: {name}")


async def main():
    api_key = get_api_key()
    if not api_key:
        logger.warning("TOPAZ_API_KEY not set — tools will fail until key is provided")
    else:
        logger.info(f"API key loaded: {api_key[:4]}...{api_key[-4:]}")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server ready")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="topaz-labs",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
