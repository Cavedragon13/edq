# Topaz Labs MCP Server

MCP server providing access to Topaz Labs AI image/video enhancement APIs.

## Features

- **Image Enhancement** - AI-powered upscaling and quality improvement
- **Sharpening** - Standard and generative sharpening
- **Denoise** - Remove noise from images
- **Restore** - Restore old/damaged photos (generative)
- **Credits Management** - Check remaining API credits
- **Cost Estimation** - Estimate credits before processing

## Setup

### 1. Get Your Topaz Labs API Key

1. Log in to [Topaz Labs Developer Portal](https://developer.topazlabs.com/)
2. Go to API Keys section
3. Click "Create" and give your key a name
4. **Copy the key immediately** - it won't be shown again!

### 2. Add to Environment

Add your API key to `/srv/containers/edq/.env`:

```bash
TOPAZ_API_KEY=your_api_key_here
```

### 3. Add to MCP Config

Add this entry to `/srv/containers/edq/.mcp.json`:

```json
{
  "mcpServers": {
    "topaz-labs": {
      "command": "/srv/containers/edq/mcp-servers/topaz-labs/venv/bin/python",
      "args": [
        "/srv/containers/edq/mcp-servers/topaz-labs/server.py"
      ],
      "env": {
        "TOPAZ_API_KEY": "${TOPAZ_API_KEY}"
      }
    }
  }
}
```

### 4. Restart Claude Code

Restart Claude Code to load the new MCP server.

## Usage

Once configured, you can use Topaz Labs tools directly from Claude Code:

**Check credits:**
```
Use the topaz_check_credits tool to see my remaining credits
```

**Enhance an image:**
```
Use topaz_enhance_image to upscale this image 2x: https://example.com/image.jpg
```

**Denoise:**
```
Use topaz_denoise_image to remove noise from https://example.com/noisy.jpg
```

**Restore old photo:**
```
Use topaz_restore_image to restore this damaged photo: https://example.com/old.jpg
```

## Available Tools

- `topaz_enhance_image` - Enhance/upscale (1-4x)
- `topaz_sharpen_image` - Sharpen image
- `topaz_denoise_image` - Remove noise
- `topaz_restore_image` - Restore damaged photos
- `topaz_check_credits` - Check API credits
- `topaz_estimate_cost` - Estimate operation cost

## Notes

- You already have a Topaz Labs subscription! This uses your existing credits.
- Images are processed via Topaz Labs cloud (not local)
- Processing times vary by image size and operation
- Results are returned as URLs for download

## Local Alternatives

If you prefer 100% local processing:
- **Upscayl** - Open source creative upscaler (can add to Dragonsuite)
- **Real-ESRGAN** - Already installed (port 8017)
- **ControlNet Tile** - Can add with FLUX for creative upscaling

Topaz API is best for when you want Topaz-quality results without running locally.
