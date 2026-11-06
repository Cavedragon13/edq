#!/usr/bin/env python3
"""
GLB-3D-Coder Studio — Seed 13 Productions / Dragonsuite (port 8022)

Text prompt -> low-poly game asset. CCORE's Qwen3.5-4B-GLB-3D-Coder (Q8_0 GGUF, Apache 2.0)
writes one standalone Three.js HTML page with a preview and an "Export GLB" button.
The model runs in llama-server (127.0.0.1:18022, started by scripts/start_glb_3d_coder.sh);
this app is a thin UI over its OpenAI-compatible API, so it holds no GPU memory itself.

Outputs: ~/ai_generated/glb-3d-coder/
  <ts>_<slug>.html   the generated page, exactly as the model wrote it
  <ts>_<slug>.json   prompt, timings, token counts, reasoning text
  <ts>_<slug>.glb    saved automatically when you press Export GLB in the preview
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import gradio as gr
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PORT = int(os.environ.get("GLB3D_PORT", "8022"))
HOST = os.environ.get("GLB3D_HOST", "0.0.0.0")
LLM_URL = os.environ.get("GLB3D_LLM_URL", "http://127.0.0.1:18022")
OUTPUT_DIR = Path(os.environ.get("GLB3D_OUTPUT_DIR", os.path.expanduser("~/ai_generated/glb-3d-coder")))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path("/srv/containers/edq/logs/glb_3d_coder.log")
FAVICON = "/srv/containers/edq/media/favicons/glb-3d-coder.svg"
MAX_GLB_BYTES = 200 * 1024 * 1024

# From the model card — the system prompt and sampling it was trained/evaluated with.
SYSTEM_PROMPT = (
    "Create game assets for the Godot editor, which uses GLB files. Create whatever the user requests as a "
    "good-quality low-poly asset using only Three.js in one complete standalone HTML file. The HTML must show "
    "the asset and include an Export GLB button that downloads a working GLB. If the requested asset needs "
    "animation, add it and include the animation in the exported GLB; otherwise make it static."
)
SAMPLING = {"temperature": 0.8, "top_k": 40, "top_p": 0.95, "min_p": 0.0, "repeat_penalty": 1.0}

EXAMPLES = [
    "Create a village blacksmith wearing a blue apron.",
    "Create a swamp goblin scout with a wooden shield.",
    "Create a stone golem boss with glowing green crystals.",
    "Create a tiny fox companion wearing a red scarf.",
    "Create a short iron sword with a leather-wrapped grip.",
    "Create a blue mana potion in a hexagonal glass bottle.",
    "Create a weathered wooden workbench with a small lantern.",
    "Create a pine tree growing on a rocky mound.",
    "Create a stone dungeon doorway module with an iron frame.",
    "Create a wooden gate with an opening animation.",
    "Create a small cargo airship with twin propellers.",
    "Create a white laboratory microscope with a rotating objective turret.",
    "Create a small farmyard with a red barn, wooden fences, hay bales, a water trough, and a vegetable patch.",
    "Create a hidden spiked floor trap with stone tiles.",
]

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
log = logging.getLogger("glb_3d_coder")
log.setLevel(logging.INFO)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_h = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3)
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_h)
log.addHandler(logging.StreamHandler())


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+\.(html|json|glb)$")


def slugify(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"^create-(an?-)?", "", s)
    return (s[:n].rstrip("-")) or "asset"


def extract_html(text):
    """Pull the HTML document out of the model's answer (fenced or bare)."""
    m = re.search(r"```(?:html)?\s*\n(.*?)(?:```|\Z)", text, re.S | re.I)
    body = m.group(1) if m else text
    start = re.search(r"<!DOCTYPE html|<html", body, re.I)
    if not start:
        return None
    body = body[start.start():]
    end = body.lower().rfind("</html>")
    return body[: end + 7] if end != -1 else body  # unterminated = truncated; keep what exists


def llm_health():
    try:
        r = httpx.get(f"{LLM_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def recent_files(limit=40):
    files = sorted(OUTPUT_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in files[:limit]]


def preview_html(name):
    if not name:
        return ("<div class='empty-preview'>Your asset preview appears here. Press "
                "<b>Export GLB</b> inside it to download the file — a copy is also saved to "
                f"<code>{OUTPUT_DIR}</code>.</div>")
    v = int(time.time())
    return (f"<iframe class='asset-frame' src='/view/{name}?v={v}' "
            "sandbox='allow-scripts allow-downloads allow-pointer-lock allow-popups' "
            "allow='fullscreen'></iframe>"
            f"<div class='frame-links'><a href='/view/{name}' target='_blank'>Open full page ↗</a> · "
            f"<a href='/raw/{name}' download>Download HTML</a></div>")


def ui_status():
    ok = llm_health()
    n = len(list(OUTPUT_DIR.glob("*.html")))
    g = len(list(OUTPUT_DIR.glob("*.glb")))
    model = "🟢 model loaded (llama-server)" if ok else "🔴 model server not reachable — relaunch from the dashboard"
    return f"{model} · {n} pages · {g} GLBs in `{OUTPUT_DIR}`"


# --------------------------------------------------------------------------- #
# Generation (streams reasoning + code from llama-server)
# --------------------------------------------------------------------------- #
def generate(prompt, max_tokens):
    prompt = (prompt or "").strip()
    if not prompt:
        raise gr.Error("Describe the asset you want first.")
    if not llm_health():
        raise gr.Error("The model server (llama-server on 127.0.0.1:18022) is not running. Relaunch the service.")

    payload = {
        "model": "glb-3d-coder",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": int(max_tokens) if max_tokens and int(max_tokens) > 0 else -1,
        **SAMPLING,
    }
    t0 = time.time()
    reasoning, content, usage = [], [], {}
    last_emit = 0.0
    log.info("generate: %s", prompt[:200])
    yield gr.update(), "", "⏳ Thinking…", gr.update()
    try:
        with httpx.stream("POST", f"{LLM_URL}/v1/chat/completions", json=payload, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                if ev.get("usage"):
                    usage = ev["usage"]
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    if d.get("reasoning_content"):
                        reasoning.append(d["reasoning_content"])
                    if d.get("content"):
                        content.append(d["content"])
                now = time.time()
                if now - last_emit > 0.5:
                    last_emit = now
                    phase = "Writing code" if content else "Thinking"
                    r_chars, c_chars = sum(map(len, reasoning)), sum(map(len, content))
                    yield (gr.update(), "".join(content)[-6000:],
                           f"⏳ {phase}… {now - t0:.0f}s · reasoning {r_chars:,} chars · code {c_chars:,} chars",
                           gr.update())
    except httpx.HTTPError as e:
        log.exception("llm request failed")
        raise gr.Error(f"Model server error: {e}")

    elapsed = time.time() - t0
    full = "".join(content)
    html = extract_html(full)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{slugify(prompt)}"
    meta = {
        "prompt": prompt, "system_prompt": SYSTEM_PROMPT, "sampling": SAMPLING,
        "model": "ccore/Qwen3.5-4B-GLB-3D-Coder Q8_0", "seconds": round(elapsed, 1), "usage": usage,
        "complete_html": bool(html and html.lower().rstrip().endswith("</html>")),
        "reasoning": "".join(reasoning), "raw_answer": full if not html else None,
    }
    (OUTPUT_DIR / f"{stem}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not html:
        log.warning("no html in answer (%d chars)", len(full))
        yield (gr.update(), full[-6000:],
               f"⚠️ The model finished without an HTML page ({elapsed:.0f}s). Saved the raw answer to `{stem}.json` — try again.",
               gr.update(choices=recent_files()))
        return
    (OUTPUT_DIR / f"{stem}.html").write_text(html, encoding="utf-8")
    toks = usage.get("completion_tokens")
    tps = f" · {toks / elapsed:.0f} tok/s" if toks else ""
    warn = "" if meta["complete_html"] else " · ⚠️ page looks truncated (no </html>) — raise the token limit or retry"
    log.info("saved %s.html (%.0fs, %s tokens)", stem, elapsed, toks)
    yield (preview_html(f"{stem}.html"), html,
           f"✅ Saved `{stem}.html` in {elapsed:.0f}s ({toks or '?'} tokens{tps}){warn}",
           gr.update(choices=recent_files(), value=f"{stem}.html"))


# --------------------------------------------------------------------------- #
# FastAPI routes: preview pages (with a GLB auto-save hook) and GLB upload
# --------------------------------------------------------------------------- #
GLB_HOOK = """<script>
/* Dragonsuite: when the page downloads a .glb, also save a copy to ~/ai_generated/glb-3d-coder/ */
(function(){
  const PAGE = %s, ORIGIN = %s;
  async function grab(a){
    try {
      const name = a.download || ''; if (!/\\.glb$/i.test(name) || !a.href) return;
      if (a.__dsGrabbed === a.href) return;   /* .click() also fires the document listener */
      a.__dsGrabbed = a.href;
      const blob = await (await fetch(a.href)).blob();
      const r = await fetch(ORIGIN + '/api/save-glb?page=' + encodeURIComponent(PAGE), {method:'POST', body: blob});
      const j = await r.json(); console.log('[dragonsuite] GLB saved as', j.saved);
      const t = document.createElement('div'); t.textContent = '✓ GLB saved to ai_generated: ' + j.saved;
      t.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:99999;background:#4c1d95;color:#fff;padding:8px 12px;border-radius:8px;border:1px solid #d8af62;font:13px system-ui';
      document.body.appendChild(t); setTimeout(() => t.remove(), 5000);
    } catch (e) { console.warn('[dragonsuite] GLB auto-save failed', e); }
  }
  const orig = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function(){ grab(this); return orig.apply(this, arguments); };
  document.addEventListener('click', e => { const a = e.target.closest && e.target.closest('a[download]'); if (a) grab(a); }, true);
})();
</script>"""

app = FastAPI()


def _safe(name, ext):
    if not SAFE_NAME.match(name) or not name.endswith(ext):
        raise HTTPException(404)
    p = OUTPUT_DIR / name
    if not p.is_file():
        raise HTTPException(404)
    return p


@app.get("/view/{name}", response_class=HTMLResponse)
def view(name: str, request: Request):
    html = _safe(name, ".html").read_text(encoding="utf-8")
    origin = f"{request.url.scheme}://{request.headers.get('host', f'127.0.0.1:{PORT}')}"
    hook = GLB_HOOK % (json.dumps(name), json.dumps(origin))
    m = re.search(r"<head[^>]*>", html, re.I)
    html = html[: m.end()] + hook + html[m.end():] if m else hook + html
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/raw/{name}")
def raw(name: str):
    p = _safe(name, ".html")
    return Response(p.read_bytes(), media_type="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.options("/api/save-glb")
def save_glb_options():
    return Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST",
                             "Access-Control-Allow-Headers": "*"})


@app.post("/api/save-glb")
async def save_glb(request: Request, page: str = ""):
    body = await request.body()
    if not body or len(body) > MAX_GLB_BYTES or body[:4] != b"glTF":
        return JSONResponse({"error": "not a GLB file"}, status_code=400,
                            headers={"Access-Control-Allow-Origin": "*"})
    stem = page[:-5] if SAFE_NAME.match(page or "") and page.endswith(".html") else \
        f"{datetime.now():%Y%m%d_%H%M%S}_export"
    out = OUTPUT_DIR / f"{stem}.glb"
    n = 2
    while out.exists():
        out = OUTPUT_DIR / f"{stem}_{n}.glb"
        n += 1
    out.write_bytes(body)
    log.info("saved GLB %s (%d bytes)", out.name, len(body))
    return JSONResponse({"saved": out.name}, headers={"Access-Control-Allow-Origin": "*"})


# --------------------------------------------------------------------------- #
# UI — Seed 13 Productions purple/gold, dark by default (localStorage toggle)
# --------------------------------------------------------------------------- #
CSS = """
:root { --s13-purple: #7c3aed; --s13-purple-deep: #4c1d95; --s13-gold: #d8af62; --s13-gold-soft: #e9cf94; }
.gradio-container { max-width: 1600px !important; transition: background-color .3s ease, color .3s ease; }
body.dark, body.dark .gradio-container { background: linear-gradient(160deg, #1a1a2e 0%, #1e1e1e 55%, #241a33 100%) !important; }
#s13-header { display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:14px 18px; border-radius:14px; border:1px solid var(--s13-gold);
  background: linear-gradient(135deg, var(--s13-purple-deep) 0%, var(--s13-purple) 60%, #9b6b2f 100%); }
#s13-header h1 { margin:0; color:#fff; font-size:1.55rem; letter-spacing:.3px; }
#s13-header .kicker { color: var(--s13-gold-soft); font-size:.78rem; letter-spacing:2px; text-transform:uppercase; margin:0 0 2px; }
#s13-header .sub { color:#ede9fe; font-size:.9rem; margin:2px 0 0; }
#theme-toggle { width:44px !important; min-width:44px !important; height:44px; border-radius:50% !important;
  border:1px solid var(--s13-gold) !important; background: rgba(0,0,0,.25) !important; color:#fff !important;
  font-size:1.2rem; transition: transform .3s ease; flex: 0 0 44px !important; }
#theme-toggle:hover { transform: rotate(180deg); }
#go-btn { background: linear-gradient(135deg, var(--s13-purple) 0%, var(--s13-purple-deep) 100%) !important;
  border:1px solid var(--s13-gold) !important; color:#fff !important; font-weight:600; }
#go-btn:hover { filter: brightness(1.12); }
.asset-frame { width:100%; height:640px; border:1px solid var(--s13-gold); border-radius:10px; background:#111; }
.frame-links { font-size:.85rem; padding-top:4px; }
.frame-links a { color: var(--s13-gold); }
.empty-preview { height:640px; display:flex; align-items:center; justify-content:center; text-align:center;
  padding:24px; border:1px dashed #4a5568; border-radius:10px; color:#9ca3af; }
#tip { border-left:3px solid var(--s13-gold); padding:6px 10px; border-radius:6px; font-size:.85rem; }
body.dark #tip { background:#2d2d2d; color:#e0e0e0; }
#s13-footer { text-align:center; color:#9ca3af; font-size:.8rem; padding-top:6px; }
#s13-footer b { color: var(--s13-gold); }
footer { display:none !important; }
"""

THEME_JS = """
() => {
  const pref = localStorage.getItem('glb-3d-coder-theme');
  const dark = pref !== 'light';
  document.body.classList.toggle('dark', dark);
  if (!pref) localStorage.setItem('glb-3d-coder-theme', 'dark');
  const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
}
"""
TOGGLE_JS = """
() => {
  const dark = !document.body.classList.contains('dark');
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('glb-3d-coder-theme', dark ? 'dark' : 'light');
  const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
}
"""

THEME = gr.themes.Soft(primary_hue="violet", secondary_hue="amber", neutral_hue="slate").set(
    body_background_fill_dark="#1e1e1e", block_background_fill_dark="#2d2d2d",
    border_color_primary_dark="#4a5568", body_text_color_dark="#e0e0e0",
    input_background_fill_dark="#2d2d2d", button_secondary_background_fill_dark="#374151",
)

TIP = ("Start with a short idea, or name the main object first, then its parts, colors, materials, layout and "
       "any animation. Answers average ~20K tokens (thinking + code), so expect a few minutes. "
       "Pressing **Export GLB** in the preview also saves the `.glb` next to the page.")

with gr.Blocks(title="GLB-3D-Coder — Seed 13") as demo:
    with gr.Row(elem_id="s13-header"):
        gr.HTML("<div><p class='kicker'>Seed 13 Productions · Dragonsuite</p>"
                "<h1>🐉 GLB-3D-Coder Studio</h1>"
                "<p class='sub'>Text → low-poly Three.js asset → GLB for Godot · CCORE Qwen3.5-4B</p></div>")
        theme_btn = gr.Button("☀️", elem_id="theme-toggle", scale=0, min_width=44)
    gr.Markdown(TIP, elem_id="tip")
    with gr.Row():
        with gr.Column(scale=4):
            prompt = gr.Textbox(label="Asset request", lines=5,
                                placeholder="Create a coral-armored lighthouse keeper.")
            example = gr.Dropdown(EXAMPLES, label="Prompt ideas (from the model card)", value=None)
            with gr.Accordion("Advanced", open=False):
                max_tokens = gr.Number(value=0, precision=0,
                                       label="Max output tokens (0 = unlimited, as the model card recommends)")
            with gr.Row():
                go = gr.Button("Generate asset", variant="primary", elem_id="go-btn")
                stop = gr.Button("Stop", variant="stop")
            status = gr.Markdown(ui_status())
            history = gr.Dropdown(recent_files(), label=f"Previous assets — {OUTPUT_DIR}", value=None)
            code = gr.Code(label="Generated HTML", language="html", lines=18, interactive=False)
        with gr.Column(scale=6):
            preview = gr.HTML(preview_html(None))
    gr.HTML("<div id='s13-footer'>Model: CCORE GLB-3D-Coder (Apache 2.0, based on Qwen3.5-4B) · "
            f"<b>Seed 13 Productions</b> · outputs in <code>{OUTPUT_DIR}</code></div>")

    theme_btn.click(fn=None, js=TOGGLE_JS)
    example.change(lambda e: e or gr.update(), example, prompt, api_name=False)
    run = go.click(generate, [prompt, max_tokens], [preview, code, status, history],
                   api_name="generate", concurrency_limit=1)
    stop.click(None, None, None, cancels=[run])
    history.change(lambda n: (preview_html(n), (OUTPUT_DIR / n).read_text(encoding="utf-8") if n else ""),
                   history, [preview, code], api_name=False)
    demo.load(lambda: (ui_status(), gr.update(choices=recent_files())), None, [status, history], api_name=False)


app = gr.mount_gradio_app(app, demo.queue(max_size=8, default_concurrency_limit=1), path="/",
                          theme=THEME, css=CSS, js=THEME_JS,
                          favicon_path=FAVICON if Path(FAVICON).exists() else None)

if __name__ == "__main__":
    log.info("GLB-3D-Coder Studio on %s:%d — llm %s — outputs %s", HOST, PORT, LLM_URL, OUTPUT_DIR)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
