#!/usr/bin/env python3
"""
Mercury2 Diffusion Chat Server
Serves mercury2.html on port 8036
Proxies streaming/diffusing requests to Inception Labs API
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import os
from pathlib import Path

# Load .env for API keys
_env_path = Path("/srv/containers/edq/.env")
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

PORT = 8036
INCEPTION_API_KEY = os.getenv('MERCURY2_API_KEY', '')
INCEPTION_BASE_URL = 'https://api.inceptionlabs.ai/v1'
MERCURY_MODEL = 'mercury-2'
MEDIA_DIR = Path("/srv/containers/edq/media")
HTML_FILE = MEDIA_DIR / "mercury2.html"


class Mercury2Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ['/', '/mercury2.html', '/index.html']:
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
            if file_path.suffix == '.js':
                content_type = 'application/javascript'
            elif file_path.suffix == '.css':
                content_type = 'text/css'
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
        if self.path == '/api/chat':
            self._handle_chat()
        else:
            self.send_error(404, f"Path {self.path} not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _handle_chat(self):
        """Handle chat request - streams SSE for diffusing mode, JSON for normal."""
        if not INCEPTION_API_KEY:
            response = json.dumps({'error': 'MERCURY2_API_KEY not configured in .env'}).encode()
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

            messages = data.get('messages', [])
            diffusing = data.get('diffusing', True)
            max_tokens = data.get('max_tokens', 1024)
            temperature = data.get('temperature', 0.7)

            inception_payload = {
                'model': MERCURY_MODEL,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'stream': diffusing,
            }
            if diffusing:
                inception_payload['diffusing'] = True

            inception_body = json.dumps(inception_payload).encode()
            inception_url = f'{INCEPTION_BASE_URL}/chat/completions'
            req = urllib.request.Request(inception_url, data=inception_body, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {INCEPTION_API_KEY}')
            req.add_header('Accept', 'text/event-stream' if diffusing else 'application/json')

            with urllib.request.urlopen(req, timeout=120) as resp:
                if diffusing:
                    # Stream SSE back to browser
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('X-Accel-Buffering', 'no')
                    self.end_headers()

                    for raw_line in resp:
                        line = raw_line.decode('utf-8', errors='replace').rstrip('\n\r')
                        if not line:
                            self.wfile.write(b'\n')
                            self.wfile.flush()
                            continue
                        if line.startswith('data: '):
                            payload_str = line[6:]
                            if payload_str == '[DONE]':
                                self.wfile.write(b'data: [DONE]\n\n')
                                self.wfile.flush()
                                break
                            try:
                                chunk = json.loads(payload_str)
                                # Forward the chunk as-is — browser parses delta
                                self.wfile.write(f'data: {json.dumps(chunk)}\n\n'.encode())
                                self.wfile.flush()
                            except json.JSONDecodeError:
                                # Forward raw if we can't parse
                                self.wfile.write(f'{line}\n\n'.encode())
                                self.wfile.flush()
                else:
                    # Non-streaming: return full JSON
                    result = resp.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(result))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(result)

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            try:
                error_json = json.loads(error_body)
                error_msg = error_json.get('error', {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get('message', str(e))
            except Exception:
                error_msg = error_body[:300]
            response = json.dumps({'error': f'Inception API error ({e.code}): {error_msg}'}).encode()
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            try:
                response = json.dumps({'error': f'Server error: {str(e)}'}).encode()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', len(response))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(response)
            except Exception:
                pass


class ReuseTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


if __name__ == "__main__":
    if not HTML_FILE.exists():
        print(f"ERROR: {HTML_FILE} not found")
        exit(1)

    print(f"⚗️  Mercury2 Diffusion Chat Server")
    print(f"   Serving: {HTML_FILE}")
    print(f"   Model: {MERCURY_MODEL}")
    print(f"   API key: {'✓ loaded' if INCEPTION_API_KEY else '✗ MERCURY2_API_KEY not set'}")
    print(f"   Port: {PORT}")
    print(f"   Access: http://127.0.0.1:{PORT}")
    print(f"   LAN: http://192.168.7.226:{PORT}")
    print()

    with ReuseTCPServer(("", PORT), Mercury2Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Mercury2 server stopped")
