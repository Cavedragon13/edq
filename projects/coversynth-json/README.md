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

**Character reference:** "Character reference…" (or dropping an image on the file row) uploads a PNG/JPEG/WebP to `/home/edq/ai_generated/frameforge/_references/` and attaches it to every job as reference id `character`. Each prompt then tells the model to keep that character's face, hair, skin tone, and build while taking pose, clothing, and background from the prompt. OpenAI receives it via `images.edit`; Gemini receives it as an image part. A head-and-shoulders crop works better than a full cover. Prompt cleanup runs automatically before each run ("Clean before run", on by default).

Output projects are saved under `/home/edq/ai_generated/frameforge/<project_name>/`. A relative `output_path` in a manifest only supplies the project folder name; an absolute path is used as-is. Each project folder holds:

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
