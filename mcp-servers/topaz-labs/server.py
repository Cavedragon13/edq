#!/usr/bin/env python3
"""
Topaz Labs MCP Server
Provides access to Topaz Labs AI image/video enhancement APIs
"""

import os
import asyncio
import httpx
from typing import Optional
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Topaz Labs API configuration
TOPAZ_API_BASE = "https://api.topazlabs.com/v1"

server = Server("topaz-labs")


def get_api_key() -> Optional[str]:
    """Get Topaz Labs API key from environment."""
    return os.getenv("TOPAZ_API_KEY")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Topaz Labs tools."""
    return [
        types.Tool(
            name="topaz_enhance_image",
            description="Enhance image quality using Topaz AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to enhance"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "generative"],
                        "description": "Enhancement mode (standard or generative)",
                        "default": "standard"
                    },
                    "scale": {
                        "type": "integer",
                        "description": "Upscale factor (1-4x)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 4
                    }
                },
                "required": ["image_url"]
            }
        ),
        types.Tool(
            name="topaz_sharpen_image",
            description="Sharpen image using Topaz AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to sharpen"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "generative"],
                        "description": "Sharpening mode",
                        "default": "standard"
                    }
                },
                "required": ["image_url"]
            }
        ),
        types.Tool(
            name="topaz_denoise_image",
            description="Remove noise from image using Topaz AI",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to denoise"
                    },
                    "strength": {
                        "type": "number",
                        "description": "Denoising strength (0-1)",
                        "default": 0.5,
                        "minimum": 0,
                        "maximum": 1
                    }
                },
                "required": ["image_url"]
            }
        ),
        types.Tool(
            name="topaz_restore_image",
            description="Restore old/damaged images using Topaz AI (generative)",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to restore"
                    }
                },
                "required": ["image_url"]
            }
        ),
        types.Tool(
            name="topaz_check_credits",
            description="Check remaining Topaz Labs API credits",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="topaz_estimate_cost",
            description="Estimate credit cost for an operation",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["enhance", "sharpen", "denoise", "restore"],
                        "description": "Operation to estimate"
                    },
                    "image_width": {
                        "type": "integer",
                        "description": "Image width in pixels"
                    },
                    "image_height": {
                        "type": "integer",
                        "description": "Image height in pixels"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "generative"],
                        "description": "Processing mode",
                        "default": "standard"
                    }
                },
                "required": ["operation", "image_width", "image_height"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """Handle tool execution."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "TOPAZ_API_KEY environment variable not set. "
            "Get your API key from https://developer.topazlabs.com/"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        if name == "topaz_check_credits":
            # Check account credits
            response = await client.get(
                f"{TOPAZ_API_BASE}/credits",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            credits = data.get("credits", {})
            return [
                types.TextContent(
                    type="text",
                    text=f"Topaz Labs Credits:\n"
                         f"Available: {credits.get('available', 'N/A')}\n"
                         f"Total: {credits.get('total', 'N/A')}\n"
                         f"Used: {credits.get('used', 'N/A')}"
                )
            ]

        elif name == "topaz_estimate_cost":
            # Estimate operation cost
            operation = arguments["operation"]
            width = arguments["image_width"]
            height = arguments["image_height"]
            mode = arguments.get("mode", "standard")

            response = await client.post(
                f"{TOPAZ_API_BASE}/estimate",
                headers=headers,
                json={
                    "operation": operation,
                    "width": width,
                    "height": height,
                    "mode": mode
                }
            )
            response.raise_for_status()
            data = response.json()

            return [
                types.TextContent(
                    type="text",
                    text=f"Estimated cost for {operation} ({mode}):\n"
                         f"Credits: {data.get('credits', 'N/A')}\n"
                         f"Processing time: ~{data.get('estimated_time', 'N/A')}s"
                )
            ]

        elif name in ["topaz_enhance_image", "topaz_sharpen_image",
                      "topaz_denoise_image", "topaz_restore_image"]:
            # Map tool names to API endpoints
            endpoint_map = {
                "topaz_enhance_image": "enhance",
                "topaz_sharpen_image": "sharpen",
                "topaz_denoise_image": "denoise",
                "topaz_restore_image": "restore"
            }

            endpoint = endpoint_map[name]
            image_url = arguments["image_url"]

            # Build request payload
            payload = {"input_url": image_url}

            if name == "topaz_enhance_image":
                payload["mode"] = arguments.get("mode", "standard")
                payload["scale"] = arguments.get("scale", 2)
            elif name == "topaz_sharpen_image":
                payload["mode"] = arguments.get("mode", "standard")
            elif name == "topaz_denoise_image":
                payload["strength"] = arguments.get("strength", 0.5)

            # Submit processing request
            response = await client.post(
                f"{TOPAZ_API_BASE}/image/{endpoint}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            task_id = data.get("task_id")

            # Poll for completion (with timeout)
            max_wait = 300  # 5 minutes
            poll_interval = 5
            elapsed = 0

            while elapsed < max_wait:
                status_response = await client.get(
                    f"{TOPAZ_API_BASE}/task/{task_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                state = status_data.get("status")

                if state == "completed":
                    output_url = status_data.get("output_url")
                    credits_used = status_data.get("credits_used", "N/A")

                    return [
                        types.TextContent(
                            type="text",
                            text=f"✓ {name.replace('topaz_', '').replace('_', ' ').title()} completed!\n"
                                 f"Output URL: {output_url}\n"
                                 f"Credits used: {credits_used}\n"
                                 f"Download the result from the URL above."
                        )
                    ]
                elif state == "failed":
                    error = status_data.get("error", "Unknown error")
                    raise RuntimeError(f"Processing failed: {error}")

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            raise TimeoutError(f"Processing timed out after {max_wait}s")

        else:
            raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="topaz-labs",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
