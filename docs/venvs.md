# Virtual Environment Registry

Centralized tracking of Python virtual environments in this workspace.

## Active Venvs

| Name | Path | Size | Used By | Purpose |
|------|------|------|---------|---------|
| venv_dragonsuite | `/srv/containers/edq/venv_dragonsuite` | ~53MB | `dragonsuite_server.py` | Dashboard backend (FastAPI) |
| venv_florence2 | `/srv/containers/edq/venv_florence2` | ~7GB | `start_dragonsight.sh` | Florence2 vision model service |
| venv_flux2 | `/srv/containers/edq/venv_flux2` | ~7GB | `start_flux2_klein.sh` | DragonFlux Klein image generation |
| venv_wan2gp | `/srv/containers/edq/venv_wan2gp` | ~9GB | `start_wan2gp.sh` | Wan2GP video generation |
| venv_fish_speech | `/srv/containers/edq/venv_fish_speech` | ~8GB | `start_fish_speech.sh` | Fish Speech TTS (OpenAudio S1-mini) |
| venv_heartmula | `/srv/containers/edq/venv_heartmula` | ~12GB | `start_heartmula.sh` | HeartMuLa music generation (3B) |
| venv_sam2 | `/srv/containers/edq/venv_sam2` | ~6GB | `start_sam2.sh` | SAM 2.1 image/video segmentation |
| venv_liveportrait | `/srv/containers/edq/venv_liveportrait` | ~8GB | `start_liveportrait.sh` | LivePortrait portrait animation (KlingTeam) |
| venv_hunyuan3d | `/srv/containers/edq/venv_hunyuan3d` | ~10GB | `start_hunyuan3d.sh` | Hunyuan3D-2 image to 3D |
| venv_qwen3_tts | `/srv/containers/edq/venv_qwen3_tts` | ~8GB | `start_qwen3_tts.sh` | Qwen3-TTS (TTS, cloning, voice design) |
| venv_realesrgan | `/srv/containers/edq/venv_realesrgan` | ~4GB | `start_realesrgan.sh` | Real-ESRGAN image upscaling |
| venv_zimage | `/srv/containers/edq/venv_zimage` | ~8GB | `start_zimage.sh` | Z-Image Base text-to-image (6B) |
| venv_rembg | `/srv/containers/edq/venv_rembg` | ~1GB | `start_rembg.sh` | Rembg AI background removal |
| venv_qwen_image_layered | `/srv/containers/edq/venv_qwen_image_layered` | ~10GB | `start_qwen_image_layered.sh` | Qwen-Image-Layered decomposition |
| venv_mule_game | `/srv/containers/edq/venv_mule_game` | ~50MB | `start_mule_game.sh` | M.U.L.E. web game (Gradio) |
| venv_facefusion | `/srv/containers/edq/venv_facefusion` | ~2GB | `start_facefusion.sh` | FaceFusion face swap & manipulation |

## MCP Server Venvs

| Name | Path | Size | Purpose |
|------|------|------|---------|
| dragonsuite-mcp | `/srv/containers/edq/mcp-servers/dragonsuite/venv` | ~20MB | Dragonsuite MCP server for Claude Code |
| topaz-labs-mcp | `/srv/containers/edq/mcp-servers/topaz-labs/venv` | ~20MB | Topaz Labs API MCP server for image/video enhancement |

## Naming Convention

- Centralized venvs: `/srv/containers/edq/venv_<project>`
- Exception: ComfyUI keeps its venv inside project dir (standard for ComfyUI)

## Cleanup Checklist

When removing a project:
1. Delete the venv directory
2. Remove from this registry
3. Remove from `config/dragonsuite.json`
4. Delete associated scripts in `scripts/`

## History

| Date | Action |
|------|--------|
| 2026-01-20 | Deleted `venv_qwen` (477MB) - Qwen legacy removed |
| 2026-01-20 | Deleted orphan `/Wan2GP/.venv` (9.2GB) - duplicate of projects/Wan2GP |
| 2026-01-20 | Deleted orphan `/Wan2GP/` (63GB total) - script uses projects/Wan2GP |
| 2026-01-20 | Deleted empty `projects/wan-animate/venv` (32K) |
| 2026-01-20 | Created this registry |
| 2026-01-23 | Added `venv_heartmula` for HeartMuLa music generator |
| 2026-01-23 | Added `venv_sam2`, `venv_sadtalker`, `venv_hunyuan3d`, `venv_matanyone` |
| 2026-01-24 | Added `venv_qwen3_tts` for Qwen3-TTS (1.7B models) |
| 2026-01-24 | Added `venv_realesrgan` for Real-ESRGAN upscaling |
| 2026-01-25 | Deleted `comfyui-wan/venv` (129GB) - ComfyUI removed from Dragonsuite |
| 2026-01-29 | Added `venv_zimage` for Z-Image Base (Alibaba Tongyi 6B) |
| 2026-01-31 | Added `venv_rembg` for Rembg AI background removal |
| 2026-01-31 | Added `venv_qwen_image_layered` for Qwen-Image-Layered decomposition |
| 2026-02-01 | Added MCP servers section; created `mcp-servers/dragonsuite/venv` |
| 2026-02-01 | Deleted `venv_matanyone` - dependency conflicts, SAM2+Rembg cover use cases |
| 2026-02-02 | Replaced `venv_sadtalker` with `venv_liveportrait` (KlingTeam, 2026) |
| 2026-02-06 | Added `venv_mule_game` for M.U.L.E. web game (tribute to Dani Bunten Berry) |
| 2026-02-08 | Added `venv_facefusion` for FaceFusion face swap & manipulation |
| 2026-02-08 | Added `topaz-labs-mcp` MCP server for Topaz Labs API integration |
