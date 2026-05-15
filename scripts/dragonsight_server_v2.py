#!/usr/bin/env python3
"""
Dragonsight 4.6 - Local HTTP Server with Ollama Proxy + Florence-2
Serves dragonsight4.html on port 8080
Proxies /api/ollama/* to localhost:11434 (avoids CORS issues)
Runs Florence-2 locally for /api/florence/analyze
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import base64
import io
from pathlib import Path
from datetime import datetime
from socketserver import ThreadingMixIn

PORT = 8080
OLLAMA_PORT = 11434
DOLPHIN_PORT = 8025
MEDIA_DIR = Path("/srv/containers/edq/media")
HTML_FILE = MEDIA_DIR / "dragonsight4.html"
OUTPUT_DIR = Path.home() / "ai_generated" / "dragonsight"

# Florence-2 lazy state — loaded on first request
_florence_model = None
_florence_processor = None
_florence_error = None


def _load_florence():
    """Load Florence-2 model and processor on first call. Returns (model, processor, error)."""
    global _florence_model, _florence_processor, _florence_error
    if _florence_model is not None:
        return _florence_model, _florence_processor, None
    if _florence_error is not None:
        return None, None, _florence_error
    try:
        import torch
        from transformers import AutoProcessor, AutoModelForCausalLM
        MODEL_ID = "multimodalart/Florence-2-large-no-flash-attn"
        print("Loading Florence-2 (first request)…")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _florence_model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            trust_remote_code=True,
            attn_implementation="eager",
        ).to(device)
        _florence_processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        print(f"Florence-2 loaded on {device}")
        return _florence_model, _florence_processor, None
    except Exception as e:
        _florence_error = str(e)
        return None, None, _florence_error


def _run_florence(image_pil, task):
    """Run a Florence-2 task. Returns parsed string result."""
    import torch
    model, processor, err = _load_florence()
    if err:
        raise RuntimeError(err)
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    inputs = processor(text=task, images=image_pil, return_tensors="pt")
    inputs = {k: v.to(device, dtype if v.is_floating_point() else None) for k, v in inputs.items()}
    with torch.inference_mode():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=512,
            do_sample=False,
            num_beams=3,
        )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(
        generated_text, task=task, image_size=(image_pil.width, image_pil.height)
    )
    return parsed[task]


def _analyze_with_florence(image_b64: str) -> dict:
    """Run all four Florence-2 tasks and return structured result."""
    from PIL import Image
    img_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    detailed  = _run_florence(image, "<MORE_DETAILED_CAPTION>")
    concise   = _run_florence(image, "<CAPTION>")

    # Dense region labels → tags
    region_result = _run_florence(image, "<DENSE_REGION_CAPTION>")
    if isinstance(region_result, dict) and "labels" in region_result:
        labels = region_result["labels"]
        tags = ", ".join(dict.fromkeys(l.strip() for l in labels if l.strip()))
    else:
        # Fallback: extract nouns from the caption
        tags = concise

    return {
        "detailed": detailed,
        "concise":  concise,
        "tags":     tags,
        "filename_hint": concise,   # JS will sanitize this into a filename
    }


class DragonsightHandler(http.server.BaseHTTPRequestHandler):
    """Serve dragonsight4.html and proxy Ollama API calls."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ['/', '/dragonsight4.html']:
            try:
                with open(HTML_FILE, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, f"{HTML_FILE} not found")
        elif self.path == '/media/dragonsight4.js':
            js_file = MEDIA_DIR / 'dragonsight4.js'
            try:
                with open(js_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript')
                self.send_header('Content-Length', len(content))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "dragonsight4.js not found")
        else:
            self.send_error(404, f"Path {self.path} not found")

    def do_POST(self):
        if self.path == '/api/ollama/chat':
            self._proxy_ollama()
        elif self.path == '/api/florence/analyze':
            self._handle_florence()
        elif self.path == '/api/dolphin/analyze':
            self._proxy_dolphin()
        elif self.path == '/api/save':
            self._save_metadata()
        else:
            self.send_error(404, f"Path {self.path} not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length else b''

    def _json_response(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _proxy_ollama(self):
        body = self._read_body()
        if not body:
            self.send_error(400, "No request body")
            return
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{OLLAMA_PORT}/api/chat',
                data=body, method='POST'
            )
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(result))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.URLError as e:
            self._json_response(503, {'error': f'Ollama unavailable: {e}'})
        except Exception as e:
            self._json_response(500, {'error': f'Server error: {e}'})

    def _handle_florence(self):
        body = self._read_body()
        if not body:
            self._json_response(400, {'error': 'No request body'})
            return
        try:
            req = json.loads(body)
            image_b64 = req.get('image_base64', '')
            if not image_b64:
                self._json_response(400, {'error': 'Missing image_base64'})
                return
            result = _analyze_with_florence(image_b64)
            self._json_response(200, result)
        except Exception as e:
            import traceback
            self._json_response(500, {'error': str(e), 'trace': traceback.format_exc()})

    def _proxy_dolphin(self):
        body = self._read_body()
        if not body:
            self._json_response(400, {'error': 'No request body'})
            return
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{DOLPHIN_PORT}/analyze',
                data=body,
                method='POST',
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(result))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.URLError as e:
            self._json_response(503, {'error': f'Dolphin Vision unavailable on port {DOLPHIN_PORT}: {e}'})
        except Exception as e:
            self._json_response(500, {'error': f'Server error: {e}'})

    def _save_metadata(self):
        body = self._read_body()
        if not body:
            self._json_response(400, {'error': 'No request body'})
            return
        try:
            data = json.loads(body)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            suggested = data.get('suggested_name', '').strip()
            original = data.get('original_name', data.get('original_filename', 'unknown')).strip()
            base_name = Path(suggested or original).stem or 'unknown'
            safe_name = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in base_name).strip('_') or 'unknown'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = OUTPUT_DIR / f"{safe_name}_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._json_response(200, {'success': True, 'file': str(output_file)})
            print(f"   Saved: {output_file}")
        except json.JSONDecodeError as e:
            self._json_response(400, {'error': f'Invalid JSON: {e}'})
        except Exception as e:
            self._json_response(500, {'error': f'Save error: {e}'})


class ReuseTCPServer(ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


if __name__ == "__main__":
    if not HTML_FILE.exists():
        print(f"ERROR: {HTML_FILE} not found")
        exit(1)

    print(f"🐉 Dragonsight 4.6")
    print(f"   Serving:      {HTML_FILE}")
    print(f"   Port:         {PORT}")
    print(f"   LAN:          http://192.168.7.226:{PORT}")
    print(f"   Backends:     Ollama (chat API) · Florence-2 (local) · Gemini · LM Studio · Dolphin")
    print(f"   Florence-2:   loads on first request (~10s)")
    print()

    with ReuseTCPServer(("", PORT), DragonsightHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Dragonsight 4.6 stopped")
