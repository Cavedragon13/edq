#!/usr/bin/env python3
"""
DragonArt Studio - Local HTTP Server
Serves built React app on port 8015
Saves generated images/videos to ~/ai_generated/dragonart-studio/

Part of Dragonsuite - https://192.168.7.226:8100
"""

import http.server
import socketserver
import json
import base64
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote

PORT = 8015
DIST_DIR = Path("/srv/containers/edq/projects/dragonart-studio/dist")
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/dragonart-studio"))
SESSIONS_DIR = OUTPUT_DIR / "sessions"


class DragonArtHandler(http.server.BaseHTTPRequestHandler):
    """Serve static files and handle save requests."""

    # Increase timeout for large files
    timeout = 300

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_cors_headers(self):
        """Add CORS headers to response."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_GET(self):
        """Serve static files from dist/, or session ZIPs from sessions/"""
        # Parse path, remove query string
        path = urlparse(self.path).path

        # Serve saved session ZIPs
        if path.startswith('/sessions/'):
            filename = path[len('/sessions/'):]
            file_path = SESSIONS_DIR / filename
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, f"Session not found: {filename}")
                return
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Length', len(content))
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._send_error(500, f"Error reading session: {str(e)}")
            return

        if path == '/':
            path = '/index.html'

        file_path = DIST_DIR / path.lstrip('/')

        # SPA fallback: serve index.html for non-asset routes
        if not file_path.exists() and not path.startswith('/assets/'):
            file_path = DIST_DIR / 'index.html'

        if file_path.exists() and file_path.is_file():
            content_type = self._guess_type(file_path)
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', len(content))
                self.send_header('Cache-Control', 'no-cache')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._send_error(500, f"Error reading file: {str(e)}")
        else:
            self.send_error(404, f"File not found: {path}")

    def do_POST(self):
        """Handle API requests."""
        if self.path == '/api/save-image':
            self._save_image()
        elif self.path == '/api/save-video':
            self._save_video()
        elif self.path == '/api/save-session':
            self._save_session()
        else:
            self._send_error(404, f"Unknown endpoint: {self.path}")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _save_image(self):
        """Save base64 image to disk."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            image_base64 = data.get('image', '')
            session_name = data.get('sessionName', 'untitled')
            step = data.get('step', 0)
            edit_mode = data.get('editMode', '')

            if not image_base64:
                self._send_error(400, "No image data provided")
                return

            # Parse base64 data URL
            if ',' in image_base64:
                header, encoded = image_base64.split(',', 1)
                ext = 'png' if 'png' in header else 'jpg'
            else:
                encoded = image_base64
                ext = 'png'

            # Create output directory
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            # Generate filename: session_mode_step_timestamp.ext
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = "".join(c for c in session_name[:30] if c.isalnum() or c in ' -_').strip()
            safe_name = safe_name.replace(' ', '_') or 'untitled'
            safe_mode = "".join(c for c in edit_mode[:20] if c.isalnum() or c in '-_') or 'edit'

            filename = f"{safe_name}_{safe_mode}_step{step}_{timestamp}.{ext}"
            output_path = OUTPUT_DIR / filename

            # Decode and save
            image_bytes = base64.b64decode(encoded)
            with open(output_path, 'wb') as f:
                f.write(image_bytes)

            response = json.dumps({
                'success': True,
                'file': str(output_path),
                'filename': filename
            }).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response)

            print(f"   Saved: {filename}")

        except json.JSONDecodeError as e:
            self._send_error(400, f"Invalid JSON: {str(e)}")
        except base64.binascii.Error as e:
            self._send_error(400, f"Invalid base64 data: {str(e)}")
        except Exception as e:
            self._send_error(500, f"Save failed: {str(e)}")

    def _save_session(self):
        """Save session ZIP to disk and return server URL for reliable download."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "No data provided")
                return

            zip_bytes = self.rfile.read(content_length)

            session_name = unquote(self.headers.get('X-Session-Name', 'session'))
            SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = "".join(c for c in session_name[:40] if c.isalnum() or c in ' -_').strip()
            safe_name = safe_name.replace(' ', '_') or 'session'
            filename = f"{safe_name}_{timestamp}.zip"

            output_path = SESSIONS_DIR / filename
            with open(output_path, 'wb') as f:
                f.write(zip_bytes)

            size_mb = len(zip_bytes) / 1024 / 1024
            print(f"   Saved session: {filename} ({size_mb:.1f} MB)")

            response = json.dumps({'success': True, 'filename': filename}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            self._send_error(500, f"Save session failed: {str(e)}")

    def _save_video(self):
        """Save video to disk."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            video_base64 = data.get('video', '')
            session_name = data.get('sessionName', 'untitled')

            if not video_base64:
                self._send_error(400, "No video data provided")
                return

            # Parse base64 data URL
            if ',' in video_base64:
                header, encoded = video_base64.split(',', 1)
                ext = 'mp4'  # Veo returns mp4
            else:
                encoded = video_base64
                ext = 'mp4'

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = "".join(c for c in session_name[:30] if c.isalnum() or c in ' -_').strip()
            safe_name = safe_name.replace(' ', '_') or 'untitled'

            filename = f"{safe_name}_veo_{timestamp}.{ext}"
            output_path = OUTPUT_DIR / filename

            video_bytes = base64.b64decode(encoded)
            with open(output_path, 'wb') as f:
                f.write(video_bytes)

            response = json.dumps({
                'success': True,
                'file': str(output_path),
                'filename': filename
            }).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response)

            print(f"   Saved video: {filename}")

        except Exception as e:
            self._send_error(500, f"Save video failed: {str(e)}")

    def _send_error(self, code, message):
        """Send JSON error response with CORS headers."""
        response = json.dumps({'error': message}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(response)
        print(f"   Error {code}: {message}")

    def _guess_type(self, path):
        """Guess MIME type from file extension."""
        ext = path.suffix.lower()
        types = {
            '.html': 'text/html; charset=utf-8',
            '.js': 'application/javascript',
            '.mjs': 'application/javascript',
            '.css': 'text/css',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
        }
        return types.get(ext, 'application/octet-stream')


class ReuseTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """TCP server with address reuse and per-request threading."""
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET,
                               socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


def main():
    """Start the DragonArt Studio server."""
    if not DIST_DIR.exists():
        print(f"ERROR: Build directory not found: {DIST_DIR}")
        print("Run the build first:")
        print("  cd /srv/containers/edq/projects/dragonart-studio")
        print("  npm install && npm run build")
        exit(1)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("DragonArt Studio")
    print("================")
    print(f"   Serving:  {DIST_DIR}")
    print(f"   Port:     {PORT}")
    print(f"   Local:    http://localhost:{PORT}")
    print(f"   LAN:      http://192.168.7.226:{PORT}")
    print(f"   Output:   {OUTPUT_DIR}")
    print()
    print("Press Ctrl+C to stop")
    print()

    with ReuseTCPServer(("", PORT), DragonArtHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDragonArt Studio server stopped")


if __name__ == "__main__":
    main()
