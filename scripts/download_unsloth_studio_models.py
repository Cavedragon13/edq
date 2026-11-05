"""Pre-cache Unsloth Studio's helper GGUF (used for dataset-assist auto-captioning).

Calls the same precache_helper_gguf() the app runs on its own FastAPI startup
(studio/backend/utils/datasets/llm_assist.py) — no-op if already cached. This is
the only model Unsloth Studio downloads on its own; every training/inference
model is chosen and fetched by the user from inside the UI, so there is nothing
else for a static download script to pre-fetch.
"""
import sys
from pathlib import Path

backend_dir = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "studio" / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from utils.datasets.llm_assist import precache_helper_gguf  # noqa: E402

print(f"Pre-caching Unsloth Studio helper GGUF (backend: {backend_dir})...")
precache_helper_gguf()
print("Done.")
