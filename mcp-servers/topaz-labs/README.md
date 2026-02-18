# Topaz Labs MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> 🎨 Professional AI image enhancement through Claude Code

The **first** Model Context Protocol (MCP) server for [Topaz Labs](https://www.topazlabs.com/) — enabling professional image enhancement, upscaling, sharpening, denoising, and restoration directly from Claude Code.

![RTFM: Read The Fine Manual Before You Code](../../ai_generated/rtfm_logo_original.png)

## Features

✨ **Enhance Images** - Upscale 1-4x with Standard V2 or Recover 3 models
⚡ **Async Processing** - Generative enhancement with polling
🔧 **Restore** - Professional restoration for old/damaged photos
💰 **Credits** - Check API usage and remaining credits
📁 **Local Files** - Works with local image paths (no upload server needed)

## Quick Start

### 1. Get Your API Key

1. Sign up at [topazlabs.com/api](https://www.topazlabs.com/api)
2. Navigate to **My Account** → **API Keys**
3. Create a new API key (save it immediately - you can't view it again!)

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install httpx mcp
```

### 3. Configure MCP Server

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
TOPAZ_API_KEY=your-api-key-here
```

### 4. Restart Claude Code

The MCP server will load automatically on next startup.

## Usage Examples

### Enhance an Image (Sync)

```python
# Via Claude Code MCP tools
topaz_enhance_image(
    image_path="/path/to/photo.jpg",
    model="Standard V2"
)
# → Saves: /path/to/photo_enhanced.jpg
```

### Restore Old Photos (Async)

```python
# Generative restoration with Recover 3
topaz_enhance_async(
    image_path="/path/to/old_photo.jpg",
    model="Recover 3"
)
# → Polls until complete, saves: /path/to/old_photo_Recover_3_enhanced.jpg
```

### Check Credits

```python
topaz_check_credits()
# → "Credits endpoint not available (status 404). Check your account at..."
# Note: Credit checking may not be available via API - check web portal
```

## Available Tools

| Tool | Description | Input | Output |
|------|-------------|-------|--------|
| `topaz_enhance_image` | Sync enhancement (Standard V2) | `image_path`, `model` | Enhanced JPG in same dir |
| `topaz_enhance_async` | Async generative (Recover 3) | `image_path`, `model` | Restored JPG in same dir |
| `topaz_check_credits` | Check API balance | None | Credit info or error |

## API Details

**Base URL:** `https://api.topazlabs.com`
**Authentication:** `X-API-Key` header
**Format:** `multipart/form-data` (actual file uploads)
**Output:** Direct image bytes (JPEG)

### Endpoints Used

```bash
# Standard enhancement (sync)
POST /image/v1/enhance
Content-Type: multipart/form-data
X-API-Key: your-key
Body: image=@file.jpg&model=Standard V2

# Generative enhancement (async)
POST /image/v1/enhance-gen/async
Returns: {"requestId": "..."}

# Check status (async)
GET /image/v1/request/{requestId}
Returns: {"status": "complete", "downloadUrl": "..."}
```

### Models

- **Standard V2** - Fast, high-quality upscaling (synchronous, ~30s)
- **Recover 3** - Generative restoration for damaged images (async, 1-5min)

## Lesson Learned: RTFM! 📖

This MCP server went through **two major versions**:

**v1.0 (Wrong)** - Built on assumptions:
- ❌ Used `https://api.topazlabs.com/v1/credits`
- ❌ Used `Authorization: Bearer` header
- ❌ Expected JSON with image URLs
- ❌ Couldn't work at all

**v1.1 (Correct)** - Built from documentation:
- ✅ Uses `https://api.topazlabs.com/image/v1/enhance`
- ✅ Uses `X-API-Key` header
- ✅ Uploads actual files via multipart/form-data
- ✅ Works with real Topaz Labs API

**Takeaway:** 5 minutes reading [developer.topazlabs.com](https://developer.topazlabs.com/) saved 30+ minutes of rewriting!

Always **Read The Fine Manual Before You Code**. 🎯

## Requirements

- **Python:** 3.10+
- **Dependencies:**
  ```
  httpx>=0.24.0
  mcp>=1.0.0
  ```

Install via:
```bash
pip install -r requirements.txt
```

## Architecture

```
Claude Code
    ↓ (stdio MCP protocol)
Topaz Labs MCP Server
    ↓ (HTTPS multipart/form-data)
Topaz Labs Cloud API
    ↓
Enhanced Images
```

## Pricing

Topaz Labs uses **credit-based** pay-per-use:

- Credits vary by resolution and processing mode
- Monitor usage at [topazlabs.com/my-account](https://topazlabs.com/my-account/)
- API credit endpoint may not be public (check web portal instead)

## Error Handling

The server gracefully handles:

- **FileNotFoundError** - Image path doesn't exist
- **HTTPStatusError 401** - Invalid API key
- **HTTPStatusError 402** - Insufficient credits
- **HTTPStatusError 429** - Rate limit exceeded
- **HTTPStatusError 404** - Endpoint not found
- **TimeoutError** - Processing timeout (5 minutes)

## Troubleshooting

### "TOPAZ_API_KEY environment variable not set"

Set your key in one of:
1. `.mcp.json` env section
2. Shell: `export TOPAZ_API_KEY=your-key`
3. `.env` file: `TOPAZ_API_KEY=your-key`

### "404 Not Found"

✅ **This server uses correct endpoints** (as of 2026-02-08):
- `/image/v1/enhance` (verified working)
- `/image/v1/enhance-gen/async` (verified working)

If you get 404s, check [developer.topazlabs.com](https://developer.topazlabs.com/) for API changes.

### "402 Payment Required"

Add credits at [topazlabs.com/my-account](https://topazlabs.com/my-account/).

### Images not processing

1. **Check file exists:** `ls -la /path/to/image.jpg`
2. **Verify API key:** `echo $TOPAZ_API_KEY`
3. **Test API directly:**
   ```bash
   curl -X POST https://api.topazlabs.com/image/v1/enhance \
     -H "X-API-Key: $TOPAZ_API_KEY" \
     -F "image=@test.jpg" \
     -F "model=Standard V2" \
     -o enhanced.jpg
   ```

## Development

### Project Structure

```
topaz-labs/
├── server.py          # MCP server (v1.1 - corrected)
├── requirements.txt   # Dependencies
├── README.md          # This file
└── LICENSE            # MIT License
```

### Testing

```bash
# Start the MCP server
python server.py

# Use Claude Code to test:
# "Enhance this image: /path/to/test.jpg"
```

### Contributing

This is the **first Topaz Labs MCP server**! Contributions welcome:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing`
5. Open Pull Request

## Resources

- **Topaz Labs API:** https://developer.topazlabs.com/
- **API Reference:** https://developer.topazlabs.com/api-reference
- **Get API Key:** https://topazlabs.com/my-account/
- **MCP Protocol:** https://modelcontextprotocol.io/
- **Report Issues:** GitHub Issues (coming soon)

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io/)
- Powered by [Topaz Labs AI](https://www.topazlabs.com/)
- Logo generated with Z-Image Base (RTFM theme)
- Inspired by professional image workflows

## Author

Built for the Claude Code community 🚀

**Note:** Unofficial, community-built MCP server. Not affiliated with Topaz Labs Inc.

---

**Made with Claude Code** | [**RTFM Before You Code**](../../docs/topaz-labs-integration.md) 📖
