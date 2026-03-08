#!/usr/bin/env python3
"""
Dragonsight 4 - Local HTTP Server with Ollama Proxy
Serves dragonsight4.html on port 8080
Proxies /api/ollama/* to localhost:11434 (avoids CORS issues)
Saves metadata JSON to ~/ai_generated/dragonsight/
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import os
from pathlib import Path
from datetime import datetime

# Load .env for API keys
_env_path = Path("/srv/containers/edq/.env")
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

PORT = 8080
OLLAMA_PORT = 11434
LMSTUDIO_PORT = 1234
DOLPHIN_PORT = 8025
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
MEDIA_DIR = Path("/srv/containers/edq/media")
HTML_FILE = MEDIA_DIR / "dragonsight4.html"
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/dragonsight"))

class DragonsightHandler(http.server.BaseHTTPRequestHandler):
    """Serve dragonsight4.html and proxy Ollama API calls."""
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests - serve HTML and static media, or return 404."""
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
            return

        if self.path.startswith('/media/'):
            file_path = (MEDIA_DIR / self.path.replace('/media/', '', 1)).resolve()
            if not str(file_path).startswith(str(MEDIA_DIR.resolve())):
                self.send_error(403, "Forbidden")
                return
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, f"{file_path} not found")
                return

            content_type = 'application/octet-stream'
            if file_path.suffix == '.html':
                content_type = 'text/html'
            elif file_path.suffix == '.js':
                content_type = 'application/javascript'
            elif file_path.suffix == '.css':
                content_type = 'text/css'
            elif file_path.suffix == '.svg':
                content_type = 'image/svg+xml'
            elif file_path.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                content_type = f"image/{file_path.suffix.lstrip('.')}"

            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_error(404, f"Path {self.path} not found")
    
    def do_POST(self):
        """Handle POST requests - proxy to Ollama/LM Studio or save metadata."""
        if self.path == '/api/ollama/generate':
            self._proxy_ollama()
        elif self.path == '/api/lmstudio/completions':
            self._proxy_lmstudio()
        elif self.path == '/api/dolphin/analyze':
            self._proxy_dolphin()
        elif self.path == '/api/gemini/generate':
            self._proxy_gemini()
        elif self.path == '/api/save':
            self._save_metadata()
        else:
            self.send_error(404, f"Path {self.path} not found")

    def _save_metadata(self):
        """Save metadata JSON to output directory."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Create output directory if needed
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            # Use AI-suggested filename if present, fall back to original upload name
            suggested = data.get('suggested_name', '').strip()
            original = data.get('original_name', data.get('original_filename', 'unknown')).strip()
            base_name = Path(suggested or original).stem or 'unknown'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = OUTPUT_DIR / f"{base_name}_{timestamp}.json"

            # Save the full JSON
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Return success with file path
            response = json.dumps({
                'success': True,
                'file': str(output_file)
            }).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

            print(f"   Saved: {output_file}")

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            error_msg = f"Save error: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _proxy_ollama(self):
        """Proxy POST requests to Ollama /api/generate."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)

            # Forward to Ollama
            ollama_url = f'http://127.0.0.1:{OLLAMA_PORT}/api/generate'
            req = urllib.request.Request(ollama_url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=300) as response:
                ollama_response = response.read()

            # Return Ollama response with CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(ollama_response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(ollama_response)

        except urllib.error.URLError as e:
            error_msg = f"Ollama unavailable: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            error_msg = f"Server error: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

    def _proxy_lmstudio(self):
        """Proxy POST requests to LM Studio /v1/chat/completions."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)

            # Forward to LM Studio
            lmstudio_url = f'http://127.0.0.1:{LMSTUDIO_PORT}/v1/chat/completions'
            req = urllib.request.Request(lmstudio_url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Accept', 'application/json')

            with urllib.request.urlopen(req, timeout=300) as response:
                lmstudio_response = response.read()

            # Return LM Studio response with CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(lmstudio_response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(lmstudio_response)

        except urllib.error.URLError as e:
            error_msg = f"LM Studio unavailable: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            error_msg = f"Server error: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)


    def _proxy_dolphin(self):
        """Proxy POST requests to Dolphin Vision /analyze endpoint."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)

            dolphin_url = f'http://127.0.0.1:{DOLPHIN_PORT}/analyze'
            req = urllib.request.Request(dolphin_url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Accept', 'application/json')

            with urllib.request.urlopen(req, timeout=300) as response:
                dolphin_response = response.read()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(dolphin_response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(dolphin_response)

        except urllib.error.URLError as e:
            error_msg = f"Dolphin Vision unavailable (is port {DOLPHIN_PORT} running?): {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            error_msg = f"Server error: {str(e)}"
            response = json.dumps({'error': error_msg}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)


    def _proxy_gemini(self):
        """Proxy image analysis to Google Gemini API."""
        if not GOOGLE_API_KEY:
            response = json.dumps({'error': 'GOOGLE_API_KEY not configured in .env'}).encode()
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)
            data = json.loads(body)

            image_base64 = data.get('image_base64', '')
            prompt = data.get('prompt', '')
            mime_type = data.get('mime_type', 'image/jpeg')

            if not image_base64 or not prompt:
                self.send_error(400, "Missing image_base64 or prompt")
                return

            # Build Gemini REST API request
            gemini_url = (
                f'https://generativelanguage.googleapis.com/v1beta/models/'
                f'{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}'
            )
            gemini_body = json.dumps({
                'contents': [{
                    'parts': [
                        {'text': prompt},
                        {'inline_data': {'mime_type': mime_type, 'data': image_base64}}
                    ]
                }]
            }).encode()

            req = urllib.request.Request(gemini_url, data=gemini_body, method='POST')
            req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=60) as gemini_resp:
                gemini_data = json.loads(gemini_resp.read())

            # Extract text from response
            text = gemini_data['candidates'][0]['content']['parts'][0]['text']
            response = json.dumps({'response': text}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            try:
                error_json = json.loads(error_body)
                error_msg = error_json.get('error', {}).get('message', str(e))
            except Exception:
                error_msg = error_body[:200]
            response = json.dumps({'error': f'Gemini API error: {error_msg}'}).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except (KeyError, IndexError) as e:
            response = json.dumps({'error': f'Unexpected Gemini response format: {str(e)}'}).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            response = json.dumps({'error': f'Server error: {str(e)}'}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)


class ReuseTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """TCP server with SO_REUSEADDR and per-request threads.

    ThreadingMixIn is required so the 4 parallel Ollama requests from
    Promise.all are handled concurrently instead of serially — without it,
    requests 2-4 block behind request 1's full LLM inference time.
    """
    allow_reuse_address = True
    daemon_threads = True  # threads exit cleanly when server shuts down

    def server_bind(self):
        """Set SO_REUSEADDR on socket before binding."""
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


if __name__ == "__main__":
    # Verify dragonsight4.html exists
    if not HTML_FILE.exists():
        print(f"ERROR: {HTML_FILE} not found")
        exit(1)
    
    print(f"🐉 Dragonsight 4 HTTP Server")
    print(f"   Serving: {HTML_FILE}")
    print(f"   Ollama Proxy: /api/ollama/generate → localhost:{OLLAMA_PORT}")
    print(f"   LM Studio Proxy: /api/lmstudio/completions → localhost:{LMSTUDIO_PORT}")
    print(f"   Dolphin Proxy: /api/dolphin/analyze → localhost:{DOLPHIN_PORT}")
    print(f"   Gemini Proxy: /api/gemini/generate → Google API ({'✓ key loaded' if GOOGLE_API_KEY else '✗ no key'})")
    print(f"   Port: {PORT}")
    print(f"   Access: http://127.0.0.1:{PORT}")
    print(f"   LAN: http://192.168.7.226:{PORT}")
    print()
    
    # Start server
    with ReuseTCPServer(("", PORT), DragonsightHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Dragonsight 4 server stopped")
