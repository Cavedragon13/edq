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

# Load .env manually (dotenv not guaranteed to be installed in system Python)
_env_path = Path('/srv/containers/edq/.env')
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            if _k not in os.environ:
                os.environ[_k] = _v

GOOGLE_API_KEY = os.environ.get('STREET_VIEW_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')

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

        if path == '/api/config':
            self._send_config()
            return

        # Serve saved session ZIPs
        if path.startswith('/sessions/'):
            filename = path[len('/sessions/'):]
            file_path = SESSIONS_DIR / filename
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, f"Session not found: {filename}")
                return
            try:
                file_size = file_path.stat().st_size
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Length', file_size)
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self._send_cors_headers()
                self.end_headers()
                # Stream in 64KB chunks — avoids loading large ZIPs into RAM
                # and keeps the write calls short so the connection stays alive.
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
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
        elif self.path == '/api/sv_capture':
            self._sv_capture()
        elif self.path == '/api/gpt-image':
            self._gpt_image()
        elif self.path == '/api/gemini-image':
            self._gemini_image()
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

            # Also copy to Publish folder so the nightly cron job picks it up
            # for automatic deployment to seed13productions.com
            publish_dir = Path("/srv/containers/edq/Publish")
            try:
                publish_dir.mkdir(parents=True, exist_ok=True)
                publish_path = publish_dir / filename
                import shutil
                shutil.copy2(str(output_path), str(publish_path))
                print(f"   Copied to Publish queue: {publish_path}")
            except Exception as pub_e:
                print(f"   WARNING: Could not copy to Publish queue: {pub_e}")

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

    def _send_config(self):
        """Return server config including Maps API key."""
        result = {'mapsKey': GOOGLE_API_KEY}
        response = json.dumps(result).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(response)

    def _sv_capture(self):
        """Geocode an address and fetch a Street View Static image."""
        import requests as req_lib
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            address = data.get('address', '').strip()
            heading = data.get('heading', 0)
            pitch = data.get('pitch', 0)
            fov = max(10, min(120, int(data.get('fov', 90))))

            if not address:
                self._send_error(400, "Address required")
                return

            # Geocode address
            geo_resp = req_lib.get(
                'https://maps.googleapis.com/maps/api/geocode/json',
                params={'address': address, 'key': GOOGLE_API_KEY},
                timeout=10
            ).json()

            if geo_resp.get('status') != 'OK' or not geo_resp.get('results'):
                self._send_error(404, f"Could not geocode address: {address}")
                return

            loc = geo_resp['results'][0]['geometry']['location']
            lat, lng = loc['lat'], loc['lng']

            # Check Street View availability
            meta = req_lib.get(
                'https://maps.googleapis.com/maps/api/streetview/metadata',
                params={'location': f"{lat},{lng}", 'key': GOOGLE_API_KEY, 'source': 'outdoor'},
                timeout=10
            ).json()

            if meta.get('status') != 'OK':
                self._send_error(404, "No Street View imagery at this location")
                return

            sv_loc = meta['location']

            # Fetch Street View image
            sv_resp = req_lib.get(
                'https://maps.googleapis.com/maps/api/streetview',
                params={
                    'size': '640x640',
                    'location': f"{sv_loc['lat']},{sv_loc['lng']}",
                    'heading': heading,
                    'pitch': pitch,
                    'fov': fov,
                    'key': GOOGLE_API_KEY,
                    'source': 'outdoor',
                    'return_error_code': 'true',
                },
                timeout=15
            )

            if sv_resp.status_code != 200:
                self._send_error(sv_resp.status_code, "Street View API error")
                return

            img_b64 = base64.b64encode(sv_resp.content).decode()
            date_str = meta.get('date', '')
            pano_id = meta.get('pano_id', '')[:10]

            info = f"📍 {sv_loc['lat']:.5f}, {sv_loc['lng']:.5f} · heading {heading}° · fov {fov}°"
            if date_str:
                info += f" · {date_str}"
            if pano_id:
                info += f" · pano {pano_id}…"

            result = {
                'image_b64': img_b64,
                'info': info,
                'lat': sv_loc['lat'],
                'lng': sv_loc['lng'],
            }
            response = json.dumps(result).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            self._send_error(500, f"Street View capture failed: {str(e)}")

    def _gpt_image(self):
        """Proxy to OpenAI gpt-image-2. Keeps OPENAI_API_KEY server-side only."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 20 * 1024 * 1024:
                self._send_error(413, "Request body too large (max 20MB)")
                return
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            image_b64 = data.get('image', '')
            prompt = data.get('prompt', '')
            size = data.get('size', '1024x1024')
            quality = data.get('quality', 'auto')
            n = max(1, min(10, int(data.get('n', 1))))

            if not image_b64 or not prompt:
                self._send_error(400, "image and prompt are required")
                return

            # gpt-image-2 has minimum pixel budget (~1MP); enforce via size
            try:
                w, h = map(int, size.split('x'))
                if w * h < 1000000:  # ~1MP minimum
                    self._send_error(400, f"Image size too small. gpt-image-2 requires at least ~1MP (e.g., 1024x1024). Got {w}x{h}={w*h:,} pixels")
                    return
            except (ValueError, AttributeError):
                self._send_error(400, f"Invalid size format: {size}. Use WIDTHxHEIGHT (e.g., 1024x1024)")
                return

            try:
                from openai import OpenAI, BadRequestError
            except ImportError:
                self._send_error(503, "OpenAI SDK not installed. Run: pip install --user openai")
                return

            import io
            if ',' in image_b64:
                _, encoded = image_b64.split(',', 1)
            else:
                encoded = image_b64
            image_bytes = base64.b64decode(encoded)

            client = OpenAI(
                api_key=os.environ.get('OPENAI_API_KEY', ''),
                timeout=60.0,
            )

            fallback = False
            try:
                result = client.images.edit(
                    model='gpt-image-2',
                    image=('image.png', io.BytesIO(image_bytes), 'image/png'),
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=n,
                )
                images_b64 = [item.b64_json for item in result.data]
            except BadRequestError:
                if n > 1:
                    fallback = True
                    result = client.images.edit(
                        model='gpt-image-2',
                        image=('image.png', io.BytesIO(image_bytes), 'image/png'),
                        prompt=prompt,
                        size=size,
                        quality=quality,
                        n=1,
                    )
                    images_b64 = [result.data[0].b64_json]
                else:
                    raise
            # Ensure we got base64 data (gpt-image-2 returns b64_json, not url)
            if images_b64 and not images_b64[0]:
                raise ValueError("gpt-image-2 returned empty image data")

            response_data = json.dumps({'images': images_b64, 'fallback': fallback}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_data))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_data)
            print(f"   gpt-image-2: {len(images_b64)} image(s) generated")

        except Exception as e:
            self._send_error(500, f"gpt-image-2 failed: {str(e)}")

    def _gemini_image(self):
        """Proxy to Gemini image generation. Keeps GOOGLE_API_KEY server-side only."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 20 * 1024 * 1024:
                self._send_error(413, "Request body too large (max 20MB)")
                return
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            images_b64 = data.get('images', [])  # [mainImage, ...referenceImages]
            prompt = data.get('prompt', '')
            model = data.get('model', 'gemini-3-pro-image-preview')

            if not images_b64 or not prompt:
                self._send_error(400, "images and prompt are required")
                return

            try:
                from google import genai
                from google.genai import types as genai_types
            except ImportError:
                self._send_error(503, "google-genai SDK not installed. Run: pip install --user google-genai")
                return

            client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY', ''))

            # Build parts: images first, then text prompt
            parts = []
            for img_b64 in images_b64:
                if ',' in img_b64:
                    header, encoded = img_b64.split(',', 1)
                    mime = 'image/jpeg' if ('jpeg' in header or 'jpg' in header) else 'image/png'
                else:
                    encoded, mime = img_b64, 'image/png'
                img_bytes = base64.b64decode(encoded)
                parts.append(genai_types.Part.from_bytes(data=img_bytes, mime_type=mime))
            parts.append(genai_types.Part.from_text(text=prompt))

            safety = [
                genai_types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_ONLY_HIGH'),
                genai_types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_ONLY_HIGH'),
                genai_types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_ONLY_HIGH'),
                genai_types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_ONLY_HIGH'),
            ]

            response = client.models.generate_content(
                model=model,
                contents=parts,
                config=genai_types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    safety_settings=safety,
                ),
            )

            image_inline = None
            try:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_inline = part.inline_data
                        break
            except (IndexError, AttributeError):
                pass

            if not image_inline:
                try:
                    text_err = response.candidates[0].content.parts[0].text
                    self._send_error(422, text_err or 'Safety filter blocked image generation')
                except Exception:
                    self._send_error(422, 'Safety filter blocked image generation')
                return

            result_b64 = base64.b64encode(image_inline.data).decode()
            mime_out = image_inline.mime_type

            response_data = json.dumps({'image': f'data:{mime_out};base64,{result_b64}'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_data))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_data)
            print(f"   gemini-image: generated via {model}")

        except Exception as e:
            self._send_error(500, f"Gemini image failed: {str(e)}")

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
