#!/usr/bin/env python3
"""Downloads image gallery — lightbox + delete, port 8060."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

DOWNLOADS = Path.home() / "Downloads"
THUMB_CACHE = Path("/tmp/dl_thumbs")
THUMB_SIZE = (320, 320)
PORT = 8060
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".avif"}

THUMB_CACHE.mkdir(exist_ok=True)


def safe_path(name: str) -> Path | None:
    """Resolve name to a path strictly inside DOWNLOADS, or return None."""
    p = (DOWNLOADS / name).resolve()
    try:
        p.relative_to(DOWNLOADS.resolve())
        return p
    except ValueError:
        return None


def thumb_path(src: Path) -> Path:
    key = hashlib.md5(f"{src}{src.stat().st_mtime}".encode()).hexdigest()
    return THUMB_CACHE / f"{key}.jpg"


def make_thumb(src: Path) -> Path:
    tp = thumb_path(src)
    if not tp.exists():
        img = Image.open(src).convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        img.save(tp, "JPEG", quality=82)
    return tp


def image_files() -> list[Path]:
    files = [
        f for f in DOWNLOADS.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    ]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def gallery_html() -> bytes:
    files = image_files()
    names_json = json.dumps([f.name for f in files])

    cards = []
    for i, f in enumerate(files):
        name = f.name
        esc = name.replace("&", "&amp;").replace('"', "&quot;")
        cards.append(
            f'<div class="card" data-idx="{i}" onclick="openLb({i})">'
            f'<img src="/thumb/{esc}" loading="lazy" alt="{esc}">'
            f'<div class="label" title="{esc}">{esc}</div>'
            f'</div>'
        )

    cards_html = "\n".join(cards) if cards else "<p class='empty'>No images in ~/Downloads</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Downloads Gallery</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1a1a1a; color: #e0e0e0; font-family: system-ui, sans-serif; min-height: 100vh; overflow-x: hidden; }}

  /* ── header ── */
  header {{ display: flex; align-items: center; justify-content: space-between;
            padding: 12px 20px; background: #242424; border-bottom: 1px solid #333;
            position: sticky; top: 0; z-index: 5; gap: 12px; }}
  h1 {{ font-size: 1rem; font-weight: 600; color: #ccc; white-space: nowrap; }}
  .meta {{ font-size: 0.8rem; color: #666; flex: 1; }}
  .btn {{ background: #333; border: 1px solid #444; color: #ccc; padding: 5px 13px;
          border-radius: 6px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }}
  .btn:hover {{ background: #444; }}

  /* ── grid ── */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
           gap: 10px; padding: 14px; }}
  .card {{ background: #242424; border: 1px solid #2e2e2e; border-radius: 8px;
           overflow: hidden; cursor: pointer; transition: border-color .15s, transform .15s; }}
  .card:hover {{ border-color: #555; transform: translateY(-2px); }}
  .card img {{ width: 100%; height: 200px; object-fit: cover; display: block; background: #1a1a1a; }}
  .label {{ padding: 7px 10px; font-size: 0.7rem; color: #888; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis; }}
  .empty {{ padding: 60px; text-align: center; color: #444; grid-column: 1/-1; }}

  /* ── lightbox ── */
  #lb {{ position: fixed; inset: 0; background: rgba(0,0,0,.92); z-index: 100;
         display: flex; align-items: center; justify-content: center; gap: 0; }}
  #lb.hidden {{ display: none; }}

  #lb-prev, #lb-next {{ flex-shrink: 0; background: rgba(255,255,255,.07);
    border: none; color: #ccc; font-size: 2.4rem; cursor: pointer; padding: 0 18px;
    align-self: stretch; transition: background .15s; user-select: none; }}
  #lb-prev:hover, #lb-next:hover {{ background: rgba(255,255,255,.14); color: #fff; }}
  #lb-prev:disabled, #lb-next:disabled {{ opacity: .2; cursor: default; }}

  #lb-body {{ display: flex; flex-direction: column; align-items: center;
              max-width: calc(100vw - 120px); max-height: 100vh; overflow: hidden; }}
  #lb-img {{ max-width: 100%; max-height: calc(100vh - 80px); object-fit: contain;
             display: block; }}

  #lb-bar {{ width: 100%; display: flex; align-items: center; justify-content: space-between;
             padding: 10px 16px; gap: 12px; background: #1a1a1a; min-height: 52px; flex-shrink: 0; }}
  #lb-name {{ font-size: 0.78rem; color: #888; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; flex: 1; }}
  #lb-counter {{ font-size: 0.78rem; color: #555; white-space: nowrap; }}
  #lb-del {{ background: #5a1a1a; border: 1px solid #8b2020; color: #f87171;
             padding: 5px 13px; border-radius: 6px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }}
  #lb-del:hover {{ background: #7a2020; }}

  #lb-close {{ position: fixed; top: 14px; right: 18px; background: rgba(255,255,255,.1);
               border: none; color: #ccc; font-size: 1.4rem; cursor: pointer; z-index: 110;
               width: 36px; height: 36px; border-radius: 50%; line-height: 36px; text-align: center; }}
  #lb-close:hover {{ background: rgba(255,255,255,.2); color: #fff; }}
</style>
</head>
<body>

<header>
  <h1>📁 Downloads Gallery</h1>
  <span class="meta" id="hdr-meta">{len(files)} image{"s" if len(files) != 1 else ""}</span>
  <button class="btn" onclick="location.reload()">↻ Refresh</button>
</header>

<div class="grid" id="grid">
{cards_html}
</div>

<!-- Lightbox -->
<div id="lb" class="hidden">
  <button id="lb-close" onclick="closeLb()">✕</button>
  <button id="lb-prev" onclick="navigate(-1)">‹</button>
  <div id="lb-body">
    <img id="lb-img" src="" alt="">
    <div id="lb-bar">
      <span id="lb-name"></span>
      <span id="lb-counter"></span>
      <button id="lb-del" onclick="deleteImage()">🗑 Delete</button>
    </div>
  </div>
  <button id="lb-next" onclick="navigate(1)">›</button>
</div>

<script>
  let images = {names_json};
  let cur = 0;

  const lb     = document.getElementById('lb');
  const lbImg  = document.getElementById('lb-img');
  const lbName = document.getElementById('lb-name');
  const lbCtr  = document.getElementById('lb-counter');
  const lbPrev = document.getElementById('lb-prev');
  const lbNext = document.getElementById('lb-next');

  function openLb(idx) {{
    cur = idx;
    lb.classList.remove('hidden');
    render();
    document.body.style.overflow = 'hidden';
  }}

  function closeLb() {{
    lb.classList.add('hidden');
    document.body.style.overflow = '';
  }}

  function render() {{
    const name = images[cur];
    lbImg.src = '/img/' + encodeURIComponent(name);
    lbName.textContent = name;
    lbCtr.textContent = (cur + 1) + ' / ' + images.length;
    lbPrev.disabled = cur === 0;
    lbNext.disabled = cur === images.length - 1;
  }}

  function navigate(dir) {{
    const next = cur + dir;
    if (next >= 0 && next < images.length) openLb(next);
  }}

  async function deleteImage() {{
    const name = images[cur];
    if (!confirm('Delete ' + name + '?')) return;

    const res = await fetch('/delete/' + encodeURIComponent(name), {{ method: 'POST' }});
    if (!res.ok) {{ alert('Delete failed'); return; }}

    // remove card from grid
    const card = document.querySelector('.card[data-idx="' + cur + '"]');
    if (card) card.remove();

    // remove from list and reindex remaining cards
    images.splice(cur, 1);
    document.querySelectorAll('.card').forEach((c, i) => {{
      c.dataset.idx = i;
      c.onclick = (e => (idx => () => openLb(idx))(i))();
    }});

    // update header count
    document.getElementById('hdr-meta').textContent =
      images.length + ' image' + (images.length !== 1 ? 's' : '');

    if (images.length === 0) {{ closeLb(); return; }}
    if (cur >= images.length) cur = images.length - 1;
    render();
  }}

  document.addEventListener('keydown', e => {{
    if (lb.classList.contains('hidden')) return;
    if (e.key === 'ArrowLeft')  navigate(-1);
    if (e.key === 'ArrowRight') navigate(1);
    if (e.key === 'Escape')     closeLb();
  }});

  // close on backdrop click
  lb.addEventListener('click', e => {{ if (e.target === lb) closeLb(); }});
</script>
</body>
</html>""".encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_bytes(self, data: bytes, mime: str):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(self.path).split("?")[0]

        if path in ("/", "/index.html"):
            self.send_bytes(gallery_html(), "text/html; charset=utf-8")

        elif path.startswith("/thumb/"):
            src = safe_path(path[7:])
            if not src or not src.is_file() or src.suffix.lower() not in IMAGE_EXTS:
                self.send_error(404); return
            try:
                self.send_bytes(make_thumb(src).read_bytes(), "image/jpeg")
            except Exception:
                self.send_error(500)

        elif path.startswith("/img/"):
            src = safe_path(path[5:])
            if not src or not src.is_file():
                self.send_error(404); return
            mime = mimetypes.guess_type(str(src))[0] or "application/octet-stream"
            self.send_bytes(src.read_bytes(), mime)

        else:
            self.send_error(404)

    def do_POST(self):
        path = unquote(self.path)

        if path.startswith("/delete/"):
            src = safe_path(path[8:])
            if not src or not src.is_file() or src.suffix.lower() not in IMAGE_EXTS:
                self.send_error(404); return
            src.unlink()
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        else:
            self.send_error(404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Downloads gallery → http://192.168.7.226:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
