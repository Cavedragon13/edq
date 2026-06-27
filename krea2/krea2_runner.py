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
import subprocess
import threading
import time
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

GENERATE_LOCK = threading.Lock()
LAST_RUN: dict = {}


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
    for path in sorted(LORA_DIR.rglob("*")):
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


def lora_prompt(payload: dict, prompt: str) -> tuple[str, list[dict]]:
    loras_used = []
    selected = str(payload.get("lora_name") or "").strip()
    if selected and selected.lower() != "none":
        available = {item["tag"]: item for item in list_loras()}
        if selected not in available:
            raise ValueError(f"Selected LoRA is not installed: {selected}")
        weight = clamp_float(payload.get("lora_weight"), 1.0, 0.0, 2.0)
        prompt += f"<lora:{selected}:{weight:g}>"
        item = dict(available[selected])
        item["weight"] = weight
        loras_used.append(item)

    custom_tags = str(payload.get("custom_lora_tags") or "").strip()
    if custom_tags:
        if len(custom_tags) > 500:
            raise ValueError("Extra LoRA tags are too long.")
        prompt += custom_tags
        loras_used.append({"name": "Custom prompt tags", "tag": custom_tags, "weight": None})

    return prompt, loras_used


def build_command(payload: dict, out_path: Path) -> list[str]:
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

    if BACKEND_ASSIGNMENT:
        cmd[cmd.index("-W"):cmd.index("-W")] = ["--backend", BACKEND_ASSIGNMENT]

    extra = os.environ.get("KREA2_EXTRA_ARGS", "").strip()
    if extra:
        cmd.extend(shlex.split(extra))
    return cmd


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
    _prompt_with_loras, loras_used = lora_prompt(payload, str(payload.get("prompt") or "").strip())
    lora_suffix = ""
    selected = str(payload.get("lora_name") or "").strip()
    if selected and selected.lower() != "none":
        lora_suffix = "-lora-" + sanitize_filename_token(selected)
    out_path = OUTPUT_DIR / f"krea2-{stamp}{lora_suffix}.png"
    log_path = LOG_DIR / f"krea2-{stamp}.log"
    cmd = build_command(payload, out_path)

    LAST_RUN = {
        "status": "running",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "output": str(out_path),
        "log": str(log_path),
        "loras": loras_used,
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
            }
            raise RuntimeError(f"sd-cli failed with exit code {proc.returncode}.")
        if not out_path.exists():
            raise RuntimeError("sd-cli completed but no output image was written.")
        LAST_RUN = {
            "status": "ok",
            "elapsed_seconds": elapsed,
            "output": str(out_path),
            "log": str(log_path),
            "loras": loras_used,
        }
        return {
            "ok": True,
            "elapsed_seconds": elapsed,
            "image_url": "/outputs/" + out_path.name,
            "log": str(log_path),
            "loras": loras_used,
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
main{max-width:1120px;margin:0 auto;padding:28px}header{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:18px}
h1{font-size:22px;letter-spacing:.08em;text-transform:uppercase;margin:0}p{color:var(--muted);margin:6px 0 0}
.grid{display:grid;grid-template-columns:minmax(320px,420px) 1fr;gap:16px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
label{display:block;color:var(--muted);font-size:12px;margin:12px 0 6px}textarea,input,select{width:100%;background:#08111f;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit}
textarea{min-height:150px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.actions{display:flex;align-items:center;gap:10px;margin-top:14px}
button{background:var(--accent);color:#041018;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}button:disabled{opacity:.5;cursor:wait}
.status{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted);display:grid;gap:6px}.status b{color:var(--text)}.ok{color:var(--ok)}.bad{color:var(--bad)}
.section-title{margin:16px 0 2px;color:var(--text);font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.mini{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}
.preview{min-height:560px;display:flex;align-items:center;justify-content:center;background:#050a13;border:1px solid var(--line);border-radius:8px;overflow:hidden}.preview img{max-width:100%;height:auto;display:block}
.msg{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);font-size:12px;margin-top:12px;white-space:pre-wrap}
@media(max-width:860px){.grid{grid-template-columns:1fr}main{padding:14px}.preview{min-height:320px}}
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
      <div class="row">
        <div><label for="width">Width</label><input id="width" type="number" value="1024" min="256" max="1536" step="64"></div>
        <div><label for="height">Height</label><input id="height" type="number" value="1024" min="256" max="1536" step="64"></div>
      </div>
      <div class="row">
        <div><label for="steps">Steps</label><input id="steps" type="number" value="8" min="1" max="24"></div>
        <div><label for="seed">Seed</label><input id="seed" type="number" value="-1"></div>
      </div>
      <div class="row">
        <div><label for="cfg">CFG</label><input id="cfg" type="number" value="1" min="0" max="20" step="0.1"></div>
        <div><label for="shift">Flow shift</label><input id="shift" type="number" value="1.15" min="0" max="10" step="0.05"></div>
      </div>
      <label for="sampler">Sampler</label>
      <select id="sampler"><option value="euler">euler</option><option value="dpm++2m">dpm++2m</option><option value="res_multistep">res_multistep</option></select>
      <div class="section-title">LoRA</div>
      <div class="row">
        <div><label for="lora">Installed LoRA</label><select id="lora"><option value="">None</option></select></div>
        <div><label for="loraWeight">Weight</label><input id="loraWeight" type="number" value="1" min="0" max="2" step="0.05"></div>
      </div>
      <div class="row">
        <div><label for="loraMode">Apply mode</label><select id="loraMode"><option value="auto">auto</option><option value="at_runtime">at_runtime</option><option value="immediately">immediately</option></select></div>
        <div><label>&nbsp;</label><button id="refreshLoras" type="button">Refresh LoRAs</button></div>
      </div>
      <label for="customLora">Extra LoRA tags</label>
      <input id="customLora" type="text" placeholder="<lora:name:1>">
      <div class="mini" id="loraStatus"></div>
      <div class="actions">
        <button id="generate">Generate</button>
      </div>
      <div class="msg" id="msg"></div>
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
async function refresh(){
  const d=await json('/api/status');
  qs('status').innerHTML='<div>Ready: <b class="'+(d.ready?'ok':'bad')+'">'+d.ready+'</b> Busy: <b>'+d.busy+'</b></div>'+
    d.models.map(m=>'<div>'+m.label+': <b class="'+(m.exists?'ok':'bad')+'">'+m.size+'</b></div>').join('')+
    '<div>LoRAs: <b>'+d.lora_count+'</b></div>'+
    (d.latest_output?'<div>Latest: <a href="/outputs/'+d.latest_output+'" target="_blank">'+d.latest_output+'</a></div>':'');
}
async function refreshLoras(){
  const selected=qs('lora').value;
  const d=await json('/api/loras');
  const opts=['<option value="">None</option>'].concat(d.loras.map(l=>'<option value="'+esc(l.tag)+'">'+esc(l.name)+' · '+esc(l.size)+'</option>'));
  qs('lora').innerHTML=opts.join('');
  if([...qs('lora').options].some(o=>o.value===selected)) qs('lora').value=selected;
  const known=d.known_loras?.length||0;
  qs('loraStatus').textContent=(d.loras.length?d.loras.length+' installed':'No installed LoRAs')+' · '+known+' known official entries · '+d.lora_dir;
}
async function generate(){
  qs('generate').disabled=true; qs('msg').textContent='Starting generation...';
  try{
    const payload={prompt:qs('prompt').value,width:qs('width').value,height:qs('height').value,steps:qs('steps').value,seed:qs('seed').value,cfg_scale:qs('cfg').value,flow_shift:qs('shift').value,sampler:qs('sampler').value,lora_name:qs('lora').value,lora_weight:qs('loraWeight').value,lora_apply_mode:qs('loraMode').value,custom_lora_tags:qs('customLora').value};
    const d=await json('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    qs('preview').innerHTML='<a href="'+d.image_url+'" target="_blank"><img src="'+d.image_url+'?t='+Date.now()+'" alt="Krea output"></a>';
    qs('msg').textContent='Done in '+d.elapsed_seconds+'s\\nLog: '+d.log;
    await refresh();
  }catch(e){ qs('msg').textContent='Error: '+e.message; await refresh().catch(()=>{}); }
  finally{ qs('generate').disabled=false; }
}
qs('refresh').onclick=()=>{ refresh(); refreshLoras(); };
qs('refreshLoras').onclick=refreshLoras;
qs('generate').onclick=generate;
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
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = INDEX_HTML.encode()
            self._headers(200, "text/html; charset=utf-8")
            self.wfile.write(body)
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
        if path.startswith("/outputs/"):
            name = unquote(path.split("/", 2)[2])
            target = (OUTPUT_DIR / name).resolve()
            if OUTPUT_DIR.resolve() not in target.parents or not target.exists():
                self._json({"error": "Output not found."}, 404)
                return
            self._headers(200, "image/png" if target.suffix == ".png" else "text/plain")
            self.wfile.write(target.read_bytes())
            return
        self._json({"error": "Not found."}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/generate":
            self._json({"error": "Not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
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
