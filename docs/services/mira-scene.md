# Mira Scene (port 8071)

Single image → editable 3D scene, using the full upstream
[Mira-Scene](https://github.com/sunyangtian/Mira-Scene) pipeline
([HF weights](https://huggingface.co/Yang-Tian/Mira-Scene), MIT code; third-party parts keep their own licences).

Dashboard card `mira-scene`, launcher `scripts/start_mira_scene.sh`, web server
`scripts/mira_scene_server.py`, UI `media/mira_scene.html`. Outputs land in
`/home/edq/ai_generated/mira-scene/<job>/` (`job.json`, `run.log`, `in/`, `out/<case>/…`);
`latest.json` points at the newest job.

## What a job does

Seven stages (upstream `infer_scripts/pipeline.py`), run by `scripts/run_mira_pipeline.sh`:

| Stage | Env (`conda_envs/`) | Notes |
| --- | --- | --- |
| segmentation | `mira-segmentation` | SAM3 masks + agentic **Gemini** object naming, verification, support-relation scene graph |
| depth | `mira-geometry` | Pixel-Perfect Depth (+ MoGe-2, Depth-Anything-V2) |
| ccm | `mira-ccm` | Canonical coordinate maps + voxels (Mira-CCM Stage 2 checkpoint = `models/mira-scene/pipeline`) |
| mesh | `mira-sam3d` | SAM-3D Objects stage 2, textured (baking on) |
| floor | `mira-geometry` | Floor plane; texture extended with Gemini image edit |
| scene | `mira-geometry` | Gravity-aware joint placement → `scene.glb`, `scene_with_floor.glb` |
| environment | `mira-geometry` | Environment panorama via Gemini image edit (see limits) |

Typical run: roughly 25–35 min on the RTX 5070 Ti for a 9-object scene (segmentation is the longest stage). One job at a time; the server holds no VRAM
itself (the launcher gate reserves ~14.5 GB for a running job).

## Gemini wiring (no Lumina key)

Upstream expects a Lumina OpenAI-compatible endpoint with `CODEX_API_KEY`. We keep the upstream code and redirect it:

- `run_mira_pipeline.sh` exports `CODEX_API_KEY` from `GOOGLE_API_KEY` in `/srv/containers/edq/.env` (never written to disk elsewhere).
- Segmentation/scene-graph VLM: Gemini's OpenAI-compatible endpoint
  (`api.base_url` in `projects/Mira-Scene/infer_scripts/config/local.yaml`), model `gemini-3.1-pro-preview`.
  Upstream's default `gemini-2.5-pro` returns 404 for new users (checked 2026-09-30). `gemini-3.8-flash` also works (cheaper).
- Floor texture + environment map: Gemini's OpenAI compatibility layer has no `images.edit`, so
  `infer_scripts/gemini_image.py` calls the native google-genai **Interactions API** (`gemini-3.1-flash-image`,
  response type must be `image/jpeg`). Enabled by `MIRA_IMAGE_BACKEND=gemini`.

## Local patches (committed in `projects/Mira-Scene`, rebase onto upstream)

1. `gemini_image.py` + hooks in `4_estimate_floor.py`, `6_generate_environment_map.py`.
2. `utils/sam3d_utils.py`: `MIRA_LOW_VRAM=1` keeps SAM-3D weights on CPU and moves the embedder, generator and
   decoders to the GPU only while used. Upstream keeps everything resident and OOMs on 16 GB (14 GB → ~4 GB peak).
3. `infer_scripts/config/local.yaml` (our paths; no secrets).

## Known limits

- **Environment panorama is imperfect.** Gemini has no 2:1 aspect ratio, so it renders 21:9 and we resample to 2:1;
  results look like a street panorama but can show seams/duplicated content. It is a background/lighting extra, not part of the scene geometry.
- Automatic segmentation can miss or mislabel objects; upstream recommends reviewing masks in its SAM3 web UI
  (`0_segmentation.py --web`, not wired into the dashboard).
- TRELLIS.2 mesh backend is not set up (`mesh.backend: sam3d`).
- Gemini calls are paid (Gemini API project, Tier 2 prepay). Segmentation is an agentic multi-round loop per object, so cost scales with object count; per-scene cost has not been measured yet — check the AI Studio usage page after a few scenes.

## CLI / maintenance

```bash
bash scripts/run_mira_pipeline.sh <image_or_dir> <output_dir> [--from-stage S --force-stage S]
bash scripts/download_mira_scene_models.sh && bash scripts/download_mira_stage_models.sh
```

Conda prefixes are absolute paths (`conda_envs/mira-*`, Miniforge in `opt/miniforge3`); never move them.
`scripts/create_mira_base_envs.sh` rebuilds them. Older Codex-era notes: `archives/unwind-mira-supra2-20260930/`.
