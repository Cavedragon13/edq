#!/usr/bin/env python3
"""
Unlimited OCR 2 Studio — Seed 13 Productions / Dragonsuite (port 8007)

Document parsing with baidu/Unlimited-OCR-2 (3.3B, MIT license): images or PDFs -> Markdown
(tables, formulas, figure crops, layout boxes). Uses the model's own Transformers path
(trust_remote_code `infer`), not the vendor's custom SGLang build.

Modes (from the model card):
  * Single page  — one image, dynamic tiling ("gundam"), best detail.
  * Document     — all pages in one request ("base" view per page) so the model uses cross-page context.
                   SR-SWA keeps memory roughly flat as page count grows.

Outputs: ~/ai_generated/unlimited-ocr/<ts>_<name>/
  result.md               cleaned Markdown (figure crops linked from images/)
  result_raw.md           raw model output with grounding tags
  result_with_boxes_N.jpg each page with detected layout boxes
  images/                 figure crops
  meta.json               settings, timings, token counts
"""
import sys

sys.path.insert(0, "/srv/containers/edq/scripts")
import gpu_runtime  # noqa: E402  FIRST — configures the CUDA allocator before torch

import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import queue  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402
from pathlib import Path  # noqa: E402

import fitz  # noqa: E402  PyMuPDF
import gradio as gr  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PORT = int(os.environ.get("UOCR_PORT", "8007"))
HOST = os.environ.get("UOCR_HOST", "0.0.0.0")
MODEL_DIR = Path(os.environ.get("UOCR_MODEL_DIR", "/srv/containers/edq/models/unlimited-ocr-2"))
OUTPUT_DIR = Path(os.environ.get("UOCR_OUTPUT_DIR", os.path.expanduser("~/ai_generated/unlimited-ocr")))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path("/srv/containers/edq/logs/unlimited_ocr.log")
FAVICON = "/srv/containers/edq/media/favicons/unlimited-ocr.svg"
PDF_DPI = int(os.environ.get("UOCR_PDF_DPI", "200"))
MAX_PAGES = int(os.environ.get("UOCR_MAX_PAGES", "200"))
TOKENS_PER_PAGE = 8000          # model card: per-page output budget
MAX_PAGE_TOKENS = 20000         # model card: per-page hard cap (PageCountGuard)

MODES = {
    "Auto (tiles for 1 page, document mode for several)": None,
    "Single page — detailed tiling": True,
    "Document — all pages in one pass": False,
}

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
log = logging.getLogger("unlimited_ocr")
log.setLevel(logging.INFO)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_h = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3)
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(_h)
log.addHandler(logging.StreamHandler())

# --------------------------------------------------------------------------- #
# Model (loaded once in the background; the UI is usable while it warms up)
# --------------------------------------------------------------------------- #
_model = None
_tokenizer = None
_load_error = None
_lock = threading.Lock()


def load_model():
    global _model, _tokenizer, _load_error
    try:
        from transformers import AutoModel, AutoTokenizer
        t0 = time.time()
        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), trust_remote_code=True)
        m = AutoModel.from_pretrained(str(MODEL_DIR), trust_remote_code=True, use_safetensors=True,
                                      torch_dtype=torch.bfloat16)
        _model = m.eval().cuda()
        log.info("model loaded in %.0fs, %.1f GiB allocated", time.time() - t0,
                 torch.cuda.memory_allocated() / 2**30)
    except Exception as e:  # surfaced in the UI status line
        _load_error = f"{type(e).__name__}: {e}"
        log.exception("model load failed")


class QueueStreamer:
    """Stands in for transformers.TextStreamer inside the remote code so tokens reach the UI."""

    def __init__(self, tokenizer, skip_prompt=False, skip_special_tokens=False, **_):
        self.tok, self.ids, self.q = tokenizer, [], _stream_q

    def put(self, value):
        self.ids.extend(value.tolist() if value.dim() else [int(value)])
        if len(self.ids) % 16 == 0:
            self.q.put(("partial", self.tok.decode(self.ids, skip_special_tokens=False), len(self.ids)))

    def end(self):
        self.q.put(("partial", self.tok.decode(self.ids, skip_special_tokens=False), len(self.ids)))


_stream_q = queue.Queue()


def _patch_streamer():
    mod = sys.modules[type(_model).__module__]
    mod.TextStreamer = QueueStreamer


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def to_pages(files, job_dir):
    """Images pass through; PDFs are rasterized at PDF_DPI into the job folder (kept for reference)."""
    pages = []
    src_dir = job_dir / "pages"
    for f in files:
        p = Path(f if isinstance(f, str) else f.name)
        if p.suffix.lower() == ".pdf":
            src_dir.mkdir(exist_ok=True)
            doc = fitz.open(p)
            mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
            for i, page in enumerate(doc):
                if len(pages) >= MAX_PAGES:
                    break
                out = src_dir / f"{p.stem}_p{i + 1:04d}.png"
                page.get_pixmap(matrix=mat).save(str(out))
                pages.append(str(out))
            doc.close()
        else:
            pages.append(str(p))
        if len(pages) >= MAX_PAGES:
            break
    return pages[:MAX_PAGES]


# Unlimited OCR 2 layout format (observed 2026-11-06; the bundled _uocr_save_results only knows the older
# DeepSeek <|ref|>/<|det|> tags):  <PAGE> ... <BLOCK>type[<LEVELn>][x1, y1, x2, y2][<CHILD>]<FORK>content
# Boxes are on a 0-1000 scale relative to the page image.
BLOCK_RE = re.compile(r"^([A-Za-z_\-]+)(?:<LEVEL(\d)>)?\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\](?:<CHILD>)?<FORK>(.*)$", re.S)
FIGURE_TYPES = {"image", "figure", "picture", "photo", "chart", "graphic", "seal", "logo", "diagram"}
FORMULA_TYPES = {"formula", "equation", "interline_equation", "display_formula", "isolate_formula"}
SKIP_TYPES = {"header", "footer", "page_header", "page_footer", "page_number", "number", "abandon"}
BOX_COLORS = {"title": (124, 58, 237), "text": (59, 130, 246), "table": (16, 185, 129), "formula": (234, 179, 8)}


def parse_blocks(raw):
    """raw model output -> list of pages, each a list of (type, level, box, content)."""
    pages_txt = raw.split("<PAGE>")
    pages_txt = pages_txt[1:] if len(pages_txt) > 1 else pages_txt
    out = []
    for ptxt in pages_txt:
        blocks = []
        for chunk in ptxt.split("<BLOCK>"):
            chunk = chunk.strip()
            if not chunk:
                continue
            m = BLOCK_RE.match(chunk)
            if m:
                t, lvl, x1, y1, x2, y2, body = m.groups()
                blocks.append((t.lower(), int(lvl) if lvl else None,
                               tuple(int(v) for v in (x1, y1, x2, y2)), body.strip()))
            else:
                blocks.append(("text", None, None, chunk))
        out.append(blocks)
    return out


def blocks_to_markdown(pages_blocks, page_imgs=None, img_dir=None):
    """Markdown with headings, HTML tables, $$ formulas; figures cropped to img_dir when page images are given."""
    parts = []
    for pi, blocks in enumerate(pages_blocks):
        md, fig_n = [], 0
        for t, lvl, box, body in blocks:
            if t in SKIP_TYPES:
                continue
            if t in FIGURE_TYPES or (not body and t not in ("other",)):
                if page_imgs and img_dir is not None and box and pi < len(page_imgs):
                    im = page_imgs[pi]
                    w, h = im.size
                    crop = im.crop((box[0] * w // 1000, box[1] * h // 1000, box[2] * w // 1000, box[3] * h // 1000))
                    if crop.size[0] > 4 and crop.size[1] > 4:
                        img_dir.mkdir(exist_ok=True)
                        name = f"page{pi + 1}_fig{fig_n}.jpg"
                        crop.convert("RGB").save(img_dir / name, quality=92)
                        md.append(f"![{t}](images/{name})")
                        fig_n += 1
                if body:
                    md.append(f"*{body}*")
                continue
            if not body:
                continue
            if t == "title":
                md.append("#" * min(max(lvl or 1, 1), 6) + " " + body.replace("\n", " "))
            elif t in FORMULA_TYPES:
                b = body.strip()
                md.append(b if b.startswith(("$$", "\\[")) else f"$$\n{b.strip('$')}\n$$")
            elif t in ("caption", "figure_caption", "table_caption", "image_caption", "chart_caption", "table_footnote"):
                md.append(f"*{body}*")
            else:
                md.append(body)
        parts.append("\n\n".join(md))
    return "\n\n---\n\n".join(parts).strip() + "\n"


def draw_boxes(pages_blocks, page_imgs, job_dir):
    from PIL import ImageDraw
    paths = []
    for pi, (blocks, im) in enumerate(zip(pages_blocks, page_imgs)):
        im = im.convert("RGB").copy()
        d = ImageDraw.Draw(im)
        w, h = im.size
        lw = max(2, w // 400)
        for t, _, box, _ in blocks:
            if not box:
                continue
            c = BOX_COLORS.get(t, (216, 175, 98))
            xy = (box[0] * w / 1000, box[1] * h / 1000, box[2] * w / 1000, box[3] * h / 1000)
            d.rectangle(xy, outline=c, width=lw)
            d.text((xy[0] + 3, max(0, xy[1] - 12 - lw)), t, fill=c)
        p = job_dir / f"result_with_boxes_{pi}.jpg"
        im.save(p, quality=88)
        paths.append(str(p))
    return paths


def clean_preview(text):
    """Live view while tokens stream: same conversion as the saved file, minus figure crops."""
    try:
        return blocks_to_markdown(parse_blocks(text))
    except Exception:
        return re.sub(r"<BLOCK>[^<]*?(?:<LEVEL\d>)?\[[\d,\s]+\](?:<CHILD>)?<FORK>", "\n", text).replace("<PAGE>", "\n---\n")


def fix_md_links(md, job_dir):
    """Make figure-crop links absolute so gr.Markdown can show them."""
    return md.replace("](images/", f"](/gradio_api/file={job_dir}/images/")


def recent_jobs(limit=40):
    jobs = sorted((p for p in OUTPUT_DIR.iterdir() if (p / "result.md").exists()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in jobs[:limit]]


def ui_status():
    if _load_error:
        return f"🔴 Model failed to load: `{_load_error}` — see {LOG_FILE}"
    if _model is None:
        return "🟡 Loading Unlimited OCR 2…"
    used = torch.cuda.memory_allocated() / 2**30
    return f"🟢 Ready · {used:.1f} GiB on GPU · {len(recent_jobs(10**6))} jobs in `{OUTPUT_DIR}`"


# --------------------------------------------------------------------------- #
# OCR job
# --------------------------------------------------------------------------- #
def run_ocr(files, mode_label, ngram_guard):
    if _model is None:
        raise gr.Error(_load_error or "The model is still loading — try again in a moment.")
    if not files:
        raise gr.Error("Add at least one image or PDF.")
    first = Path(files[0] if isinstance(files[0], str) else files[0].name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = OUTPUT_DIR / f"{ts}_{re.sub(r'[^A-Za-z0-9_-]+', '-', first.stem)[:40]}"
    job_dir.mkdir(parents=True)
    pages = to_pages(files, job_dir)
    crop_mode = MODES.get(mode_label)
    n = len(pages)
    log.info("job %s: %d page(s), crop_mode=%s", job_dir.name, n, crop_mode)

    kwargs = dict(prompt="", image_file=pages if n > 1 else pages[0], output_path=str(job_dir),
                  save_results=False, crop_mode=crop_mode, return_dict=True,
                  max_new_tokens=TOKENS_PER_PAGE * n, max_page_tokens=MAX_PAGE_TOKENS)
    if ngram_guard:  # model card's anti-repetition setup: n-gram 35, window 1024 multi-page / 128 single
        kwargs.update(no_repeat_ngram_size=35, ngram_window=1024 if n > 1 else 128)

    result, error = {}, []

    def work():
        try:
            with gpu_runtime.oom_guard("OCR"):
                result.update(_model.infer(_tokenizer, **kwargs))
        except Exception as e:
            error.append(e)
            log.exception("ocr failed")
        finally:
            _stream_q.put(("done", None, None))

    with _lock:
        while not _stream_q.empty():
            _stream_q.get_nowait()
        t0 = time.time()
        threading.Thread(target=work, daemon=True).start()
        yield "", "", f"⏳ Reading {n} page(s)…", gr.update(), None
        while True:
            kind, text, ntok = _stream_q.get()
            if kind == "done":
                break
            yield (clean_preview(text), gr.update(),
                   f"⏳ {n} page(s) · {ntok:,} tokens · {time.time() - t0:.0f}s", gr.update(), None)
        torch.cuda.empty_cache()

    if error:
        shutil.rmtree(job_dir, ignore_errors=True) if not any(job_dir.glob("result*")) else None
        raise gr.Error(str(error[0]))

    elapsed = time.time() - t0
    raw = result.get("text", "")
    (job_dir / "result_raw.md").write_text(raw, encoding="utf-8")
    page_imgs = [Image.open(p).convert("RGB") for p in pages]
    blocks = parse_blocks(raw)
    for stale in job_dir.glob("result_with_boxes_*.jpg"):  # the bundled saver's versions are blank for this format
        stale.unlink()
    shutil.rmtree(job_dir / "images", ignore_errors=True)
    md = blocks_to_markdown(blocks, page_imgs, job_dir / "images")
    md_path = job_dir / "result.md"
    md_path.write_text(md, encoding="utf-8")
    draw_boxes(blocks, page_imgs, job_dir)
    meta = {"files": [str(f if isinstance(f, str) else f.name) for f in files], "pages": n,
            "mode": mode_label, "ngram_guard": bool(ngram_guard), "seconds": round(elapsed, 1),
            "output_tokens": len(result.get("token_ids", [])), "finish_reason": result.get("finish_reason"),
            "pages_out": result.get("num_pages_out"), "model": "baidu/Unlimited-OCR-2"}
    (job_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    boxes = sorted(job_dir.glob("result_with_boxes_*.jpg"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    tps = meta["output_tokens"] / max(elapsed, 1e-6)
    log.info("job %s done: %.0fs, %d tokens", job_dir.name, elapsed, meta["output_tokens"])
    yield (fix_md_links(md, job_dir), md,
           f"✅ {n} page(s) in {elapsed:.0f}s · {meta['output_tokens']:,} tokens ({tps:.0f} tok/s) · saved `{job_dir.name}/`",
           [str(b) for b in boxes], str(md_path))


def open_job(name):
    if not name:
        return gr.update(), gr.update(), gr.update(), None
    d = OUTPUT_DIR / name
    md = (d / "result.md").read_text(encoding="utf-8")
    boxes = sorted(d.glob("result_with_boxes_*.jpg"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    return fix_md_links(md, d), md, [str(b) for b in boxes], str(d / "result.md")


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
#md-out { max-height: 720px; overflow-y: auto; padding: 8px 14px; border:1px solid #4a5568; border-radius:10px; }
#md-out img { max-width: 100%; }
#tip { border-left:3px solid var(--s13-gold); padding:6px 10px; border-radius:6px; font-size:.85rem; }
body.dark #tip { background:#2d2d2d; color:#e0e0e0; }
#s13-footer { text-align:center; color:#9ca3af; font-size:.8rem; padding-top:6px; }
#s13-footer b { color: var(--s13-gold); }
footer { display:none !important; }
"""

# Gradio 6.17 (pinned here by transformers==4.52.1 -> huggingface-hub<1.0) accepts launch(js=...) but never
# sends it to the page (verified 2026-11-06: localStorage stayed empty). So the dark-by-default script goes in
# launch(head=...) instead, re-applied while the app mounts.
THEME_JS = """
() => {
  const apply = () => {
    if (!document.body) return;
    const pref = localStorage.getItem('unlimited-ocr-theme');
    const dark = pref !== 'light';
    document.body.classList.toggle('dark', dark);
    if (!pref) localStorage.setItem('unlimited-ocr-theme', 'dark');
    const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
  };
  apply();
  document.addEventListener('DOMContentLoaded', apply);
  [100, 400, 1000, 2500].forEach(ms => setTimeout(apply, ms));
}
"""
HEAD = "<script>(" + THEME_JS.strip() + ")();</script>"
TOGGLE_JS = """
() => {
  const dark = !document.body.classList.contains('dark');
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('unlimited-ocr-theme', dark ? 'dark' : 'light');
  const b = document.querySelector('#theme-toggle'); if (b) b.textContent = dark ? '☀️' : '🌙';
}
"""

THEME = gr.themes.Soft(primary_hue="violet", secondary_hue="amber", neutral_hue="slate").set(
    body_background_fill_dark="#1e1e1e", block_background_fill_dark="#2d2d2d",
    border_color_primary_dark="#4a5568", body_text_color_dark="#e0e0e0",
    input_background_fill_dark="#2d2d2d", button_secondary_background_fill_dark="#374151",
)

TIP = (f"Drop page images or PDFs (rasterized at {PDF_DPI} DPI, up to {MAX_PAGES} pages). Several files are read "
       "as one document in the order given. Output is Markdown with tables, LaTeX formulas and figure crops.")

with gr.Blocks(title="Unlimited OCR 2 — Seed 13") as demo:
    with gr.Row(elem_id="s13-header"):
        gr.HTML("<div><p class='kicker'>Seed 13 Productions · Dragonsuite</p>"
                "<h1>🐉 Unlimited OCR 2</h1>"
                "<p class='sub'>Images & PDFs → Markdown · tables, formulas, figures · any length</p></div>")
        theme_btn = gr.Button("☀️", elem_id="theme-toggle", scale=0, min_width=44)
    gr.Markdown(TIP, elem_id="tip")
    with gr.Row():
        with gr.Column(scale=4):
            files = gr.File(label="Pages (images or PDF)", file_count="multiple",
                            file_types=["image", ".pdf"], type="filepath")
            mode = gr.Radio(list(MODES), value=list(MODES)[0], label="Mode")
            ngram = gr.Checkbox(value=True, label="Repetition guard (model card's n-gram setting)")
            go = gr.Button("Read document", variant="primary", elem_id="go-btn")
            status = gr.Markdown(ui_status())
            history = gr.Dropdown(recent_jobs(), label=f"Previous jobs — {OUTPUT_DIR}", value=None)
            download = gr.File(label="result.md", interactive=False)
            boxes = gr.Gallery(label="Detected layout", columns=3, height=320, object_fit="contain")
        with gr.Column(scale=6):
            with gr.Tabs():
                with gr.Tab("Rendered"):
                    rendered = gr.Markdown(elem_id="md-out", latex_delimiters=[
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "\\[", "right": "\\]", "display": True},
                        {"left": "$", "right": "$", "display": False},
                        {"left": "\\(", "right": "\\)", "display": False}])
                with gr.Tab("Markdown source"):
                    source = gr.Code(language="markdown", lines=30, interactive=False)
    gr.HTML("<div id='s13-footer'>Model: Baidu Unlimited OCR 2 (MIT) · <b>Seed 13 Productions</b> · outputs in "
            f"<code>{OUTPUT_DIR}</code></div>")

    theme_btn.click(fn=None, js=TOGGLE_JS)
    go.click(run_ocr, [files, mode, ngram], [rendered, source, status, boxes, download],
             api_name="ocr", concurrency_limit=1)
    history.change(open_job, history, [rendered, source, boxes, download], api_name=False)
    demo.load(lambda: (ui_status(), gr.update(choices=recent_jobs())), None, [status, history], api_name=False)
    timer = gr.Timer(5)
    timer.tick(ui_status, None, status, api_name=False)


def _startup():
    load_model()
    if _model is not None:
        _patch_streamer()


if __name__ == "__main__":
    log.info("Unlimited OCR 2 Studio on %s:%d — model %s — outputs %s", HOST, PORT, MODEL_DIR, OUTPUT_DIR)
    if not torch.cuda.is_available():
        log.error("CUDA not available — refusing to start")
        sys.exit(1)
    threading.Thread(target=_startup, daemon=True).start()
    demo.queue(max_size=8, default_concurrency_limit=1)
    demo.launch(server_name=HOST, server_port=PORT, share=False, show_error=True,
                favicon_path=FAVICON if Path(FAVICON).exists() else None,
                allowed_paths=[str(OUTPUT_DIR)], theme=THEME, css=CSS, head=HEAD)
