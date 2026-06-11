#!/usr/bin/env python3
"""Downloads gallery — lightbox + slideshow + video support, port 8060."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image

DOWNLOADS = Path.home() / "Downloads"
AI_GENERATED = Path.home() / "ai_generated"
THUMB_CACHE = Path("/tmp/dl_thumbs")
THUMB_SIZE = (320, 320)
PORT = 8060
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".avif"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

THUMB_CACHE.mkdir(exist_ok=True)


def resolve_root(key: str) -> Path | None:
    """Map an allowlisted root key to a directory.

    'downloads' (or empty) -> ~/Downloads; any other key -> ~/ai_generated/<key>.
    The key must be a single path component (no traversal). We validate the name
    BEFORE resolving, then resolve — output_dir entries are often symlinks into
    project dirs, so resolving first would push the target outside ~/ai_generated.
    """
    if not key or key == "downloads":
        return DOWNLOADS
    if "/" in key or key in (".", ".."):
        return None
    p = AI_GENERATED / key
    if not p.is_dir():
        return None
    return p.resolve()


def safe_path(name: str, root: Path) -> Path | None:
    rr = root.resolve()
    p = (rr / name).resolve()
    try:
        p.relative_to(rr)
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


def make_video_thumb(src: Path) -> Path | None:
    tp = thumb_path(src)
    if not tp.exists():
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", "1", "-i", str(src),
                    "-vframes", "1",
                    "-vf", "scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:black",
                    str(tp),
                ],
                capture_output=True,
                timeout=15,
            )
            if result.returncode != 0 or not tp.exists():
                return None
        except Exception:
            return None
    return tp if tp.exists() else None


def media_files(root: Path) -> list[dict]:
    files = [
        f for f in root.iterdir()
        if f.is_file() and f.suffix.lower() in MEDIA_EXTS
    ]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "video": f.suffix.lower() in VIDEO_EXTS} for f in files]


def gallery_html(root_key: str, root: Path) -> bytes:
    is_dl = root == DOWNLOADS
    title = "Downloads Gallery" if is_dl else f"{root.name} — Gallery"
    where = "~/Downloads" if is_dl else f"~/ai_generated/{root_key}"
    media = media_files(root)
    media_json = json.dumps(media)
    root_json = json.dumps(root_key)
    n_img = sum(1 for m in media if not m["video"])
    n_vid = sum(1 for m in media if m["video"])

    parts = []
    if n_img:
        parts.append(f"{n_img} image{'s' if n_img != 1 else ''}")
    if n_vid:
        parts.append(f"{n_vid} video{'s' if n_vid != 1 else ''}")
    count_text = ", ".join(parts) if parts else f"No media in {where}"

    cards = []
    for i, m in enumerate(media):
        name = m["name"]
        esc = name.replace("&", "&amp;").replace('"', "&quot;")
        rq = f"?root={root_key}"
        if m["video"]:
            cards.append(
                f'<div class="card video-card" data-idx="{i}" onclick="openLb({i})">'
                f'<div class="thumb-wrap">'
                f'<img src="/thumb/{esc}{rq}" loading="lazy" alt="{esc}">'
                f'<div class="play-icon">&#9654;</div>'
                f'</div>'
                f'<div class="label" title="{esc}">{esc}</div>'
                f'</div>'
            )
        else:
            cards.append(
                f'<div class="card" data-idx="{i}" onclick="openLb({i})">'
                f'<img src="/thumb/{esc}{rq}" loading="lazy" alt="{esc}">'
                f'<div class="label" title="{esc}">{esc}</div>'
                f'</div>'
            )

    cards_html = "\n".join(cards) if cards else f"<p class='empty'>No media in {where}</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1a1a1a; color: #e0e0e0; font-family: system-ui, sans-serif; min-height: 100vh; overflow-x: hidden; }}

  /* header */
  header {{ display: flex; align-items: center; justify-content: space-between;
            padding: 12px 20px; background: #242424; border-bottom: 1px solid #333;
            position: sticky; top: 0; z-index: 5; gap: 12px; }}
  h1 {{ font-size: 1rem; font-weight: 600; color: #ccc; white-space: nowrap; }}
  .meta {{ font-size: 0.8rem; color: #666; flex: 1; }}
  .btn {{ background: #333; border: 1px solid #444; color: #ccc; padding: 5px 13px;
          border-radius: 6px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }}
  .btn:hover {{ background: #444; }}
  .btn-ss {{ background: #1a3a5a; border-color: #2a6a9a; color: #7ab8e8; }}
  .btn-ss:hover {{ background: #2a4a7a; }}
  .hidden {{ display: none !important; }}

  /* grid */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
           gap: 10px; padding: 14px; }}
  .card {{ background: #242424; border: 1px solid #2e2e2e; border-radius: 8px;
           overflow: hidden; cursor: pointer; transition: border-color .15s, transform .15s; }}
  .card:hover {{ border-color: #555; transform: translateY(-2px); }}
  .card > img {{ width: 100%; height: 200px; object-fit: cover; display: block; background: #111; }}
  .label {{ padding: 7px 10px; font-size: 0.7rem; color: #888; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis; }}
  .empty {{ padding: 60px; text-align: center; color: #444; grid-column: 1/-1; }}

  /* video card */
  .video-card .thumb-wrap {{ position: relative; width: 100%; height: 200px; background: #111; }}
  .video-card .thumb-wrap img {{ width: 100%; height: 200px; object-fit: cover; display: block; }}
  .play-icon {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                width: 48px; height: 48px; background: rgba(0,0,0,.65); border-radius: 50%;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.2rem; color: #fff; pointer-events: none; }}

  /* lightbox */
  #lb {{ position: fixed; inset: 0; background: rgba(0,0,0,.92); z-index: 100;
         display: flex; align-items: center; justify-content: center; }}
  #lb.hidden {{ display: none; }}

  #lb-prev, #lb-next {{ flex-shrink: 0; background: rgba(255,255,255,.07);
    border: none; color: #ccc; font-size: 2.4rem; cursor: pointer; padding: 0 18px;
    align-self: stretch; transition: background .15s; user-select: none; }}
  #lb-prev:hover, #lb-next:hover {{ background: rgba(255,255,255,.14); color: #fff; }}
  #lb-prev:disabled, #lb-next:disabled {{ opacity: .2; cursor: default; }}

  #lb-body {{ display: flex; flex-direction: column; align-items: center;
              max-width: calc(100vw - 120px); max-height: 100vh; overflow: hidden; }}
  #lb-img {{ max-width: 100%; max-height: calc(100vh - 80px); object-fit: contain; display: block; }}
  #lb-vid {{ max-width: 100%; max-height: calc(100vh - 80px); display: none; background: #000; outline: none; }}

  #lb-bar {{ width: 100%; display: flex; align-items: center; justify-content: space-between;
             padding: 10px 16px; gap: 8px; background: #1a1a1a; min-height: 52px; flex-shrink: 0; }}
  #lb-name {{ font-size: 0.78rem; color: #888; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; flex: 1; min-width: 0; }}
  #lb-counter {{ font-size: 0.78rem; color: #555; white-space: nowrap; }}
  .lb-btn {{ background: #333; border: 1px solid #444; color: #ccc; padding: 5px 11px;
             border-radius: 6px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }}
  .lb-btn:hover {{ background: #444; }}
  #lb-del {{ background: #5a1a1a; border-color: #8b2020; color: #f87171; }}
  #lb-del:hover {{ background: #7a2020; }}
  #lb-ss-pause {{ background: #1a3a5a; border-color: #2a6a9a; color: #7ab8e8; }}
  #lb-ss-pause:hover {{ background: #2a4a7a; }}

  /* slideshow progress bar */
  #ss-bar {{ position: fixed; bottom: 0; left: 0; height: 3px; background: #4a9af8; width: 0; z-index: 110; }}

  #lb-close {{ position: fixed; top: 14px; right: 18px; background: rgba(255,255,255,.1);
               border: none; color: #ccc; font-size: 1.4rem; cursor: pointer; z-index: 110;
               width: 36px; height: 36px; border-radius: 50%; line-height: 36px; text-align: center; }}
  #lb-close:hover {{ background: rgba(255,255,255,.2); color: #fff; }}
</style>
</head>
<body>

<header>
  <h1>&#128193; {title}</h1>
  <span class="meta" id="hdr-meta">{count_text}</span>
  <button class="btn btn-ss" id="ss-btn" onclick="toggleSlideshow()">&#9654; Slideshow</button>
  <button class="btn" onclick="location.reload()">&#8635; Refresh</button>
</header>

<div class="grid" id="grid">
{cards_html}
</div>

<div id="lb" class="hidden">
  <button id="lb-close" onclick="closeLb()">&#10005;</button>
  <button id="lb-prev" onclick="navigate(-1)">&#8249;</button>
  <div id="lb-body">
    <img id="lb-img" src="" alt="">
    <video id="lb-vid" controls preload="metadata"></video>
    <div id="lb-bar">
      <span id="lb-name"></span>
      <span id="lb-counter"></span>
      <button id="lb-ss-pause" class="lb-btn hidden" onclick="toggleSsPause()">&#9646;&#9646; Pause</button>
      <button id="lb-del" class="lb-btn" onclick="deleteMedia()">&#128465; Delete</button>
    </div>
  </div>
  <button id="lb-next" onclick="navigate(1)">&#8250;</button>
</div>
<div id="ss-bar"></div>

<script>
  const mediaItems = {media_json};
  const ROOT_KEY = {root_json};
  function rq(p) {{ return p + '?root=' + encodeURIComponent(ROOT_KEY); }}
  let cur = 0;
  let ssActive = false;
  let ssPaused = false;
  let ssTimer = null;
  const SS_IMG_MS = 4000;
  const SS_VID_MAX_MS = 60000;

  const lb        = document.getElementById('lb');
  const lbImg     = document.getElementById('lb-img');
  const lbVid     = document.getElementById('lb-vid');
  const lbName    = document.getElementById('lb-name');
  const lbCtr     = document.getElementById('lb-counter');
  const lbPrev    = document.getElementById('lb-prev');
  const lbNext    = document.getElementById('lb-next');
  const lbSsPause = document.getElementById('lb-ss-pause');
  const ssBtn     = document.getElementById('ss-btn');
  const ssBar     = document.getElementById('ss-bar');

  function openLb(idx) {{
    cur = idx;
    lb.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    render();
  }}

  function closeLb() {{
    stopSlideshow();
    lbVid.pause();
    lbVid.src = '';
    lb.classList.add('hidden');
    document.body.style.overflow = '';
  }}

  function render() {{
    const item = mediaItems[cur];
    lbVid.removeEventListener('ended', onVidEnded);
    clearSsTimer();

    if (item.video) {{
      lbImg.style.display = 'none';
      lbImg.src = '';
      lbVid.pause();
      lbVid.style.display = 'block';
      lbVid.poster = rq('/thumb/' + encodeURIComponent(item.name));
      lbVid.src = rq('/img/' + encodeURIComponent(item.name));
      lbVid.load();
      lbVid.play().catch(function() {{}});
    }} else {{
      lbVid.pause();
      lbVid.src = '';
      lbVid.style.display = 'none';
      lbImg.style.display = 'block';
      lbImg.src = rq('/img/' + encodeURIComponent(item.name));
    }}

    lbName.textContent = item.name;
    lbCtr.textContent = (cur + 1) + ' / ' + mediaItems.length;
    lbPrev.disabled = cur === 0;
    lbNext.disabled = cur === mediaItems.length - 1;

    if (ssActive && !ssPaused) scheduleNext(item.video);
  }}

  function navigate(dir) {{
    const next = cur + dir;
    if (next >= 0 && next < mediaItems.length) openLb(next);
  }}

  /* ── slideshow ── */
  function toggleSlideshow() {{
    if (ssActive) stopSlideshow();
    else {{
      ssActive = true;
      ssPaused = false;
      ssBtn.textContent = '■ Stop';
      lbSsPause.classList.remove('hidden');
      lbSsPause.textContent = '⏸ Pause';
      if (lb.classList.contains('hidden')) openLb(0);
      else render();
    }}
  }}

  function stopSlideshow() {{
    if (!ssActive) return;
    ssActive = false;
    ssPaused = false;
    clearSsTimer();
    ssBtn.textContent = '▶ Slideshow';
    lbSsPause.classList.add('hidden');
  }}

  function toggleSsPause() {{
    if (!ssActive) return;
    if (ssPaused) {{
      ssPaused = false;
      lbSsPause.textContent = '⏸ Pause';
      if (mediaItems[cur].video) lbVid.play().catch(function() {{}});
      scheduleNext(mediaItems[cur].video);
    }} else {{
      ssPaused = true;
      lbSsPause.textContent = '▶ Resume';
      clearSsTimer();
      lbVid.pause();
    }}
  }}

  function clearSsTimer() {{
    if (ssTimer) {{ clearTimeout(ssTimer); ssTimer = null; }}
    lbVid.removeEventListener('ended', onVidEnded);
    ssBar.style.transition = 'none';
    ssBar.style.width = '0';
  }}

  function scheduleNext(isVideo) {{
    const ms = isVideo ? SS_VID_MAX_MS : SS_IMG_MS;
    if (isVideo) lbVid.addEventListener('ended', onVidEnded, {{once: true}});
    ssTimer = setTimeout(advanceSs, ms);
    requestAnimationFrame(function() {{
      ssBar.style.transition = 'width ' + ms + 'ms linear';
      ssBar.style.width = '100%';
    }});
  }}

  function onVidEnded() {{
    clearSsTimer();
    advanceSs();
  }}

  function advanceSs() {{
    ssTimer = null;
    if (!ssActive || ssPaused) return;
    openLb((cur + 1) % mediaItems.length);
  }}

  /* ── delete ── */
  async function deleteMedia() {{
    const item = mediaItems[cur];
    if (!confirm('Delete ' + item.name + '?')) return;
    const res = await fetch(rq('/delete/' + encodeURIComponent(item.name)), {{method: 'POST'}});
    if (!res.ok) {{ alert('Delete failed'); return; }}

    const card = document.querySelector('.card[data-idx="' + cur + '"]');
    if (card) card.remove();
    mediaItems.splice(cur, 1);
    document.querySelectorAll('.card').forEach(function(c, i) {{
      c.dataset.idx = i;
      c.onclick = (function(idx) {{ return function() {{ openLb(idx); }}; }})(i);
    }});

    const ni = mediaItems.filter(function(m) {{ return !m.video; }}).length;
    const nv = mediaItems.filter(function(m) {{ return m.video; }}).length;
    const parts = [];
    if (ni) parts.push(ni + ' image' + (ni !== 1 ? 's' : ''));
    if (nv) parts.push(nv + ' video' + (nv !== 1 ? 's' : ''));
    document.getElementById('hdr-meta').textContent = parts.join(', ') || 'Empty';

    if (mediaItems.length === 0) {{ closeLb(); return; }}
    if (cur >= mediaItems.length) cur = mediaItems.length - 1;
    render();
  }}

  document.addEventListener('keydown', function(e) {{
    if (lb.classList.contains('hidden')) return;
    if (e.key === 'ArrowLeft')  navigate(-1);
    if (e.key === 'ArrowRight') navigate(1);
    if (e.key === 'Escape')     closeLb();
    if (e.key === ' ' && ssActive) {{ e.preventDefault(); toggleSsPause(); }}
  }});

  lb.addEventListener('click', function(e) {{ if (e.target === lb) closeLb(); }});
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

    def serve_file(self, src: Path):
        """Stream a file with HTTP range request support (required for video seeking)."""
        mime = mimetypes.guess_type(str(src))[0] or "application/octet-stream"
        file_size = src.stat().st_size
        range_hdr = self.headers.get("Range", "")

        if range_hdr.startswith("bytes="):
            spec = range_hdr[6:].split(",")[0].strip()
            parts = spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with src.open("rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with src.open("rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break

    def root_for_request(self) -> tuple[str, Path] | None:
        parsed = urlparse(self.path)
        root_key = parse_qs(parsed.query).get("root", [""])[0]
        root = resolve_root(root_key)
        if root is None:
            return None
        return root_key, root

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        rr = self.root_for_request()
        if rr is None:
            self.send_error(404); return
        root_key, root = rr

        if path in ("/", "/index.html"):
            self.send_bytes(gallery_html(root_key, root), "text/html; charset=utf-8")

        elif path.startswith("/thumb/"):
            src = safe_path(path[7:], root)
            if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXTS:
                self.send_error(404); return
            try:
                if src.suffix.lower() in VIDEO_EXTS:
                    tp = make_video_thumb(src)
                    if tp is None:
                        self.send_error(404); return
                else:
                    tp = make_thumb(src)
                self.send_bytes(tp.read_bytes(), "image/jpeg")
            except Exception:
                self.send_error(500)

        elif path.startswith("/img/"):
            src = safe_path(path[5:], root)
            if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXTS:
                self.send_error(404); return
            try:
                self.serve_file(src)
            except Exception:
                self.send_error(500)

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        rr = self.root_for_request()
        if rr is None:
            self.send_error(404); return
        _, root = rr

        if path.startswith("/delete/"):
            src = safe_path(path[8:], root)
            if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXTS:
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
