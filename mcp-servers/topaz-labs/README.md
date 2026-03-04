# Topaz Labs MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A [Model Context Protocol](https://modelcontextprotocol.io/) server for the [Topaz Labs Image Enhancement API](https://developer.topazlabs.com/). Gives Claude Code (and any MCP-compatible AI agent) direct access to Topaz AI image enhancement — upscaling, sharpening, denoising, colorizing, restoration, and generative reimagining.

**Platform-independent** — calls the Topaz cloud API, works on Linux, macOS, and Windows without installing Topaz desktop apps.

## Features

- **21 image enhancement models** across 5 operation types
- **Sync and async** enhancement paths — fast standard models and slower generative models
- **Automatic output naming** — results saved next to source file with model suffix
- **Full error handling** — useful messages for auth failures, invalid files, insufficient credits

## Available Models

### Standard Enhancement (`topaz_enhance_image`)

| Model | Best For |
| --- | --- |
| `Standard V2` | General upscaling, fast |
| `High Fidelity V2` | Maximum detail preservation |
| `Low Resolution V2` | Low-quality source images |
| `Natural Enhance` | Natural-looking enhancement |
| `Detail` | Fine detail recovery |
| `Portrait` | Portraits and faces |
| `Wildlife` | Animals and nature |
| `Auto Sharpen` | Automatic sharpening |
| `Bloom` | Creative enhancement |
| `Bloom Precision` | Bloom with fine control |
| `Bloom Realism` | Bloom with realistic output |
| `Reimagine` | AI reimagination |
| `Wonder 2` | Generative enhancement |
| `Redefine` | AI redefine |
| `Colorize` | Add color to B&W images |
| `Dust-Scratch V2` | Restore old/damaged photos |
| `Sharpen: Standard` | Standard sharpening |
| `Sharpen: Strong` | Aggressive sharpening |
| `Denoise: Normal` | Standard noise removal |
| `Denoise: Strong` | Heavy noise removal |
| `Lighting: Adjust V2` | Lighting/exposure correction |

### Generative Enhancement (`topaz_enhance_generative`)

Async processing, 1–5 minutes. Higher quality for restoration and creative work.

| Model | Best For |
| --- | --- |
| `Recover 3` | Restore severely degraded images |
| `Bloom` / `Bloom Precision` / `Bloom Realism` | Creative bloom effects |
| `Reimagine` | AI-driven reimagination |
| `Wonder 2` | Generative enhancement |
| `Redefine` | AI redefine |

## Quick Start

### 1. Get Your API Key

Sign up and get a key at [developer.topazlabs.com](https://developer.topazlabs.com/).

### 2. Install

```bash
git clone https://github.com/Cavedragon13/topaz-labs-mcp.git
cd topaz-labs-mcp
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

Add to your Claude Code `.mcp.json`:

```json
{
  "mcpServers": {
    "topaz-labs": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/server.py"],
      "env": {
        "TOPAZ_API_KEY": "${TOPAZ_API_KEY}"
      }
    }
  }
}
```

Set your API key in `.env`:

```bash
TOPAZ_API_KEY=your-key-here
```

### 4. Use It

Ask Claude:

```text
Enhance this image with Topaz: /path/to/photo.jpg
```

```text
Upscale /path/to/photo.jpg using High Fidelity V2 and save to /output/
```

```text
Restore this old damaged photo: /path/to/scan.jpg (use Recover 3)
```

```text
Add color to this black and white photo: /path/to/bw.jpg
```

## Direct API Testing

Test without Claude using curl:

```bash
source .env

# Standard enhancement
curl -X POST https://api.topazlabs.com/image/v1/enhance \
  -H "X-API-Key: $TOPAZ_API_KEY" \
  -F "image=@photo.jpg" \
  -F "model=Standard V2" \
  -o enhanced.jpg

# Sharpen
curl -X POST https://api.topazlabs.com/image/v1/sharpen \
  -H "X-API-Key: $TOPAZ_API_KEY" \
  -F "image=@photo.jpg" \
  -F "model=Standard" \
  -o sharpened.jpg
```

## API Details

| Operation | Endpoint | Notes |
| --- | --- | --- |
| Enhance (most models) | `POST /image/v1/enhance` | Returns image bytes directly |
| Sharpen | `POST /image/v1/sharpen` | Model: Standard, Strong |
| Denoise | `POST /image/v1/denoise` | Model: Normal, Strong |
| Lighting | `POST /image/v1/lighting` | Model: Adjust V2 |
| Generative (async) | `POST /image/v1/enhance-gen/async` | Returns requestId, poll for result |
| Poll status | `GET /image/v1/request/{requestId}` | Check status, get download URL |

**Authentication:** `X-API-Key` header
**Input formats:** JPEG, PNG, TIFF
**Output:** JPEG

## Requirements

- Python 3.10+
- `httpx>=0.24.0`
- `mcp>=1.0.0`

## License

MIT — see [LICENSE](LICENSE)

## Notes

- This is a community-built server, not affiliated with Topaz Labs Inc.
- Model availability and API endpoints verified 2026-03-03.
- Topaz Labs may add or remove models without notice — if a model returns 400/404, check [developer.topazlabs.com](https://developer.topazlabs.com/) for the current list.
