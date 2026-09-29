# Supra2-IMG

Supra2-IMG is a standalone 104.1M-parameter text-to-image model from
`SupraLabs/Supra2-IMG`. Dragonsuite serves its focused prompt UI on port 8070.
It produces 256×256 PNGs under `/home/edq/ai_generated/supra2-img/` with
timestamped names. The checkpoint, Flan-T5-Base encoder, and SD VAE are
downloaded explicitly by `scripts/download_supra2_img_models.sh`; the service
does not fetch model files on first launch. Generation is serialized because
the model uses the shared 16GB GPU, and the launcher declares its measured
    resource gate in `scripts/start_supra2_img.sh`.

Verification on 2026-09-28: the Dashboard launch gate passed, `/health` reported
`models_ready: true`, and both the API and browser UI generated valid 256×256
PNGs. A 50-step, CFG 3.0 API run saved
`supra2_20260928_173108_a5e6e6_a-luminous-red-fox-standing-in-a-moonlit-p.png`;
the browser acceptance run saved a second timestamped PNG. The service was
stopped through the Dashboard API after testing and port 8070 is currently
closed.

Upstream references: [model card](https://huggingface.co/SupraLabs/Supra2-IMG)
and its [inference script](https://huggingface.co/SupraLabs/Supra2-IMG/blob/main/inference.py).
