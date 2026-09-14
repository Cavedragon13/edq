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
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

# Credentials are loaded only on the server.
from dotenv import load_dotenv
load_dotenv('/srv/containers/edq/.env')

GOOGLE_API_KEY = os.environ.get('STREET_VIEW_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')

PORT = int(os.getenv('DRAGONART_PORT', '8015'))
DIST_DIR = Path(os.getenv('DRAGONART_DIST_DIR', '/srv/containers/edq/projects/dragonart-studio/dist'))
OUTPUT_DIR = Path(os.getenv('DRAGONART_OUTPUT_DIR', '/home/edq/ai_generated/dragonart-studio'))
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

        if path in ('/api/config', '/api/status'):
            self._send_config()
            return

        # Serve saved session ZIPs
        if path.startswith('/sessions/'):
            filename = path[len('/sessions/'):]
            file_path = (SESSIONS_DIR / filename).resolve()
            if not file_path.is_relative_to(SESSIONS_DIR.resolve()):
                self.send_error(404)
                return
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

        file_path = (DIST_DIR / unquote(path).lstrip('/')).resolve()
        if not file_path.is_relative_to(DIST_DIR.resolve()):
            self.send_error(404)
            return

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
        elif self.path == '/api/canny-edge':
            self._canny_edge()
        elif self.path == '/api/gpt-image':
            self._gpt_image()
        elif self.path == '/api/gemini-helper':
            self._gemini_helper()
        elif self.path == '/api/gemini-video':
            self._gemini_video()
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
        result = provider_models.status_payload('DragonArt Studio', providers=['openai', 'google'], default_provider='openai')
        result['configured'] = {'google': bool(os.getenv('GOOGLE_API_KEY')), 'openai': bool(os.getenv('OPENAI_API_KEY'))}
        result['defaults']['image_model'] = provider_models.resolve_model('openai', 'image_edit', preferred='gpt-image-2.5-flare')['model']
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

    def _canny_edge(self):
        try:
            import io
            import cv2
            import numpy as np
            from PIL import Image
            data = self._read_provider_request()
            raw = base64.b64decode(data['image'].split(',', 1)[1])
            source = Image.open(io.BytesIO(raw)).convert('RGBA')
            # Composite alpha on white before filtering, preserving full dimensions.
            canvas = Image.new('RGBA', source.size, 'white')
            canvas.alpha_composite(source)
            gray = cv2.cvtColor(np.asarray(canvas.convert('RGB')), cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 1.0)
            edges = cv2.Canny(gray, 80, 160, L2gradient=True)
            buffer = io.BytesIO()
            Image.fromarray(edges).save(buffer, format='PNG')
            payload = json.dumps({'image': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(payload))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self._send_error(500, f'Canny filter failed: {e}')

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

            if size != 'auto':
                try:
                    w, h = map(int, size.split('x'))
                    valid = (w > 0 and h > 0 and w % 16 == 0 and h % 16 == 0
                             and max(w, h) <= 3840 and max(w, h) <= 3 * min(w, h)
                             and 655360 <= w * h <= 8294400)
                    if not valid:
                        raise ValueError('Unsupported image dimensions')
                except (ValueError, AttributeError):
                    self._send_error(400, 'Use auto or dimensions divisible by 16, up to 3840 per edge, 1:3–3:1, and 655360–8294400 pixels.')
                    return
            if quality not in {'auto', 'low', 'medium', 'high', 'xhigh', 'max'}:
                self._send_error(400, 'Unsupported image quality')
                return

            try:
                from openai import OpenAI, BadRequestError
            except ImportError:
                self._send_error(503, "OpenAI SDK not installed. Install openai in venv_dragonsuite")
                return

            import io
            if ',' in image_b64:
                _, encoded = image_b64.split(',', 1)
            else:
                encoded = image_b64
            image_bytes = base64.b64decode(encoded)

            background = data.get('background', 'auto')
            if background not in {'auto', 'opaque', 'transparent'}:
                self._send_error(400, 'Unsupported background mode')
                return
            client = OpenAI(
                api_key=os.environ.get('OPENAI_API_KEY', ''),
                timeout=300.0,
                max_retries=0,
            )

            image_model = data.get('model') if data.get('model') in provider_models.models_for('openai', 'image') else provider_models.resolve_model('openai', 'image_edit', preferred='gpt-image-2.5-flare').get('model')
            fallback = False
            try:
                result = client.images.edit(
                    model=image_model,
                    image=('image.png', io.BytesIO(image_bytes), 'image/png'),
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=n,
                    background=background,
                    output_format='png',
                )
                images_b64 = [item.b64_json for item in result.data]
            except BadRequestError:
                if n > 1:
                    fallback = True
                    result = client.images.edit(
                        model=image_model,
                        image=('image.png', io.BytesIO(image_bytes), 'image/png'),
                        prompt=prompt,
                        size=size,
                        quality=quality,
                        n=1,
                        background=background,
                        output_format='png',
                    )
                    images_b64 = [result.data[0].b64_json]
                else:
                    raise
            # Ensure we got base64 data (gpt-image-2 returns b64_json, not url)
            if images_b64 and not images_b64[0]:
                raise ValueError(f"{image_model} returned empty image data")

            if background == 'transparent':
                from PIL import Image
                for encoded_image in images_b64:
                    with Image.open(io.BytesIO(base64.b64decode(encoded_image))) as im:
                        if 'A' not in im.getbands() or im.getchannel('A').getextrema()[0] != 0:
                            raise ValueError('Provider did not return genuine PNG transparency; please retry the sheet')
            response_data = json.dumps({'images': images_b64, 'fallback': fallback, 'model': image_model}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_data))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_data)
            print(f"   {image_model}: {len(images_b64)} image(s) generated")

        except Exception as e:
            self._send_error(500, f"OpenAI image failed: {str(e)}")

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
            model = data.get('model') if data.get('model') in provider_models.models_for('google', 'image') else provider_models.resolve_model('google', 'image_generation', preferred='gemini-3.1-flash-image').get('model')

            if not images_b64 or not prompt:
                self._send_error(400, "images and prompt are required")
                return

            try:
                from google import genai
                from google.genai import types as genai_types
            except ImportError:
                self._send_error(503, "google-genai SDK not installed. Install google-genai in venv_dragonsuite")
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

            response_data = json.dumps({'image': f'data:{mime_out};base64,{result_b64}', 'model': model}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_data))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_data)
            print(f"   gemini-image: generated via {model}")

        except Exception as e:
            self._send_error(500, f"Gemini image failed: {str(e)}")

    def _read_provider_request(self):
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 20 * 1024 * 1024:
            raise ValueError('Request must be between 1 byte and 20MB')
        return json.loads(self.rfile.read(length))

    def _gemini_helper(self):
        from google import genai
        from google.genai import types
        try:
            data = self._read_provider_request()
            task = data.get('task')
            prompts = {
                'names': "Suggest 3 distinct creative art session titles, each 5 words or less. Return JSON with suggestions: an array of 3 strings.",
                'metadata': "Describe this image. Return JSON with string fields description (one sentence), altText (concise accessible description), seoKeywords (5-7 comma-separated keywords).",
            }
            if task not in prompts:
                self._send_error(400, 'Unknown helper task')
                return
            header, encoded = data['image'].split(',', 1)
            mime = header.split(':', 1)[1].split(';', 1)[0]
            with genai.Client(api_key=os.environ['GOOGLE_API_KEY']) as client:
                response = client.models.generate_content(
                    model=provider_models.resolve_model('google', 'analysis', preferred='gemini-3.1-flash-lite')['model'],
                    contents=[types.Part.from_bytes(data=base64.b64decode(encoded), mime_type=mime), prompts[task]],
                    config=types.GenerateContentConfig(response_mime_type='application/json'),
                )
            result = json.loads(response.text)
            if task == 'names':
                suggestions = result if isinstance(result, list) else result.get('suggestions') if isinstance(result, dict) else None
                if not isinstance(suggestions, list) or len(suggestions) != 3 or not all(isinstance(item, str) and item.strip() for item in suggestions):
                    raise ValueError('Expected three nonempty session names')
                result = {'suggestions': [item.strip() for item in suggestions]}
            elif not isinstance(result, dict) or not all(isinstance(result.get(field), str) and result[field].strip() for field in ('description', 'altText', 'seoKeywords')):
                raise ValueError('Expected image description, alt text and keywords')
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(payload))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self._send_error(500, f'Image helper failed: {e}')

    def _gemini_video(self):
        from google import genai
        from google.genai import types
        import time
        try:
            data = self._read_provider_request()
            model = data.get('model', 'veo-3.1-lite-generate-preview')
            if model not in {'veo-3.1-lite-generate-preview', 'veo-3.1-fast-generate-preview'}:
                self._send_error(400, 'Unsupported video model')
                return
            header, encoded = data['image'].split(',', 1)
            mime = header.split(':', 1)[1].split(';', 1)[0]
            with genai.Client(api_key=os.environ['GOOGLE_API_KEY']) as client:
                operation = client.models.generate_videos(
                    model=model, prompt=data['prompt'],
                    image=types.Image(image_bytes=base64.b64decode(encoded), mime_type=mime),
                    config=types.GenerateVideosConfig(number_of_videos=1, resolution='720p', aspect_ratio='16:9'),
                )
                deadline = time.monotonic() + 600
                while not operation.done:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Video is still rendering; please check the provider before retrying')
                    time.sleep(10)
                    operation = client.operations.get(operation)
                if operation.error:
                    raise RuntimeError(operation.error)
                video = operation.response.generated_videos[0].video
                content = client.files.download(file=video)
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(500, f'Video generation failed: {e}')

    def _send_error(self, code, message):
        """Send JSON error response with CORS headers."""
        if 'prepayment credits are depleted' in str(message):
            message = 'Google prepaid credits are depleted. Add credits in the API key project at AI Studio, then retry. You can still use OpenAI and enter a session name manually.'
        payload = provider_models.error_payload(message) if 'provider_models' in globals() else {'error': message}
        if str(message).startswith("Google prepaid credits are depleted"):
            code = 402
            payload["error_category"] = "quota_or_billing"
        response = json.dumps(payload).encode('utf-8')
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
