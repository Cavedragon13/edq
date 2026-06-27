# FrameForge

Seed 13 Productions batch image-generation dashboard.

FrameForge turns an idea or manifest into independent image jobs:

```text
idea -> prompt refinement -> manifest.json -> queued jobs -> saved images + metadata
```

Core behavior:

- Canonical provider-neutral manifests.
- Provider switch for OpenAI (`gpt-image-2`) and Gemini (`gemini-3.1-flash-image-preview`).
- Prompt cleanup pass that rewrites named-artist/style references into visual art direction before image generation.
- 1 to 10 independent jobs per manifest.
- One image API call per job.
- Per-job status, metadata, output files, and JSONL job start/complete/error events.
- Validation, dry-run, opt-in prompt cleanup, failed-job retry, and gallery download modes.
- Browser runs are executed one image at a time so completed images appear as the batch progresses.
- Legacy CoverSynth endpoints are still present for older callers.

Output projects are saved under `/home/edq/ai_generated/<project_name>/` with:

```text
manifest.json
run_log.json
references/
jobs/
images/
logs/
```

Run through Dragonsuite or directly:

```bash
cd /srv/containers/edq
bash scripts/start_coversynth_json.sh
```
