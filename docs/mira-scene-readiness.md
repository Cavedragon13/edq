# Mira-Scene readiness note

Mira-Scene remains a separate source checkout at
`/srv/containers/edq/projects/Mira-Scene` and is not registered as a Dashboard
service yet. The upstream inference guide requires five separate environments,
external CUDA-extension projects, gated SAM 3 / SAM 3D or TRELLIS.2
checkpoints, and a configured image-generation API. Its published manifests
use older CUDA/PyTorch combinations; udragon's RTX 5070 Ti standard is cu128,
so the environment bootstrap is being adapted rather than copied verbatim.

Progress on 2026-09-28:

- Private Miniforge is installed at `/srv/containers/edq/opt/miniforge3`.
- Official SAM3, SAM-3D Objects, and TRELLIS.2 source checkouts are present
  under `/srv/containers/edq/projects/`.
- Hugging Face identity and gated-read access were verified for the Mira,
  SAM3, SAM-3D Objects, and DINOv3 model families without printing the token.
- The public Mira core pipeline download is active under
  `/srv/containers/edq/models/mira-scene`; the image encoder and VAE are
  complete, with the transformer still transferring.
- All five base environment prefixes are now present under
  `/srv/containers/edq/conda_envs/` with PyTorch 2.7.1/cu128 and validated
  CUDA access.
- Segmentation, geometry, and CCM runtime dependencies are installed and
  import-checked, including the official SAM3 source, Open3D/Trimesh,
  spconv-cu120, Mira-CCM, and UniDataset.
- The explicit stage-model downloader is active for the non-gated PPD/MoGe/
  Depth-Anything stack. SAM3 weight retrieval returned a real HF 403 because
  the configured account has not yet been authorized for that gated model.

Remaining gates before Dashboard registration:

1. Authorize the configured Hugging Face account for `facebook/sam3`, then
   rerun the explicit stage-model downloader.
2. Download the selected depth and 3D-backend checkpoints via explicit
   scripts, and build/import-test the selected mesh backend on Blackwell.
3. Run a real image-to-3D test, inspect the resulting GLB/scene artifact, and
   measure clean-stop VRAM recovery.
4. Only then add the service registry entry, launcher, API, UI, and health
   check. Until those gates pass, this note is intentionally not a claim that
   Mira-Scene is a usable Dashboard service.
