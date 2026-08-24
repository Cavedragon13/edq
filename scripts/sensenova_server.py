"""SenseNova-U1.5-8B-MoT — Gradio T2I server (GGUF + layer-offload, 16GB card)."""

import gpu_runtime  # noqa: F401  (FIRST — configures the CUDA allocator before torch import)
import argparse
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr
import numpy as np
import torch
from PIL import Image

REPO_SRC = "/srv/containers/edq/projects/SenseNova-U1/src"
if REPO_SRC not in sys.path:
    sys.path.insert(0, REPO_SRC)

import sensenova_u1  # noqa: E402
from sensenova_u1.utils import (  # noqa: E402
    load_model_and_tokenizer,
    make_offload_ctx,
    vram_mode_keeps_generation_resident,
    vram_mode_to_prefetch_count,
)

MODEL_PATH = "/srv/containers/edq/models/sensenova-u1.5"
GGUF_CHECKPOINT = "/srv/containers/edq/models/sensenova-u1.5/gguf/SenseNova-U1.5-8B-MoT-Preview-Q8.gguf"
OUTPUT_DIR = Path("/home/edq/ai_generated/sensenova")
VRAM_MODE = "balanced"
FAST_VRAM_BUDGET_GIB = 12.0

NORM_MEAN = (0.5, 0.5, 0.5)
NORM_STD = (0.5, 0.5, 0.5)

RESOLUTIONS = {
    "1:1 (2048x2048)": (2048, 2048),
    "16:9 (2720x1536)": (2720, 1536),
    "9:16 (1536x2720)": (1536, 2720),
    "3:2 (2496x1664)": (2496, 1664),
    "2:3 (1664x2496)": (1664, 2496),
    "4:3 (2368x1760)": (2368, 1760),
    "3:4 (1760x2368)": (1760, 2368),
}


def _denorm(x: torch.Tensor) -> torch.Tensor:
    mean = torch.tensor(NORM_MEAN, device=x.device, dtype=x.dtype).view(1, 3, 1, 1)
    std = torch.tensor(NORM_STD, device=x.device, dtype=x.dtype).view(1, 3, 1, 1)
    return (x * std + mean).clamp(0, 1)


def _to_pil(batch: torch.Tensor) -> list[Image.Image]:
    arr = _denorm(batch.float()).permute(0, 2, 3, 1).cpu().numpy()
    arr = (arr * 255.0).round().astype(np.uint8)
    return [Image.fromarray(a) for a in arr]


class Engine:
    def __init__(self):
        print(f"[sensenova] loading config/tokenizer from {MODEL_PATH}")
        print(f"[sensenova] GGUF checkpoint: {GGUF_CHECKPOINT}")
        print(f"[sensenova] vram_mode={VRAM_MODE} fast_vram_budget_gib={FAST_VRAM_BUDGET_GIB}")
        self.prefetch_count = vram_mode_to_prefetch_count(VRAM_MODE)
        self.model, self.tokenizer = load_model_and_tokenizer(
            MODEL_PATH,
            dtype=torch.bfloat16,
            device="cuda",
            gguf_checkpoint=GGUF_CHECKPOINT,
            for_offload=self.prefetch_count > 0,
        )
        print("[sensenova] model loaded")

    def _offload_ctx(self):
        return make_offload_ctx(
            self.model,
            self.prefetch_count,
            "cuda",
            keep_generation_resident=vram_mode_keeps_generation_resident(VRAM_MODE),
            fast_vram_budget_gib=FAST_VRAM_BUDGET_GIB,
        )

    @torch.inference_mode()
    def generate(self, prompt: str, resolution_label: str, cfg_scale: float, num_steps: int, seed: int):
        width, height = RESOLUTIONS[resolution_label]
        with self._offload_ctx() as offloaded:
            out = offloaded.t2i_generate(
                self.tokenizer,
                prompt,
                image_size=(width, height),
                cfg_scale=cfg_scale,
                cfg_norm="none",
                timestep_shift=3.0,
                cfg_interval=(0.0, 1.0),
                num_steps=int(num_steps),
                batch_size=1,
                seed=int(seed),
                think_mode=False,
            )
        return _to_pil(out)[0]


engine: Engine | None = None


def get_engine() -> Engine:
    global engine
    if engine is None:
        engine = Engine()
    return engine


def ui_generate(prompt, resolution_label, cfg_scale, num_steps, seed):
    if not prompt or not prompt.strip():
        raise gr.Error("Enter a prompt first.")
    try:
        with gpu_runtime.oom_guard("SenseNova-U1.5 T2I generation"):
            image = get_engine().generate(prompt, resolution_label, cfg_scale, num_steps, seed)
    except RuntimeError as e:
        raise gr.Error(str(e))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"sensenova_{ts}.png"
    image.save(out_path)
    image.save(OUTPUT_DIR / "latest.png")
    return image, str(out_path)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="SenseNova-U1.5-8B-MoT", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# SenseNova-U1.5-8B-MoT — Native Unified Multimodal (T2I)")
        with gr.Row():
            with gr.Column():
                prompt = gr.Textbox(label="Prompt", lines=4, placeholder="Describe the image...")
                resolution = gr.Dropdown(choices=list(RESOLUTIONS.keys()), value="1:1 (2048x2048)", label="Resolution")
                cfg_scale = gr.Slider(1.0, 10.0, value=4.0, step=0.1, label="CFG Scale")
                num_steps = gr.Slider(10, 100, value=50, step=1, label="Steps")
                seed = gr.Number(value=42, precision=0, label="Seed")
                run_btn = gr.Button("Generate", variant="primary")
            with gr.Column():
                image_out = gr.Image(label="Result", type="pil")
                path_out = gr.Textbox(label="Saved to", interactive=False)
        run_btn.click(ui_generate, [prompt, resolution, cfg_scale, num_steps, seed], [image_out, path_out])
    return demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8048)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    sensenova_u1.set_attn_backend("auto")
    demo = build_ui()
    demo.queue(max_size=4).launch(
        server_name=args.host,
        server_port=args.port,
        allowed_paths=[str(OUTPUT_DIR)],
    )


if __name__ == "__main__":
    main()
