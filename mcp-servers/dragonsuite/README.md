# Dragonsuite MCP Server

Custom MCP server for managing Dragonsuite GPU services from Claude Code.

## Tools

- **dragonsuite_status** - Get status of all services
- **dragonsuite_vram** - Check GPU VRAM usage
- **dragonsuite_start** - Start a service
- **dragonsuite_stop** - Stop a service
- **dragonsuite_logs** - View service logs

## Installation

```bash
cd /srv/containers/edq/mcp-servers/dragonsuite
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

This server is configured in Claude Code's MCP settings and runs automatically when needed.

## Available Services

| ID | Name | Port | GPU |
|----|------|------|-----|
| dragonsuite | Dashboard | 8100 | No |
| dragonflux | DragonFlux Klein | 8001 | Yes |
| wan2gp | Wan2GP Video | 8002 | Yes |
| fish-speech | Fish Speech TTS | 8003 | Yes |
| heartmula | HeartMuLa Music | 8004 | Yes |
| sam2 | SAM 2.1 | 8005 | Yes |
| sadtalker | SadTalker | 8006 | Yes |
| hunyuan3d | Hunyuan3D-2 | 8007 | Yes |
| matanyone | MatAnyone | 8008 | Yes |
| qwen3-tts | Qwen3-TTS | 8009 | Yes |
| realesrgan | Real-ESRGAN | 8010 | Yes |
| zimage | Z-Image Base | 8011 | Yes |
| rembg | Rembg | 8012 | Yes |
| qwen-layered | Qwen-Image-Layered | 8013 | Yes |
| remotion | Remotion Studio | 3000 | No |
