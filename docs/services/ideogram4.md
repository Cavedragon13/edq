# Ideogram 4

Ideogram 4 is installed as a Dragonsuite image-generation service at `http://192.168.7.226:8054`, backed by `/srv/containers/edq/projects/ideogram4` and the isolated `/srv/containers/edq/venv_ideogram4` environment. The launcher `/srv/containers/edq/scripts/start_ideogram4.sh` loads `/srv/containers/edq/.env`, requires `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` for the gated Hugging Face weights, and uses `IDEOGRAM_API_KEY` or `MAGIC_PROMPT_API_KEY` when magic-prompt expansion is selected. Outputs and JSON sidecars are written to `/home/edq/ai_generated/ideogram4`.

Default operation uses the CUDA-only `ideogram-ai/ideogram-4-nf4` weights, `V4_TURBO_12`, and 1024 square output for a fast first pass on udragon's RTX 5070 Ti 16GB. The UI also exposes direct plain prompts, direct structured JSON captions, other documented sampler presets, common documented resolution buckets, optional Hive moderation keys, and an fp8 fallback path.
