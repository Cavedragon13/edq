#!/usr/bin/env python3
"""
Topaz Labs MCP Server (Updated for Real API)
Provides access to Topaz Labs AI image/video enhancement APIs

Based on actual API documentation from developer.topazlabs.com
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

# Topaz Labs API configuration (CORRECTED)
TOPAZ_API_BASE = "https://api.topazlabs.com"

server = Server("topaz-labs")

# Logging to file (stdout reserved for MCP stdio protocol)
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
logger.info("=" * 50)
logger.info("Topaz Labs MCP Server v1.2.0 starting")
logger.info(f"Log file: {LOG_FILE}")


def get_api_key() -> Optional[str]:
    """Get Topaz Labs API key from environment."""
    return os.getenv("TOPAZ_API_KEY")


def validate_environment() -> bool:
    """Validate environment and log diagnostics."""
    api_key = get_api_key()
    if not api_key:
        logger.error("TOPAZ_API_KEY environment variable not set!")
        logger.error("Get your key from https://topazlabs.com/my-account/")
        return False
    redacted = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
    logger.info(f"TOPAZ_API_KEY found: {redacted}")
    return True


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Topaz Labs tools."""
    return [
        types.Tool(
            name="topaz_enhance_image",
            description="Enhance image quality using Topaz AI (Standard V2 model)",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Local path to the image file to enhance"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["Standard V2", "Recover 3"],
                        "description": "Enhancement model to use",
                        "default": "Standard V2"
                    }
                },
                "required": ["image_path"]
            }
        ),
        types.Tool(
            name="topaz_enhance_async",
            description="Enhance image with generative AI (async processing, supports Recover 3)",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Local path to the image file to enhance"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["Recover 3"],
                        "description": "Generative enhancement model",
                        "default": "Recover 3"
                    }
                },
                "required": ["image_path"]
            }
        ),
        types.Tool(
            name="topaz_check_credits",
            description="Check remaining Topaz Labs API credits (if credits endpoint exists)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """Handle tool execution."""
    logger.info(f"Tool called: {name}")
    api_key = get_api_key()
    if not api_key:
        logger.error("Tool call failed: TOPAZ_API_KEY not set")
        raise ValueError(
            "TOPAZ_API_KEY environment variable not set. "
            "Get your API key from https://topazlabs.com/my-account/"
        )

    headers = {
        "X-API-Key": api_key,
        "accept": "image/jpeg"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        if name == "topaz_check_credits":
            # Note: Credits endpoint may not exist, trying common patterns
            try:
                response = await client.get(
                    f"{TOPAZ_API_BASE}/account/credits",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                return [
                    types.TextContent(
                        type="text",
                        text=f"Topaz Labs Credits: {data}"
                    )
                ]
            except httpx.HTTPStatusError as e:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Credits endpoint not available (status {e.response.status_code}). "
                             "Check your account at https://topazlabs.com/my-account/"
                    )
                ]

        elif name == "topaz_enhance_image":
            # Standard synchronous enhancement
            image_path = Path(arguments["image_path"])
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            model = arguments.get("model", "Standard V2")

            with open(image_path, "rb") as f:
                files = {"image": f}
                data = {"model": model}

                response = await client.post(
                    f"{TOPAZ_API_BASE}/image/v1/enhance",
                    headers=headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()

                # Save enhanced image
                output_path = image_path.parent / f"{image_path.stem}_enhanced.jpg"
                output_path.write_bytes(response.content)

                return [
                    types.TextContent(
                        type="text",
                        text=f"✓ Image enhanced successfully!\n"
                             f"Model: {model}\n"
                             f"Output: {output_path}\n"
                             f"Size: {len(response.content) / 1024:.1f} KB"
                    )
                ]

        elif name == "topaz_enhance_async":
            # Async generative enhancement (for Recover 3, etc.)
            image_path = Path(arguments["image_path"])
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            model = arguments.get("model", "Recover 3")

            with open(image_path, "rb") as f:
                files = {"image": f}
                data = {"model": model}

                # Submit async request
                response = await client.post(
                    f"{TOPAZ_API_BASE}/image/v1/enhance-gen/async",
                    headers=headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()

                request_id = result.get("requestId") or result.get("request_id")

                # Poll for completion
                max_wait = 300  # 5 minutes
                poll_interval = 5
                elapsed = 0

                while elapsed < max_wait:
                    status_response = await client.get(
                        f"{TOPAZ_API_BASE}/image/v1/request/{request_id}",
                        headers=headers
                    )
                    status_response.raise_for_status()
                    status_data = status_response.json()

                    state = status_data.get("status")

                    if state == "complete" or state == "completed":
                        # Download result
                        download_url = status_data.get("download_url") or status_data.get("downloadUrl")

                        download_response = await client.get(download_url, headers=headers)
                        download_response.raise_for_status()

                        # Save enhanced image
                        output_path = image_path.parent / f"{image_path.stem}_{model.replace(' ', '_')}_enhanced.jpg"
                        output_path.write_bytes(download_response.content)

                        return [
                            types.TextContent(
                                type="text",
                                text=f"✓ Async enhancement completed!\n"
                                     f"Model: {model}\n"
                                     f"Request ID: {request_id}\n"
                                     f"Output: {output_path}\n"
                                     f"Size: {len(download_response.content) / 1024:.1f} KB"
                            )
                        ]

                    elif state == "failed" or state == "error":
                        error = status_data.get("error", "Unknown error")
                        raise RuntimeError(f"Processing failed: {error}")

                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                raise TimeoutError(f"Processing timed out after {max_wait}s")

        else:
            raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    logger.info("Starting MCP stdio server...")
    validate_environment()

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("Server ready - waiting for requests")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="topaz-labs",
                    server_version="1.2.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
