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

PORT = 8080
OLLAMA_PORT = 11434
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
        """Handle POST requests - proxy to Ollama or save metadata."""
        if self.path == '/api/ollama/generate':
            self._proxy_ollama()
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

            # Generate filename from original filename or timestamp
            original_name = data.get('original_filename', 'unknown')
            base_name = Path(original_name).stem
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


class ReuseTCPServer(socketserver.TCPServer):
    """TCP server with SO_REUSEADDR enabled."""
    allow_reuse_address = True
    
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
    print(f"   Ollama Proxy: http://127.0.0.1:{PORT}/api/ollama/generate")
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
