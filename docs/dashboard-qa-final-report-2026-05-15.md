# Dragonsuite Dashboard QA Final Report

Date: 2026-05-15

Scope: This report summarizes the dashboard QA/repair campaign recovered from the crash-affected Codex JSONL sessions plus the follow-up HiDream/Dragonsight checks. It is not a full fresh retest of every service today; it is the best consolidated state from the completed QA slices, recovered transcripts, service docs, and the final live checks.

## Executive Summary

The dashboard is in much better shape than at the start of the campaign. The core recurring integration bugs were not model quality problems; they were wiring problems: wrong model packaging, missing output metadata, Gradio version drift, incomplete local model installs, stale-process checks, and launchers that reported "running" before the app was truly usable.

HiDream-O1 is now checked and working in the realistic workflow: Dragonsight can stay open, HiDream can launch, generate a real image, save output, stop, and release VRAM. Dragonsight now defaults to `gemma4:e4b` for Ollama.

The main remaining items are not mysteries:

- Fish Speech S2-Pro is a hardware no-go on this host without quantization/offload/memory guards.
- Fish Speech S1-mini starts but does not produce usable audio yet.
- TADA is blocked by gated upstream access to `meta-llama/Llama-3.2-1B`.
- Dragonsight Florence is broken on the current Transformers stack and is low priority if Gemma4 is the local model to beat.
- Wan2GP still needs its own dedicated test cycle.
- Paid/cloud/side-effect tools were only smoke-tested safely, not fully exercised.

## Working

### Dashboard Control Plane

- Dragonsuite API and service start/stop flow worked for the tested services.
- Duplicate port conflict was fixed: `foundation-1` moved to `8027`; `linkding` remains on `8039`.
- Dashboard stop behavior was fixed for no-port/background services that have `stop_command`.
- Linkding start/stop was tightened to use the project `.env`.
- On-demand services were repeatedly returned to clean or near-idle GPU state after tests.

### Image Generation And Image Tools

Verified with real outputs:

- `hidream-o1`: passed final realistic workflow test. Generated Valyria prompt output at `/home/edq/ai_generated/hidream-o1/output_20260514_223810_321.png`; saved `latest.png` and `latest.json`; stopped cleanly. Note: requested `1024x1024` snapped internally to `2048x2048`.
- `zanime`: fixed to use the correct local Diffusers folder; 40-step/default-style render passed. Cheap 12-20 step smokes can be misleading.
- `zimage-base`: fixed to use local cached snapshots; generated prompt-following Valyria output.
- `dragonflux-klein`: fixed to use local cached snapshots and dashboard `output_dir`; generated prompt-following output.
- `deepgen`: repaired from broken/missing old path to local `DeepGen-1.0-diffusers`; output verified.
- `realesrgan`: API upscale verified with generated inputs.
- `creative-upscale`: prompt-guided chained upscale verified; slow smoke target, about 7.5 minutes for a 20-step 2x test.
- `rembg`: API background removal verified; ONNX CUDA provider warning falls back successfully.

### Audio / TTS / Audio Processing

Verified or materially improved:

- `voxcpm2`: persistent Gradio output fixed with `allowed_paths`; short WAV output verified.
- `qwen3-tts`: SoX and numba cache issues fixed; real WAV output verified.
- `qwen3-audiobook`: fixed to accept Qwen3-TTS filepath returns; MP3/WAV output verified.
- `audio-tools`: CUDA/PyTorch and LavaSR/Vocos compatibility repaired; `/api/enhance` output verified.
- `omnivoice-studio`: dashboard launch/UI smoke passed in the broader sweep.
- `voxtral-tts`: Gradio launch compatibility fixed; launch/HTTP/stop smoke passed.

### Music

Verified with real outputs:

- `heartmula`: generated from `stale_ip_blues`; persistent MP3 verified.
- `foundation-1`: output rewired to `/home/edq/ai_generated/foundation-1`; WAV and MIDI outputs verified.
- `ace-step`: XL dashboard integration and model initialization were verified in the broader pass; stop behavior was hardened and VRAM release was verified.

### Non-GPU / Utility / Game / Automation Launch Smokes

These passed launch, HTTP reachability, and stop or safe UI-level checks during the broad sweep:

- `mcp-inspector`
- `horse-racing`
- `interactive-games`
- `mule-game`
- `dnd-generator`
- `concert-shirt`
- `dragonart-studio`
- `the-movies`
- `dl-gallery`
- `dragonweyr`
- `kalshi`
- `mercury2`
- `linkding`

Important caveat: several of these have paid/cloud/API/live-action paths. Passing a safe UI smoke does not mean every production workflow was executed.

## Not Fully Tested

### Needs Dedicated Cycle

- `wan2gp`: intentionally left for its own testing cycle. It is heavy, has click/download/setup workflow, and may be better driven with a local agent such as OpenCode + Gemma4.
- `agentic-video`: not fully exercised because it is Gemini-backed and can incur external API use.
- `dragonsong`: not fully exercised because it depends on Lyria/Gemini cloud flow.
- `dragonart-studio`: safe launch/UI smoke passed, but paid Gemini/OpenAI/Veo paths were not fully exercised.
- `the-movies`: safe launch/UI smoke passed, but full Nano Banana/Veo/Lyria/Gemini generation was not exercised.
- `dnd-generator`: UI smoke passed, but paid OpenAI portrait generation was not the focus of this dashboard sweep.

### Manual / Side-Effectful / Not Normal Smoke Targets

- `file-watcher`: side-effectful background daemon; do not casually smoke because it can rename real files.
- `dragonclawd`: Telegram/control bot; side-effectful and should be tested intentionally.
- `port-whisperer`: CLI utility, not a browser service.
- `ollama`: underlying local model service, not a normal dashboard app smoke.
- `lm-studio`: manual desktop app/local server.
- `topaz-labs`: cloud/credit-backed integration, not local dashboard smoke.

### External Always-On Services

Minidragon media/smart-home services were treated as health/link checks rather than full functional tests:

- Jellyfin
- Immich
- Navidrome
- Komga
- Portainer
- Home Assistant
- Pi-hole

## Cannot Work / Currently Blocked

### Fish Speech S2-Pro

Status: hardware no-go on current host.

Evidence: dashboard/direct S2-Pro startup reached Llama checkpoint load, then the system later logged a global OOM kill of the Python loader. The killed process had roughly 16GB RSS. On a 32GB RAM / 16GB RTX 5070 Ti host, this is not a safe dashboard service without a lighter model, quantization/offload strategy, or a hard memory guard.

Do not keep retesting S2-Pro in the dashboard as-is. It can lock the machine.

### Fish Speech S1-mini

Status: starts, but not ready.

Fixes landed: tokenizer handling, stale-process detection, persistent output saving, Gradio `allowed_paths`.

Remaining failure: generated WAVs were only around `0.046s`, so it fails the output sanity bar. Treat as code/checkpoint compatibility, not dashboard wiring.

### TADA TTS

Status: blocked.

Fixes attempted/landed: missing DAC dependency, numba cache guard, Gradio output path handling, Transformers stable-line pin.

Remaining blocker: gated upstream access to `meta-llama/Llama-3.2-1B` returns 403. Needs model access or reconfiguration to local/ungated model.

### Dragonsight Florence Backend

Status: broken, low priority if Gemma4 is the default local vision model.

Observed issues on current stack:

- `_supports_sdpa` missing unless loaded with `attn_implementation="eager"`.
- Florence language submodel no longer has a working `generate()` path under current Transformers v5 behavior.
- Attempted compatibility shims progressed but still failed; half-fix was removed.

Current practical state: Dragonsight UI is running and now defaults to `gemma4:e4b`. Florence should be treated as a separate compatibility repair, not part of HiDream readiness.

### JustDubit

Status: blocked by missing model assets.

Observed missing assets included LTX/Gemma components under `/srv/containers/edq/models/justdubit/`. The dashboard currently only had the JustDubit LoRA downloaded when checked. Needs a dedicated model-download/setup pass.

## Recurring Problems Fixed Across Tools

These are the patterns that kept repeating. This is the most important section for future agents.

1. Wrong dashboard control point

Agents drifted toward Pinokio or guessed local files. For Dragonsuite work, the source of truth is `/srv/containers/edq/config/dragonsuite.json` plus the matching launcher under `/srv/containers/edq/scripts/`.

2. Wrong model packaging or path

Examples:

- Z-Anime: AIO/ComfyUI vs Diffusers confusion.
- Z-Anime local loader: `subfolder="diffusers"` is right for a HF repo id, but the local path needed the actual `diffusers/` directory.
- DeepGen: old path/install was incomplete; fixed to local `DeepGen-1.0-diffusers`.
- Z-Image and DragonFlux: needed local cached snapshot resolution to avoid surprise first-run downloads.

Rule: verify the exact runtime model format before declaring a service ready.

3. Dashboard metadata drift

Examples:

- `foundation-1` and `linkding` both used port `8039`.
- Several services had missing `output_dir`.
- Dashboard cards advertised variants or features the actual launcher did not run.

Rule: dashboard metadata must describe the actual runtime, not every possible upstream capability.

4. Persistent output path failures

Several Gradio apps successfully generated files but could not return them because the output directory was outside Gradio's allowed paths.

Examples:

- DeepGen
- VoxCPM2
- TADA
- dormant/older audio Gradio code paths

Rule: if a Gradio component returns a filepath under `~/ai_generated/...`, launch with `allowed_paths=[str(OUTPUT_DIR)]`.

5. Missing output folders and incomplete service directories

Examples:

- `justdubit` output folder had to be created.
- Early DeepGen and Creative Upscaler state was missing local install/model pieces.
- Some dashboard entries lacked output metadata even though the app wrote files.

Rule: create output dirs explicitly, wire them into dashboard metadata, and fail fast if model dirs are missing.

6. Gradio version drift

Recurring fixes:

- Remove `show_api=False` where Gradio 6 rejects it.
- Move unsupported/changed theme usage to a compatible launch path.
- Use `allowed_paths` for persistent files.

Affected services included `wan-1b`, `ltxvideo`, `voxtral-tts`, `lavasr`, `ltx2`, `qwen3-tts`, `zanime`, and audio/file-returning Gradio apps.

7. CUDA/PyTorch/Blackwell mismatch

Audio Workstation initially used a PyTorch build that did not support RTX 5070 Ti Blackwell (`sm_120`). Repaired by moving the venv to CUDA 12.8-compatible PyTorch and updating dependent audio packages.

Rule: on udragon/RTX 5070 Ti, validate CUDA support in the venv before blaming app code.

8. Runtime dependency drift

Examples:

- Qwen3-TTS needed SoX and explicit writable `NUMBA_CACHE_DIR`.
- TADA needed DAC and compatible Transformers handling.
- Audio Workstation needed torchcodec and LavaSR/Vocos compatibility handling.
- Rembg ONNX CUDA warning was non-blocking because fallback worked.

Rule: distinguish fatal dependency errors from warnings/fallbacks.

9. Stale process and stop behavior

Several launchers treated stale processes as healthy, or stop commands failed for no-port/background tools.

Fix patterns:

- Check both expected app path/checkpoint and listening port.
- Stop by exact process signature.
- Support `stop_command` even when `port` is null.
- Verify VRAM drops after stopping heavy services.

10. Output sanity is required

API success and a saved file are not enough.

Examples:

- Z-Anime tiny smoke produced a blank/weak result, while intended 40-step settings passed.
- Fish Speech S1-mini produced only a tiny blip despite launching.
- HiDream requested `1024x1024` but actually generated `2048x2048`.

Rule: inspect representative output against the prompt before calling generative services ready.

## LLM Handoff: What To Tell Claude

Claude, stop treating "it launches" as done.

For Dragonsuite, do this every time:

1. Read local guidance first:
   - `/srv/containers/edq/CLAUDE.md`
   - `/srv/containers/edq/docs/organization-principles.md`
   - `/srv/containers/edq/docs/venvs.md`
   - relevant `docs/services/*.md`

2. Use the real control points:
   - Dashboard config: `/srv/containers/edq/config/dragonsuite.json`
   - Launchers: `/srv/containers/edq/scripts/start_<service>.sh`
   - Service docs: `/srv/containers/edq/docs/services/*.md`

3. Do not create parallel Pinokio/manual setups when the user says "in the dashboard".

4. Verify the actual model format:
   - Diffusers folder vs ComfyUI/AIO checkpoint
   - GGUF vs HF repo snapshot
   - local cache path vs remote repo id
   - base/dev/turbo/distill variant actually used by the code

5. Ensure local model assets are complete before launch. Do not make dashboard startup do giant first-run downloads unless the user asked for that.

6. Every persistent service needs:
   - own top-level venv or container
   - fail-fast model checks
   - output dir under `/home/edq/ai_generated/<service>`
   - dashboard `output_dir` where applicable
   - accurate dashboard description/features
   - stop command that actually frees the port/VRAM

7. For Gradio:
   - remove incompatible `show_api=False`
   - use `allowed_paths=[str(OUTPUT_DIR)]` when returning persistent files
   - test against current Gradio behavior, not remembered API behavior

8. On this RTX 5070 Ti box:
   - use CUDA 12.8-compatible PyTorch
   - check `torch.cuda.get_device_capability()`/import before assuming the model is broken
   - avoid launching multiple heavy GPU models unless VRAM math says it is safe

9. Done means:
   - dashboard start returns cleanly
   - port/API is reachable
   - representative output is generated
   - output visibly follows prompt/input
   - output lands in the persistent dir
   - service stops
   - VRAM/RAM returns near baseline
   - docs/config reflect the actual runtime

10. Do not ignore failed output quality.
    A blank image, a 0.046s audio blip, a missing file return, or "it only works at the right number of steps" is not ready. Capture the condition precisely.

## Wan2GP Recommendation

Wan2GP should be handled as its own mini-project, not squeezed into the general dashboard report.

Suggested approach:

1. Use OpenCode + Gemma4 as the local helper if you want a local model-guided setup.
2. First pass should be read-only:
   - inspect Wan2GP docs
   - list model choices and local cache state
   - identify expected download size and VRAM/RAM profile
   - map which UI clicks correspond to files/configs on disk
3. Choose one local model/profile deliberately.
4. Pre-download or point Wan2GP to local models outside the dashboard launcher.
5. Only then add/adjust dashboard launcher behavior.
6. Smoke test with a tiny/fast profile, then verify output file, stop behavior, and VRAM release.

Do not start Wan2GP testing as "click until it downloads enough stuff." That is exactly the kind of workflow that should be converted into explicit local model selection and preflight checks first.
