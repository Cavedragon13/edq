# Mira-Scene readiness note

Mira-Scene remains a separate source checkout at
`/srv/containers/edq/projects/Mira-Scene` and is not registered as a Dashboard
service yet. The upstream inference guide requires five separate environments,
external CUDA-extension projects, gated SAM 3 / SAM 3D or TRELLIS.2
checkpoints, and a configured image-generation API. Its published manifests
use older CUDA/PyTorch combinations; udragon's RTX 5070 Ti standard is cu128,
so the environment bootstrap is being adapted rather than copied verbatim.

Progress on 2026-09-28 through 2026-09-29:

- Private Miniforge is installed at `/srv/containers/edq/opt/miniforge3`.
- Official SAM3, SAM-3D Objects, and TRELLIS.2 source checkouts are present
  under `/srv/containers/edq/projects/`.
- Hugging Face identity and the Mira core/SAM3 gated-read access were verified
  without printing the token. The separate SAM-3D Objects, RMBG-2.0, and
  DINOv3 gates remain unapproved.
- The Mira core pipeline is complete under `/srv/containers/edq/models/mira-scene`.
- All five base environment prefixes are now present under
  `/srv/containers/edq/conda_envs/` with PyTorch 2.7.1/cu128 and validated
  CUDA access.
- Segmentation, geometry, and CCM runtime dependencies are installed and
  import-checked, including the official SAM3 source, Open3D/Trimesh,
  spconv-cu120, Mira-CCM, and UniDataset.
- The explicit stage-model downloader completed the PPD/MoGe/Depth-Anything
  stack and the now-authorized SAM3 checkpoint. `sam3.pt` is present at
  3,450,062,241 bytes.
- The PPD depth stack is now complete and passed a real smoke test on Mira's
  included `003_home_office` example: 518x518 depth, camera points, valid mask,
  and PLY output were written under
  `/home/edq/ai_generated/test-artifacts/images/mira-depth-smoke/`.
- SAM3 also passed real CUDA inference on the same example: the `chair` prompt
  produced a 518x518 mask with score 0.9648 and an inspectable mask/overlay at
  `/home/edq/ai_generated/test-artifacts/images/mira-sam3-smoke/`.
- SAM-3D Objects access is now accepted and its explicit checkpoint download
  is active, with roughly 5.9 GiB staged at the latest check. TRELLIS.2's
  main checkpoint and its previously gated RMBG-2.0/DINOv3 dependencies are
  also now authorized, but the quantized companion path has not downloaded
  duplicate weights yet. The non-interactive environment has no
  CODEX_API_KEY or LUMINA_API_KEY for Mira's configured VLM stage.

Queued companion track:

- Add a separate optional TRELLIS.2 GGUF service for the 16 GB RTX 5070 Ti,
  starting with the community Q5_K_M backend and retaining Q4_K_M as the
  memory-safe fallback. This is intentionally separate from the official
  BF16 TRELLIS.2 path: the upstream Gradio app is a useful UI reference, but
  the quantized path needs its own adapter and model layout.
- The service should expose a Dashboard-managed local web UI, contain outputs
  under `/home/edq/ai_generated/trellis2/`, and pass a real GLB plus clean
  stop/VRAM recovery before it becomes Mira's alternate mesh backend.
- Do not download every quant or duplicate the full BF16 TRELLIS.2 weights;
  choose one quant, validate it, then add higher-quality variants only if the
  first pass is useful.

Remaining gates before Dashboard registration:

1. Finish the SAM-3D checkpoint transfer and build/import-test the selected
   mesh backend on Blackwell.
2. Provide the configured VLM credential/endpoint, run the full automatic
   segmentation, and inspect its masks/scene graph.
3. Run a real image-to-3D test, inspect the resulting GLB/scene artifact, and
   measure clean-stop VRAM recovery.
4. Only then add the service registry entry, launcher, API, UI, and health
   check. Until those gates pass, this note is intentionally not a claim that
   Mira-Scene is a usable Dashboard service.
