#!/usr/bin/env python3
"""
Small local Krea 2 runner.

This wraps stable-diffusion.cpp's sd-cli with a tiny HTTP UI/API so the
Dragonsuite dashboard can start and open it as a normal service.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import base64
import binascii
from html import escape as html_escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


APP_ROOT = Path(os.environ.get("KREA2_HOME", Path.home() / ".local/share/krea2"))
MODEL_DIR = Path(os.environ.get("KREA2_MODEL_DIR", APP_ROOT / "models"))
OUTPUT_DIR = Path(os.environ.get("KREA2_OUTPUT_DIR", APP_ROOT / "outputs"))
LOG_DIR = Path(os.environ.get("KREA2_LOG_DIR", APP_ROOT / "logs"))
LORA_DIR = Path(os.environ.get("KREA2_LORA_DIR", APP_ROOT / "loras"))
LORA_MANIFEST = Path(os.environ.get("KREA2_LORA_MANIFEST", LORA_DIR / "manifest.json"))
SD_CLI = Path(
    os.environ.get(
        "KREA2_SD_CLI",
        APP_ROOT / "src/stable-diffusion.cpp/build/bin/sd-cli",
    )
)

DIFFUSION_MODEL = Path(
    os.environ.get(
        "KREA2_DIFFUSION_MODEL",
        MODEL_DIR / "TURBO/Krea-2-Turbo-Q4_K_M.gguf",
    )
)
LLM_MODEL = Path(
    os.environ.get(
        "KREA2_LLM_MODEL",
        MODEL_DIR / "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
    )
)
VAE_MODEL = Path(
    os.environ.get(
        "KREA2_VAE_MODEL",
        MODEL_DIR / "split_files/vae/wan_2.1_vae.safetensors",
    )
)

HOST = os.environ.get("KREA2_HOST", "127.0.0.1")
PORT = int(os.environ.get("KREA2_PORT", "8062"))
TIMEOUT_SECONDS = int(os.environ.get("KREA2_TIMEOUT", "1800"))
BACKEND_ASSIGNMENT = os.environ.get("KREA2_BACKEND", "vae=cpu").strip()
LORA_EXTENSIONS = {".safetensors", ".pt", ".gguf"}
LORA_APPLY_MODES = {"auto", "immediately", "at_runtime"}
INIT_IMAGE_DIR = LOG_DIR / "inputs"
MAX_INIT_IMAGE_BYTES = 20 * 1024 * 1024

GENERATE_LOCK = threading.Lock()
LAST_RUN: dict = {}

signal.signal(signal.SIGPIPE, signal.SIG_IGN)


def human_size(path: Path) -> str:
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} GB"


def file_info(label: str, path: Path) -> dict:
    return {
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "size": human_size(path),
    }


def newest_output() -> str | None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(OUTPUT_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0].name if files else None


def load_lora_manifest() -> dict:
    if not LORA_MANIFEST.exists():
        return {"official": []}
    try:
        data = json.loads(LORA_MANIFEST.read_text())
    except Exception:
        return {"official": []}
    if not isinstance(data, dict):
        return {"official": []}
    data.setdefault("official", [])
    return data


def lora_tag_for_path(path: Path) -> str:
    rel = path.relative_to(LORA_DIR).as_posix()
    suffix = path.suffix
    return rel[: -len(suffix)] if suffix else rel


def list_loras() -> list[dict]:
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_lora_manifest()
    known_by_file = {}
    known_by_tag = {}
    for item in manifest.get("official", []):
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip()
        tag = str(item.get("tag") or Path(filename).stem).strip()
        if filename:
            known_by_file[filename] = item
        if tag:
            known_by_tag[tag] = item

    loras = []
    for path in sorted(
        LORA_DIR.rglob("*"),
        key=lambda p: (p.name.lower(), p.relative_to(LORA_DIR).as_posix().lower()),
    ):
        if not path.is_file() or path.suffix.lower() not in LORA_EXTENSIONS:
            continue
        rel = path.relative_to(LORA_DIR).as_posix()
        tag = lora_tag_for_path(path)
        meta = known_by_file.get(rel) or known_by_file.get(path.name) or known_by_tag.get(tag) or {}
        loras.append(
            {
                "name": str(meta.get("name") or Path(rel).stem),
                "tag": tag,
                "filename": rel,
                "path": str(path),
                "size": human_size(path),
                "repo_id": meta.get("repo_id"),
                "trigger": meta.get("trigger", ""),
            }
        )
    return loras


def status_payload() -> dict:
    items = [
        file_info("sd-cli", SD_CLI),
        file_info("Krea 2 Turbo", DIFFUSION_MODEL),
        file_info("Qwen3-VL text encoder", LLM_MODEL),
        file_info("Wan 2.1 VAE", VAE_MODEL),
    ]
    loras = list_loras()
    return {
        "ready": all(item["exists"] for item in items),
        "busy": GENERATE_LOCK.locked(),
        "host": HOST,
        "port": PORT,
        "models": items,
        "output_dir": str(OUTPUT_DIR),
        "log_dir": str(LOG_DIR),
        "latest_output": newest_output(),
        "last_run": LAST_RUN,
        "free_disk": shutil.disk_usage(str(APP_ROOT)).free,
        "backend": BACKEND_ASSIGNMENT or "default",
        "lora_dir": str(LORA_DIR),
        "lora_count": len(loras),
        "loras": loras,
        "known_loras": load_lora_manifest().get("official", []),
    }


def clamp_int(value, default: int, low: int, high: int) -> int:
    try:
        value = int(value)
    except Exception:
        return default
    return max(low, min(high, value))


def clamp_float(value, default: float, low: float, high: float) -> float:
    try:
        value = float(value)
    except Exception:
        return default
    return max(low, min(high, value))


def sanitize_filename_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._")
    return token[:64] or "lora"


def has_init_image(payload: dict) -> bool:
    image = payload.get("init_image")
    return isinstance(image, dict) and bool(str(image.get("data_url") or "").strip())


def batch_count_for_payload(payload: dict, img2img: bool = False) -> int:
    return clamp_int(payload.get("batch_count"), 1, 1, 2 if img2img else 4)


def save_init_image(payload: dict, stamp: str) -> Path | None:
    image = payload.get("init_image")
    if not isinstance(image, dict):
        return None
    data_url = str(image.get("data_url") or "").strip()
    if not data_url:
        return None

    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("Source image must be a PNG, JPEG, or WebP data URL.")

    suffix = "jpg" if match.group(1) in {"jpeg", "jpg"} else match.group(1)
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except binascii.Error as exc:
        raise ValueError("Source image data is not valid base64.") from exc

    if not raw:
        raise ValueError("Source image is empty.")
    if len(raw) > MAX_INIT_IMAGE_BYTES:
        raise ValueError("Source image is too large. Limit is 20 MB.")

    INIT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = INIT_IMAGE_DIR / f"krea2-{stamp}-init.{suffix}"
    path.write_bytes(raw)
    return path


def payload_loras(payload: dict) -> list[dict]:
    available = {item["tag"]: item for item in list_loras()}
    requested = payload.get("loras")
    selected: list[dict] = []

    if isinstance(requested, list):
        for entry in requested:
            if not isinstance(entry, dict):
                continue
            tag = str(entry.get("tag") or entry.get("name") or "").strip()
            if not tag or tag.lower() == "none":
                continue
            if tag not in available:
                raise ValueError(f"Selected LoRA is not installed: {tag}")
            weight = clamp_float(entry.get("weight"), 1.0, 0.0, 2.0)
            item = dict(available[tag])
            item["weight"] = weight
            selected.append(item)
        return selected

    selected_tag = str(payload.get("lora_name") or "").strip()
    if selected_tag and selected_tag.lower() != "none":
        if selected_tag not in available:
            raise ValueError(f"Selected LoRA is not installed: {selected_tag}")
        weight = clamp_float(payload.get("lora_weight"), 1.0, 0.0, 2.0)
        item = dict(available[selected_tag])
        item["weight"] = weight
        selected.append(item)

    return selected


def lora_prompt(payload: dict, prompt: str) -> tuple[str, list[dict]]:
    loras_used = payload_loras(payload)
    for item in loras_used:
        prompt += f"<lora:{item['tag']}:{item['weight']:g}>"

    custom_tags = str(payload.get("custom_lora_tags") or "").strip()
    if custom_tags:
        if len(custom_tags) > 500:
            raise ValueError("Extra LoRA tags are too long.")
        prompt += custom_tags
        loras_used.append({"name": "Custom prompt tags", "tag": custom_tags, "weight": None})

    return prompt, loras_used


def build_command(payload: dict, out_path: Path, init_image_path: Path | None = None) -> list[str]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt is required.")
    prompt, _loras_used = lora_prompt(payload, prompt)

    width = clamp_int(payload.get("width"), 1024, 256, 1536)
    height = clamp_int(payload.get("height"), 1024, 256, 1536)
    width = (width // 64) * 64
    height = (height // 64) * 64
    steps = clamp_int(payload.get("steps"), 8, 1, 24)
    seed = clamp_int(payload.get("seed"), -1, -1, 2147483647)
    batch_count = batch_count_for_payload(payload, img2img=init_image_path is not None)
    cfg = clamp_float(payload.get("cfg_scale"), 1.0, 0.0, 20.0)
    flow_shift = clamp_float(payload.get("flow_shift"), 1.15, 0.0, 10.0)
    sampler = str(payload.get("sampler") or "euler").strip()
    lora_apply_mode = str(payload.get("lora_apply_mode") or "auto").strip()
    if lora_apply_mode not in LORA_APPLY_MODES:
        lora_apply_mode = "auto"

    cmd = [
        str(SD_CLI),
        "--diffusion-model",
        str(DIFFUSION_MODEL),
        "--llm",
        str(LLM_MODEL),
        "--vae",
        str(VAE_MODEL),
        "--lora-model-dir",
        str(LORA_DIR),
        "--lora-apply-mode",
        lora_apply_mode,
        "-p",
        prompt,
        "--steps",
        str(steps),
        "--batch-count",
        str(batch_count),
        "--cfg-scale",
        str(cfg),
        "--flow-shift",
        str(flow_shift),
        "--sampling-method",
        sampler,
        "-W",
        str(width),
        "-H",
        str(height),
        "-s",
        str(seed),
        "--diffusion-fa",
        "--offload-to-cpu",
        "--vae-tiling",
        "--mmap",
        "-o",
        str(out_path),
    ]

    if init_image_path:
        strength = clamp_float(payload.get("strength"), 0.55, 0.0, 1.0)
        cmd.extend(["-i", str(init_image_path), "--strength", str(strength)])

    if BACKEND_ASSIGNMENT:
        cmd[cmd.index("-W"):cmd.index("-W")] = ["--backend", BACKEND_ASSIGNMENT]

    extra = os.environ.get("KREA2_EXTRA_ARGS", "").strip()
    if extra:
        cmd.extend(shlex.split(extra))
    return cmd


def expected_output_paths(out_path: Path, batch_count: int) -> list[Path]:
    if batch_count <= 1:
        return [out_path]
    return [out_path.with_name(f"{out_path.stem}_{idx}{out_path.suffix}") for idx in range(batch_count)]


def run_generation(payload: dict) -> dict:
    global LAST_RUN
    if not status_payload()["ready"]:
        raise RuntimeError("Krea 2 is not ready. One or more model files are missing.")

    if not GENERATE_LOCK.acquire(blocking=False):
        raise RuntimeError("A generation is already running.")

    started = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    init_image_path = save_init_image(payload, stamp)
    img2img = init_image_path is not None
    batch_count = batch_count_for_payload(payload, img2img=img2img)
    _prompt_with_loras, loras_used = lora_prompt(payload, str(payload.get("prompt") or "").strip())
    lora_suffix = ""
    if loras_used:
        suffix_tags = "-".join(sanitize_filename_token(item["tag"]) for item in loras_used[:3])
        lora_suffix = "-lora-" + suffix_tags
    if img2img:
        lora_suffix += "-i2i"
    out_path = OUTPUT_DIR / f"krea2-{stamp}{lora_suffix}.png"
    log_path = LOG_DIR / f"krea2-{stamp}.log"
    cmd = build_command(payload, out_path, init_image_path)

    LAST_RUN = {
        "status": "running",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "output": str(out_path),
        "log": str(log_path),
        "loras": loras_used,
        "mode": "img2img" if img2img else "txt2img",
        "init_image": str(init_image_path) if init_image_path else None,
        "batch_count": batch_count,
    }

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        log_path.write_text(
            "$ " + " ".join(shlex.quote(x) for x in cmd) + "\n\n"
            + "STDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
            errors="replace",
        )
        elapsed = round(time.time() - started, 1)
        if proc.returncode != 0:
            LAST_RUN = {
                "status": "error",
                "returncode": proc.returncode,
                "elapsed_seconds": elapsed,
                "log": str(log_path),
                "loras": loras_used,
                "mode": "img2img" if img2img else "txt2img",
                "init_image": str(init_image_path) if init_image_path else None,
            }
            raise RuntimeError(f"sd-cli failed with exit code {proc.returncode}.")
        output_paths = [path for path in expected_output_paths(out_path, batch_count) if path.exists()]
        if not output_paths:
            raise RuntimeError("sd-cli completed but no output image was written.")
        image_urls = ["/outputs/" + path.name for path in output_paths]
        LAST_RUN = {
            "status": "ok",
            "elapsed_seconds": elapsed,
            "output": str(output_paths[0]),
            "outputs": [str(path) for path in output_paths],
            "log": str(log_path),
            "loras": loras_used,
            "batch_count": batch_count,
            "mode": "img2img" if img2img else "txt2img",
            "init_image": str(init_image_path) if init_image_path else None,
        }
        return {
            "ok": True,
            "elapsed_seconds": elapsed,
            "image_url": image_urls[0],
            "image_urls": image_urls,
            "log": str(log_path),
            "loras": loras_used,
            "batch_count": batch_count,
            "mode": "img2img" if img2img else "txt2img",
        }
    finally:
        GENERATE_LOCK.release()


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Krea 2 Turbo</title>
<style>
:root{color-scheme:dark;--bg:#080e1c;--panel:#0e1828;--line:rgba(34,211,238,.16);--text:#d8e8f4;--muted:#7b9bb2;--accent:#22d3ee;--ok:#34d399;--bad:#f87171}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Manrope,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px}header{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:18px}
h1{font-size:22px;letter-spacing:.08em;text-transform:uppercase;margin:0}p{color:var(--muted);margin:6px 0 0}
.grid{display:grid;grid-template-columns:minmax(360px,460px) 1fr;gap:16px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px}
label{display:block;color:var(--muted);font-size:12px;margin:12px 0 6px}textarea,input,select{width:100%;background:#08111f;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit}
textarea{min-height:132px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.actions{display:flex;align-items:center;gap:10px;margin:12px 0 4px}
button,.link-button{background:var(--accent);color:#041018;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;min-height:40px}button.secondary,.link-button.secondary{background:#16253a;color:var(--text);border:1px solid var(--line)}button.small{padding:8px 10px;min-height:36px}button:disabled{opacity:.5;cursor:wait}
.status{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted);display:grid;gap:6px}.status b{color:var(--text)}.ok{color:var(--ok)}.bad{color:var(--bad)}
.section-title{margin:18px 0 4px;color:var(--text);font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.mini{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45;overflow-wrap:anywhere}.mini a{color:var(--accent)}
.lora-row{display:grid;grid-template-columns:minmax(0,1fr) 84px auto;gap:8px;align-items:end;margin-top:8px}.empty-loras{color:var(--muted);font-size:13px;padding:10px 0}.compact{margin-top:8px}details{border-top:1px solid var(--line);margin-top:16px;padding-top:10px}summary{cursor:pointer;color:var(--muted);font-weight:700}
.source-preview{display:none;grid-template-columns:86px 1fr;gap:10px;align-items:center;margin-top:10px;color:var(--muted);font-size:12px}.source-preview img{width:86px;height:86px;object-fit:cover;border-radius:8px;border:1px solid var(--line)}.range-row{display:grid;grid-template-columns:1fr 48px;gap:10px;align-items:center}.range-row output{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text)}
.preview{min-height:560px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));align-items:center;justify-items:center;gap:10px;background:#050a13;border:1px solid var(--line);border-radius:8px;overflow:hidden;padding:10px}.preview.single{display:flex}.preview img{max-width:100%;height:auto;display:block;border-radius:6px}
.msg{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);font-size:12px;margin-top:12px;white-space:pre-wrap}
@media(max-width:860px){.grid{grid-template-columns:1fr}main{padding:14px}.preview{min-height:320px}.lora-row{grid-template-columns:1fr 82px auto}}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Krea 2 Turbo</h1>
      <p>Local runner via stable-diffusion.cpp.</p>
    </div>
    <button id="refresh">Refresh</button>
  </header>
  <div class="grid">
    <section class="panel">
      <div class="status" id="status">Loading status...</div>
      <label for="prompt">Prompt</label>
      <textarea id="prompt">a luminous glass dragon-shaped observatory above a moonlit harbor, precise architectural detail, cinematic realism</textarea>
      <div class="actions">
        <button id="generate">Generate</button>
        <button id="refreshLoras" class="secondary" type="button">Refresh LoRAs</button>
        <button id="copyLoraPath" class="secondary" type="button">Copy LoRAs Path</button>
      </div>
      <div class="msg" id="msg"></div>
      <div class="section-title">Source Image</div>
      <div class="row">
        <div><label for="initImage">Image</label><input id="initImage" type="file" accept="image/png,image/jpeg,image/webp"></div>
        <div><label for="strength">Strength</label><div class="range-row"><input id="strength" type="range" value="0.55" min="0" max="1" step="0.05"><output id="strengthValue">0.55</output></div></div>
      </div>
      <div class="actions">
        <button id="matchInitSize" class="secondary" type="button" disabled>Match Size</button>
        <button id="clearInitImage" class="secondary" type="button" disabled>Clear Image</button>
      </div>
      <div class="source-preview" id="sourcePreview"></div>
      <div class="section-title">LoRAs</div>
      <div id="loraRows"></div>
      <button id="addLora" class="secondary compact" type="button">Add LoRA</button>
      <div class="mini" id="loraStatus"></div>
      <label for="aspect">Aspect ratio</label>
      <select id="aspect">
        <option value="1024x1024">Square 1:1 · 1024x1024</option>
        <option value="1152x896">Landscape 4:3 · 1152x896</option>
        <option value="1344x768">Wide 16:9 · 1344x768</option>
        <option value="896x1152">Portrait 3:4 · 896x1152</option>
        <option value="768x1344">Tall 9:16 · 768x1344</option>
        <option value="1536x640">Panorama · 1536x640</option>
        <option value="custom">Custom</option>
      </select>
      <div class="row">
        <div><label for="width">Width</label><input id="width" type="number" value="1024" min="256" max="1536" step="64"></div>
        <div><label for="height">Height</label><input id="height" type="number" value="1024" min="256" max="1536" step="64"></div>
      </div>
      <div class="row">
        <div><label for="steps">Steps</label><input id="steps" type="number" value="8" min="1" max="24"></div>
        <div><label for="batchCount">Outputs</label><select id="batchCount"><option value="1">1 image</option><option value="2">2 images</option><option value="3">3 images</option><option value="4">4 images</option></select></div>
      </div>
      <div class="row">
        <div><label for="seed">Seed</label><input id="seed" type="number" value="-1"></div>
        <div></div>
      </div>
      <div class="row">
        <div><label for="cfg">CFG</label><input id="cfg" type="number" value="1" min="0" max="20" step="0.1"></div>
        <div><label for="shift">Flow shift</label><input id="shift" type="number" value="1.15" min="0" max="10" step="0.05"></div>
      </div>
      <details>
        <summary>Advanced</summary>
        <label for="sampler">Sampler</label>
        <select id="sampler"><option value="euler">euler</option><option value="dpm++2m">dpm++2m</option><option value="res_multistep">res_multistep</option></select>
        <label for="loraMode">LoRA apply mode</label>
        <select id="loraMode"><option value="auto">auto</option><option value="at_runtime">at_runtime</option><option value="immediately">immediately</option></select>
        <label for="customLora">Manual LoRA tags</label>
        <input id="customLora" type="text" placeholder="<lora:name:1>">
      </details>
    </section>
    <section class="panel">
      <div class="preview" id="preview">Generated image will appear here.</div>
    </section>
  </div>
</main>
<script>
async function json(url, opts){ const r=await fetch(url,opts); const t=await r.text(); let d={}; try{d=JSON.parse(t)}catch{d={error:t}} if(!r.ok) throw new Error(d.error||d.detail||t||r.statusText); return d; }
function qs(id){ return document.getElementById(id); }
function esc(s){ return String(s||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
let loraCatalog=[];
let selectedLoras=[];
let sourceImage=null;
let loraDirPath='';
async function refresh(){
  const d=await json('/api/status');
  const missing=d.models.filter(m=>!m.exists).map(m=>m.label);
  qs('status').innerHTML='<div>Ready: <b class="'+(d.ready?'ok':'bad')+'">'+d.ready+'</b> · Busy: <b>'+d.busy+'</b> · LoRAs: <b>'+d.lora_count+'</b></div>'+
    (missing.length?'<div class="bad">Missing: '+esc(missing.join(', '))+'</div>':'')+
    (d.latest_output?'<div>Latest: <a href="/outputs/'+d.latest_output+'" target="_blank">'+esc(d.latest_output)+'</a></div>':'');
}
function renderLoraRows(){
  const rows=qs('loraRows');
  if(!selectedLoras.length){
    rows.innerHTML='<div class="empty-loras">No LoRA selected.</div>';
    return;
  }
  const options=['<option value="">None</option>'].concat(loraCatalog.map(l=>'<option value="'+esc(l.tag)+'">'+esc(l.name)+' · '+esc(l.size)+'</option>')).join('');
  rows.innerHTML=selectedLoras.map((item,i)=>
    '<div class="lora-row" data-index="'+i+'">'+
      '<div><label>Installed LoRA</label><select data-role="tag">'+options+'</select></div>'+
      '<div><label>Weight</label><input data-role="weight" type="number" value="'+esc(item.weight ?? 1)+'" min="0" max="2" step="0.05"></div>'+
      '<button class="secondary small" data-role="remove" type="button">Remove</button>'+
    '</div>').join('');
  rows.querySelectorAll('.lora-row').forEach((row)=>{
    const i=Number(row.dataset.index);
    const select=row.querySelector('[data-role="tag"]');
    select.value=selectedLoras[i].tag || '';
    select.onchange=()=>{ selectedLoras[i].tag=select.value; };
    row.querySelector('[data-role="weight"]').oninput=(e)=>{ selectedLoras[i].weight=e.target.value; };
    row.querySelector('[data-role="remove"]').onclick=()=>{ selectedLoras.splice(i,1); renderLoraRows(); };
  });
}
function addLora(){
  const first=loraCatalog.find(l=>!selectedLoras.some(s=>s.tag===l.tag)) || loraCatalog[0];
  if(!first) return;
  selectedLoras.push({tag:first.tag,weight:1});
  renderLoraRows();
}
function applyAspect(){
  const value=qs('aspect').value;
  if(value==='custom') return;
  const parts=value.split('x').map(Number);
  if(parts.length===2 && parts.every(Boolean)){
    qs('width').value=parts[0];
    qs('height').value=parts[1];
  }
}
function syncAspect(){
  const value=qs('width').value+'x'+qs('height').value;
  const aspect=qs('aspect');
  aspect.value=[...aspect.options].some(o=>o.value===value) ? value : 'custom';
}
function roundedImageSize(width,height){
  const clamp=(v)=>Math.max(256,Math.min(1536,Math.round(v/64)*64));
  return {width:clamp(width),height:clamp(height)};
}
function setBatchLimit(){
  const limit=sourceImage ? 2 : 4;
  [...qs('batchCount').options].forEach(option=>{ option.disabled=Number(option.value)>limit; });
  if(Number(qs('batchCount').value)>limit) qs('batchCount').value=String(limit);
}
function renderSourcePreview(){
  const preview=qs('sourcePreview');
  qs('matchInitSize').disabled=!sourceImage;
  qs('clearInitImage').disabled=!sourceImage;
  setBatchLimit();
  if(!sourceImage){
    preview.style.display='none';
    preview.innerHTML='';
    return;
  }
  preview.style.display='grid';
  preview.innerHTML='<img src="'+sourceImage.data_url+'" alt="Source image preview"><div><b>'+esc(sourceImage.name)+'</b><br>'+sourceImage.width+'x'+sourceImage.height+' source · img2img batch capped at 2</div>';
}
function readSourceImage(file){
  if(!file) return;
  if(file.size > 20*1024*1024){
    qs('msg').textContent='Error: Source image is too large. Limit is 20 MB.';
    qs('initImage').value='';
    return;
  }
  const reader=new FileReader();
  reader.onload=()=>{
    const img=new Image();
    img.onload=()=>{
      sourceImage={data_url:reader.result,name:file.name,width:img.naturalWidth,height:img.naturalHeight};
      renderSourcePreview();
    };
    img.onerror=()=>{ qs('msg').textContent='Error: Could not read source image.'; };
    img.src=reader.result;
  };
  reader.onerror=()=>{ qs('msg').textContent='Error: Could not read source image.'; };
  reader.readAsDataURL(file);
}
function clearSourceImage(){
  sourceImage=null;
  qs('initImage').value='';
  renderSourcePreview();
}
function matchSourceSize(){
  if(!sourceImage) return;
  const size=roundedImageSize(sourceImage.width, sourceImage.height);
  qs('width').value=size.width;
  qs('height').value=size.height;
  syncAspect();
}
async function refreshLoras(){
  const d=await json('/api/loras');
  loraCatalog=d.loras||[];
  selectedLoras=selectedLoras.filter(item=>loraCatalog.some(l=>l.tag===item.tag));
  renderLoraRows();
  loraDirPath=d.lora_dir||'';
  const known=d.known_loras?.length||0;
  qs('loraStatus').innerHTML=(d.loras.length?d.loras.length+' installed':'No installed LoRAs')+' · '+known+' official entries · <code>'+esc(loraDirPath)+'</code>';
}
async function copyLoraPath(){
  if(!loraDirPath) return;
  const btn=qs('copyLoraPath');
  const original=btn.textContent;
  try{
    if(navigator.clipboard && window.isSecureContext){
      await navigator.clipboard.writeText(loraDirPath);
    }else{
      const ta=document.createElement('textarea');
      ta.value=loraDirPath;
      ta.style.position='fixed';
      ta.style.opacity='0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    btn.textContent='Copied!';
  }catch(e){
    btn.textContent='Copy failed';
  }
  setTimeout(()=>{ btn.textContent=original; },1500);
}
async function generate(){
  qs('generate').disabled=true; qs('msg').textContent='Starting generation...';
  try{
    const loras=selectedLoras.filter(item=>item.tag).map(item=>({tag:item.tag,weight:item.weight || 1}));
    const payload={prompt:qs('prompt').value,width:qs('width').value,height:qs('height').value,steps:qs('steps').value,batch_count:qs('batchCount').value,seed:qs('seed').value,cfg_scale:qs('cfg').value,flow_shift:qs('shift').value,sampler:qs('sampler').value,lora_apply_mode:qs('loraMode').value,custom_lora_tags:qs('customLora').value,loras,strength:qs('strength').value};
    if(sourceImage) payload.init_image={data_url:sourceImage.data_url,name:sourceImage.name,width:sourceImage.width,height:sourceImage.height};
    const d=await json('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const urls=d.image_urls||[d.image_url];
    qs('preview').className='preview'+(urls.length===1?' single':'');
    qs('preview').innerHTML=urls.map((url,i)=>'<a href="'+url+'" target="_blank"><img src="'+url+'?t='+Date.now()+'" alt="Krea output '+(i+1)+'"></a>').join('');
    qs('msg').textContent='Done in '+d.elapsed_seconds+'s · '+urls.length+' image'+(urls.length===1?'':'s')+'\\nLog: '+d.log;
    await refresh();
  }catch(e){ qs('msg').textContent='Error: '+e.message; await refresh().catch(()=>{}); }
  finally{ qs('generate').disabled=false; }
}
qs('refresh').onclick=()=>{ refresh(); refreshLoras(); };
qs('refreshLoras').onclick=refreshLoras;
qs('copyLoraPath').onclick=copyLoraPath;
qs('addLora').onclick=addLora;
qs('generate').onclick=generate;
qs('aspect').onchange=applyAspect;
qs('width').oninput=syncAspect;
qs('height').oninput=syncAspect;
qs('initImage').onchange=(e)=>readSourceImage(e.target.files[0]);
qs('clearInitImage').onclick=clearSourceImage;
qs('matchInitSize').onclick=matchSourceSize;
qs('strength').oninput=()=>{ qs('strengthValue').textContent=Number(qs('strength').value).toFixed(2); };
refreshLoras().finally(refresh);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def _headers(self, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, payload: dict, code=200):
        body = json.dumps(payload, indent=2).encode()
        self._headers(code, "application/json; charset=utf-8")
        self._write(body)

    def _write(self, body: bytes):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = INDEX_HTML.encode()
            self._headers(200, "text/html; charset=utf-8")
            self._write(body)
            return
        if path == "/favicon.ico":
            self._headers(204, "image/x-icon")
            return
        if path in ("/health", "/api/status"):
            self._json(status_payload())
            return
        if path == "/api/loras":
            self._json(
                {
                    "lora_dir": str(LORA_DIR),
                    "loras": list_loras(),
                    "known_loras": load_lora_manifest().get("official", []),
                }
            )
            return
        if path == "/loras/":
            rows = []
            for item in list_loras():
                url = "/loras/" + item["filename"].replace("/", "%2F")
                rows.append(
                    "<tr>"
                    f"<td><a href=\"{html_escape(url)}\">{html_escape(item['filename'])}</a></td>"
                    f"<td>{html_escape(item['name'])}</td>"
                    f"<td>{html_escape(item['size'])}</td>"
                    f"<td>{html_escape(item.get('repo_id') or '')}</td>"
                    "</tr>"
                )
            body = (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<title>Krea 2 LoRAs</title>"
                "<style>body{margin:24px;background:#080e1c;color:#d8e8f4;font-family:system-ui,sans-serif}"
                "a{color:#22d3ee}table{border-collapse:collapse;width:100%;max-width:1100px}"
                "td,th{border-bottom:1px solid rgba(34,211,238,.18);padding:10px;text-align:left}"
                "th{color:#7b9bb2;font-size:12px;text-transform:uppercase;letter-spacing:.08em}</style>"
                "</head><body><h1>Krea 2 LoRAs</h1>"
                f"<p>{html_escape(str(LORA_DIR))}</p>"
                "<table><thead><tr><th>File</th><th>Name</th><th>Size</th><th>Source</th></tr></thead>"
                "<tbody>" + "".join(rows) + "</tbody></table></body></html>"
            )
            self._headers(200, "text/html; charset=utf-8")
            self._write(body.encode())
            return
        if path.startswith("/loras/"):
            name = unquote(path.split("/", 2)[2])
            target = (LORA_DIR / name).resolve()
            if LORA_DIR.resolve() not in target.parents or not target.exists() or target.suffix.lower() not in LORA_EXTENSIONS:
                self._json({"error": "LoRA not found."}, 404)
                return
            self._headers(200, "application/octet-stream")
            self._write(target.read_bytes())
            return
        if path.startswith("/outputs/"):
            name = unquote(path.split("/", 2)[2])
            target = (OUTPUT_DIR / name).resolve()
            if OUTPUT_DIR.resolve() not in target.parents or not target.exists():
                self._json({"error": "Output not found."}, 404)
                return
            self._headers(200, "image/png" if target.suffix == ".png" else "text/plain")
            self._write(target.read_bytes())
            return
        self._json({"error": "Not found."}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/generate":
            self._json({"error": "Not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_INIT_IMAGE_BYTES * 2:
                self._json({"ok": False, "error": "Request is too large. Source image limit is 20 MB."}, 413)
                return
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(run_generation(payload))
        except Exception as exc:
            self._json({"ok": False, "error": str(exc), "last_run": LAST_RUN}, 500)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Krea 2 runner -> http://{HOST}:{PORT}")
    print(json.dumps(status_payload(), indent=2))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
