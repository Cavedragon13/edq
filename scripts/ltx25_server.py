#!/usr/bin/env python3
"""LTX-2.5 — Lightricks distilled audio+video generation (port 8063).

Non-Comfy path: official Lightricks/LTX-2.5-Diffusers components with the
distilled transformer swapped for a Q3_K_M GGUF (diffusers from_single_file).

16GB-VRAM / 31GB-RAM strategy:
  1. Text encoding: Gemma 12B text encoder loaded 4-bit (bitsandbytes),
     prompt encoded, encoder freed before any big module loads.
  2. Denoising: GGUF transformer + bf16 connectors/vae/audio_vae/vocoder under
     enable_model_cpu_offload() — connectors run once pre-loop, so they make a
     single round-trip to GPU. VAE tiling bounds decode memory.
Prompt enhancement is delegated to local Ollama (gemma4-obliterated) instead of
loading Lightricks' prompt_enhancer checkpoint.
"""
import gpu_runtime  # FIRST — configures the CUDA allocator before torch import
import gc
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests as http_requests
import torch
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

PORT = 8063
COMPONENTS_DIR = "/srv/containers/edq/models/ltx25/LTX-2.5-Diffusers"
GGUF_PATH = "/srv/containers/edq/models/ltx25/LTX-2.5-Distilled-Q3_K_M.gguf"
OUTPUT_DIR = Path.home() / "ai_generated/ltx25"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "gemma4-obliterated:latest"

ENHANCE_SYSTEM = (
    "You expand short video ideas into rich cinematic prompts for a "
    "text-to-video+audio model. Describe the scene, camera, lighting, motion, "
    "and the soundscape/dialogue in one flowing paragraph under 200 words. "
    "Reply with ONLY the expanded prompt, no preamble."
)

app = FastAPI(title="LTX-2.5")

_lock = threading.Lock()
_jobs: dict = {}
_pipe = None  # cached phase-B pipeline (transformer/vae/connectors/vocoder)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def enhance_prompt(prompt: str) -> str:
    """Expand the prompt via local Ollama abliterated Gemma. Fail open."""
    try:
        r = http_requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "system": ENHANCE_SYSTEM,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 320},
            },
            timeout=120,
        )
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        return text if text else prompt
    except Exception as e:  # noqa: BLE001 — enhancement is best-effort
        _log(f"prompt enhancement unavailable ({e}); using raw prompt")
        return prompt


def encode_prompt_4bit(prompt: str, negative_prompt: str, need_negative: bool):
    """Load the Gemma text encoder in 4-bit, encode, free it, return embeds."""
    from diffusers import LTX2Pipeline
    from transformers import BitsAndBytesConfig

    index = json.load(open(f"{COMPONENTS_DIR}/model_index.json"))
    te_class_name = index["text_encoder"][1]
    import transformers as tf_mod
    te_class = getattr(tf_mod, te_class_name)

    _log(f"loading text encoder {te_class_name} in 4-bit...")
    text_encoder = te_class.from_pretrained(
        COMPONENTS_DIR,
        subfolder="text_encoder",
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        ),
        torch_dtype=torch.bfloat16,
    )
    pipe_te = LTX2Pipeline.from_pretrained(
        COMPONENTS_DIR,
        text_encoder=text_encoder,
        transformer=None,
        vae=None,
        audio_vae=None,
        vocoder=None,
        connectors=None,
        duration_head=None,
        torch_dtype=torch.bfloat16,
    )
    with torch.no_grad():
        (prompt_embeds, prompt_attention_mask,
         negative_prompt_embeds, negative_prompt_attention_mask) = pipe_te.encode_prompt(
            prompt=prompt,
            negative_prompt=negative_prompt,
            do_classifier_free_guidance=need_negative,
            device="cuda",
        )
    prompt_embeds = prompt_embeds.to("cpu")
    prompt_attention_mask = prompt_attention_mask.to("cpu")
    if negative_prompt_embeds is not None:
        negative_prompt_embeds = negative_prompt_embeds.to("cpu")
        negative_prompt_attention_mask = negative_prompt_attention_mask.to("cpu")
    del pipe_te, text_encoder
    gc.collect()
    torch.cuda.empty_cache()
    _log("text encoder freed")
    return (prompt_embeds, prompt_attention_mask,
            negative_prompt_embeds, negative_prompt_attention_mask)


def get_pipeline():
    """Load (or return cached) phase-B pipeline: GGUF transformer + bf16 aux."""
    global _pipe
    if _pipe is not None:
        return _pipe
    from diffusers import GGUFQuantizationConfig, LTX2Pipeline, LTX2VideoTransformer3DModel

    _log("loading GGUF transformer (Q3_K_M)...")
    transformer = LTX2VideoTransformer3DModel.from_single_file(
        GGUF_PATH,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        config=COMPONENTS_DIR,
        subfolder="transformer",
        torch_dtype=torch.bfloat16,
    )
    _log("loading pipeline components...")
    # tokenizer stays loaded (32MB): __call__ reads its padding_side for the
    # connectors even when prompt_embeds are supplied.
    pipe = LTX2Pipeline.from_pretrained(
        COMPONENTS_DIR,
        transformer=transformer,
        text_encoder=None,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()
    _pipe = pipe
    _log("pipeline ready")
    return _pipe


def run_generation(job_id: str, params: dict) -> None:
    from diffusers.pipelines.ltx2.utils import (
        DEFAULT_NEGATIVE_PROMPT,
        DISTILLED_SIGMA_VALUES,
    )
    from diffusers.utils import encode_video

    job = _jobs[job_id]
    try:
        with _lock:
            job["status"] = "running"
            t0 = time.time()

            prompt = params["prompt"]
            if params.get("enhance", True):
                job["stage"] = "enhancing prompt (Ollama)"
                prompt = enhance_prompt(prompt)
                job["enhanced_prompt"] = prompt

            negative = params.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT
            guidance_scale = float(params.get("guidance_scale", 1.0))
            need_negative = guidance_scale > 1.0

            job["stage"] = "encoding prompt (4-bit Gemma)"
            with gpu_runtime.oom_guard("text encoding"):
                (pe, pam, npe, npam) = encode_prompt_4bit(prompt, negative, need_negative)

            job["stage"] = "loading pipeline"
            pipe = get_pipeline()

            job["stage"] = "denoising"
            seed = int(params.get("seed") or torch.seed() % (2**31))
            job["seed"] = seed
            generator = torch.Generator(device="cuda").manual_seed(seed)

            with gpu_runtime.oom_guard("video generation"), torch.no_grad():
                out = pipe(
                    prompt_embeds=pe.to("cuda"),
                    prompt_attention_mask=pam.to("cuda"),
                    negative_prompt_embeds=npe.to("cuda") if npe is not None else None,
                    negative_prompt_attention_mask=npam.to("cuda") if npam is not None else None,
                    width=int(params.get("width", 960)),
                    height=int(params.get("height", 544)),
                    num_frames=int(params.get("num_frames", 121)),
                    frame_rate=24.0,
                    sigmas=DISTILLED_SIGMA_VALUES,
                    guidance_scale=guidance_scale,
                    generator=generator,
                    output_type="pil",
                )
            frames = out.frames[0]
            audio = out.audio[0] if out.audio is not None else None

            job["stage"] = "encoding mp4"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = OUTPUT_DIR / f"ltx25_{ts}.mp4"
            kwargs = {}
            if audio is not None:
                kwargs = {
                    "audio": audio.float().cpu(),
                    "audio_sample_rate": pipe.vocoder.config.output_sampling_rate,
                }
            encode_video(frames, fps=24, output_path=str(out_path), **kwargs)

            meta = {
                "file": out_path.name,
                "prompt": params["prompt"],
                "enhanced_prompt": job.get("enhanced_prompt"),
                "seed": seed,
                "width": params.get("width", 960),
                "height": params.get("height", 544),
                "num_frames": params.get("num_frames", 121),
                "seconds": round(time.time() - t0, 1),
                "timestamp": ts,
            }
            (OUTPUT_DIR / "latest.json").write_text(json.dumps(meta, indent=2))
            job.update(status="done", file=out_path.name, meta=meta,
                       stage="done", seconds=meta["seconds"])
            _log(f"done in {meta['seconds']}s -> {out_path}")
    except RuntimeError as e:
        job.update(status="error", error=str(e), stage="failed")
        _log(f"generation failed: {e}")
    except Exception as e:  # noqa: BLE001
        job.update(status="error", error=f"{type(e).__name__}: {e}", stage="failed")
        _log(f"generation failed: {type(e).__name__}: {e}")


@app.post("/api/generate")
async def api_generate(request: Request):
    params = await request.json()
    if not params.get("prompt", "").strip():
        return JSONResponse(status_code=400, content={"error": "prompt required"})
    if _lock.locked():
        return JSONResponse(status_code=409, content={"error": "a generation is already running"})
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "queued", "stage": "queued", "params": params}
    threading.Thread(target=run_generation, args=(job_id, params), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "unknown job"})
    return {k: v for k, v in job.items() if k != "params"}


@app.get("/api/outputs")
def api_outputs():
    files = sorted(OUTPUT_DIR.glob("ltx25_*.mp4"), reverse=True)[:50]
    return [{"file": f.name, "size_mb": round(f.stat().st_size / 1e6, 1)} for f in files]


@app.get("/outputs/{name}")
def get_output(name: str):
    path = OUTPUT_DIR / Path(name).name
    if not path.is_file():
        return JSONResponse(status_code=404, content={"error": "not found"})
    return FileResponse(path, media_type="video/mp4")


@app.post("/api/unload")
def api_unload():
    global _pipe
    if _lock.locked():
        return JSONResponse(status_code=409, content={"error": "generation running"})
    _pipe = None
    gc.collect()
    torch.cuda.empty_cache()
    return {"status": "unloaded"}


@app.get("/api/status")
def api_status():
    vram_used = vram_total = 0
    if torch.cuda.is_available():
        free_b, total_b = torch.cuda.mem_get_info()
        vram_used, vram_total = (total_b - free_b) // 2**20, total_b // 2**20
    return {
        "service": "LTX-2.5",
        "pipeline_loaded": _pipe is not None,
        "busy": _lock.locked(),
        "vram_used_mib": vram_used,
        "vram_total_mib": vram_total,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LTX-2.5 — Audio+Video Generation</title>
<style>
:root { --bg:#f5f5f5; --panel:#ffffff; --text:#222; --muted:#666; --border:#ccc; --accent:#7c5cff; }
html.dark { --bg:#1e1e1e; --panel:#2d2d2d; --text:#e0e0e0; --muted:#9a9a9a; --border:#4a5568; }
* { box-sizing:border-box; transition: background 0.3s ease, color 0.3s ease, border-color 0.3s ease; }
body { margin:0; font-family:system-ui,sans-serif; background:var(--bg); color:var(--text); }
header { display:flex; align-items:center; justify-content:space-between; padding:14px 22px; border-bottom:1px solid var(--border); }
h1 { font-size:1.2rem; margin:0; } h1 span { color:var(--accent); }
#themeToggle { width:38px; height:38px; border-radius:50%; border:1px solid var(--border); background:var(--panel); color:var(--text); cursor:pointer; font-size:1.1rem; }
#themeToggle:hover { transform:rotate(30deg); }
main { max-width:1100px; margin:0 auto; padding:20px; display:grid; grid-template-columns:380px 1fr; gap:20px; }
@media (max-width:900px){ main { grid-template-columns:1fr; } }
.panel { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:18px; }
label { display:block; font-size:0.8rem; color:var(--muted); margin:12px 0 4px; }
textarea, input, select { width:100%; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:8px; font-family:inherit; font-size:0.9rem; }
textarea { resize:vertical; min-height:90px; }
.row { display:flex; gap:10px; } .row > div { flex:1; }
.check { display:flex; align-items:center; gap:8px; margin-top:14px; font-size:0.9rem; }
.check input { width:auto; }
button.primary { width:100%; margin-top:16px; padding:12px; background:var(--accent); color:#fff; border:none; border-radius:8px; font-size:1rem; cursor:pointer; }
button.primary:disabled { opacity:0.5; cursor:wait; }
#stage { margin-top:12px; font-size:0.85rem; color:var(--muted); min-height:1.2em; }
video { width:100%; border-radius:8px; background:#000; }
.gallery { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; margin-top:14px; }
.gallery video { cursor:pointer; }
.small { font-size:0.75rem; color:var(--muted); word-break:break-all; }
</style>
</head>
<body>
<header>
  <h1>🎬 LTX-<span>2.5</span> <small style="color:var(--muted);font-weight:normal">distilled · audio+video · GGUF</small></h1>
  <button id="themeToggle" title="Toggle theme">🌙</button>
</header>
<main>
  <div class="panel">
    <label>Prompt</label>
    <textarea id="prompt" placeholder="A dragon soars over a misty volcanic ridge at dawn, wings thundering..."></textarea>
    <label>Negative prompt (blank = model default)</label>
    <textarea id="negative" style="min-height:50px"></textarea>
    <div class="row">
      <div><label>Resolution</label>
        <select id="res">
          <option value="960x544" selected>960 × 544 (wide)</option>
          <option value="768x512">768 × 512</option>
          <option value="544x960">544 × 960 (vertical)</option>
          <option value="704x480">704 × 480 (light)</option>
        </select></div>
      <div><label>Length</label>
        <select id="frames">
          <option value="121" selected>5s (121f)</option>
          <option value="97">4s (97f)</option>
          <option value="73">3s (73f)</option>
          <option value="49">2s (49f)</option>
        </select></div>
    </div>
    <div class="row">
      <div><label>Seed (blank = random)</label><input id="seed" type="number" placeholder="random"></div>
    </div>
    <div class="check">
      <input type="checkbox" id="enhance" checked>
      <label for="enhance" style="margin:0">Enhance prompt (local Gemma, uncensored)</label>
    </div>
    <button class="primary" id="go">Generate</button>
    <div id="stage"></div>
  </div>
  <div class="panel">
    <video id="player" controls></video>
    <div id="meta" class="small"></div>
    <div class="gallery" id="gallery"></div>
  </div>
</main>
<script>
const root = document.documentElement, tt = document.getElementById('themeToggle');
function setTheme(d){ root.classList.toggle('dark', d); tt.textContent = d ? '☀️' : '🌙'; localStorage.setItem('ltx25theme', d ? 'dark' : 'light'); }
setTheme((localStorage.getItem('ltx25theme') || 'dark') === 'dark');
tt.onclick = () => setTheme(!root.classList.contains('dark'));

const $ = id => document.getElementById(id);
async function refreshGallery(){
  const files = await (await fetch('/api/outputs')).json();
  $('gallery').innerHTML = files.map(f =>
    `<video src="/outputs/${f.file}" muted onclick="play('${f.file}')" title="${f.file}"></video>`).join('');
}
function play(f){ $('player').src = '/outputs/' + f; $('player').play(); $('meta').textContent = f; }

$('go').onclick = async () => {
  const [w,h] = $('res').value.split('x').map(Number);
  const body = {
    prompt: $('prompt').value, negative_prompt: $('negative').value,
    width: w, height: h, num_frames: Number($('frames').value),
    enhance: $('enhance').checked,
  };
  if ($('seed').value) body.seed = Number($('seed').value);
  $('go').disabled = true; $('stage').textContent = 'submitting...';
  const r = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (!r.ok){ $('stage').textContent = j.error; $('go').disabled = false; return; }
  const timer = setInterval(async () => {
    const job = await (await fetch('/api/jobs/' + j.job_id)).json();
    $('stage').textContent = job.stage + (job.status === 'error' ? ': ' + job.error : '');
    if (job.status === 'done'){ clearInterval(timer); $('go').disabled = false; play(job.file); refreshGallery();
      $('meta').textContent = `${job.file} — seed ${job.seed} — ${job.seconds}s`; }
    if (job.status === 'error'){ clearInterval(timer); $('go').disabled = false; }
  }, 2000);
};
refreshGallery();
</script>
</body>
</html>"""


if __name__ == "__main__":
    _log(f"LTX-2.5 server starting on :{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
