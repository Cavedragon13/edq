#!/usr/bin/env python3
"""
GPU Monitor Server - Minimal floating GPU stats display
Serves the GPU monitor UI and provides real-time VRAM/utilization stats
Port: 8015
"""

import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import mimetypes

PORT = 8015
BASE_DIR = Path("/srv/containers/edq")
MEDIA_DIR = BASE_DIR / "media"


def get_gpu_stats():
    """Get GPU VRAM and utilization stats using nvidia-smi"""
    try:
        # Query NVIDIA GPU for memory and utilization
        cmd = [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return {"error": "nvidia-smi failed"}

        # Parse output: "used_mb, total_mb, utilization_percent"
        output = result.stdout.strip()
        parts = [x.strip() for x in output.split(',')]

        if len(parts) != 3:
            return {"error": "Unexpected nvidia-smi output"}

        vram_used_mb = int(parts[0])
        vram_total_mb = int(parts[1])
        gpu_util = int(parts[2])

        vram_percent = (vram_used_mb / vram_total_mb * 100) if vram_total_mb > 0 else 0

        return {
            "vram_used_mb": vram_used_mb,
            "vram_total_mb": vram_total_mb,
            "vram_percent": vram_percent,
            "gpu_utilization": gpu_util
        }

    except subprocess.TimeoutExpired:
        return {"error": "nvidia-smi timeout"}
    except Exception as e:
        return {"error": str(e)}


class GPUMonitorHandler(BaseHTTPRequestHandler):
    """HTTP request handler for GPU monitor"""

    def log_message(self, format, *args):
        """Suppress default logging (optional)"""
        pass

    def do_GET(self):
        """Handle GET requests"""

        # API endpoint for GPU stats
        if self.path == '/api/gpu-stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            stats = get_gpu_stats()
            self.wfile.write(json.dumps(stats).encode())
            return

        # Serve HTML file
        if self.path == '/' or self.path == '/index.html':
            file_path = MEDIA_DIR / "gpu_monitor.html"
        else:
            # Serve other static files from media directory
            file_path = MEDIA_DIR / self.path.lstrip('/')

        if file_path.exists() and file_path.is_file():
            self.send_response(200)

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type:
                self.send_header('Content-Type', mime_type)

            self.end_headers()

            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    """Start the GPU monitor server"""
    server = HTTPServer(('0.0.0.0', PORT), GPUMonitorHandler)
    server.timeout = 300

    print(f"🎮 GPU Monitor Server")
    print(f"=" * 50)
    print(f"✓ Server running on http://192.168.7.226:{PORT}")
    print(f"✓ Local access: http://localhost:{PORT}")
    print(f"✓ Press Ctrl+C to stop")
    print(f"=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
        server.shutdown()


if __name__ == "__main__":
    main()
