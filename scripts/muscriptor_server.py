"""MuScriptor server wrapper — Dragonsuite launch entry (port 8040).

Runs the same FastAPI app as `muscriptor serve`, plus the Dragonsuite runtime
conventions the stock CLI can't provide:
  - gpu_runtime imported before torch (CUDA allocator config + shared OOM guard)
  - transcription wrapped in oom_guard so a mid-run OOM frees VRAM cleanly
  - every finished MIDI also saved to ~/ai_generated/muscriptor/ with a timestamp
"""
import sys

sys.path.insert(0, "/srv/containers/edq/scripts")
import gpu_runtime  # noqa: E402 — must precede torch imports (CUDA allocator config)

import argparse
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path.home() / "ai_generated" / "muscriptor"


def main():
    parser = argparse.ArgumentParser(description="MuScriptor Dragonsuite server")
    parser.add_argument("--model", default="large",
                        help="'small'/'medium'/'large', local path, or hf:// URL")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8040)
    parser.add_argument("--device", default=None,
                        help="None = auto; or 'cpu', 'cuda', 'cuda:0', …")
    args = parser.parse_args()

    import uvicorn
    import muscriptor
    from muscriptor.server import create_app
    from muscriptor.transcription_model import TranscriptionModel

    _orig_transcribe = TranscriptionModel.transcribe
    _orig_to_midi = TranscriptionModel.events_to_midi_bytes

    def transcribe_guarded(self, *a, **kw):
        with gpu_runtime.oom_guard("music transcription"):
            yield from _orig_transcribe(self, *a, **kw)

    def to_midi_saving(self, *a, **kw):
        midi_bytes = _orig_to_midi(self, *a, **kw)
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            (OUTPUT_DIR / f"transcription_{stamp}.mid").write_bytes(midi_bytes)
            (OUTPUT_DIR / "latest.mid").write_bytes(midi_bytes)
        except OSError as e:
            print(f"[muscriptor] could not save MIDI copy: {e}", file=sys.stderr)
        return midi_bytes

    TranscriptionModel.transcribe = transcribe_guarded
    TranscriptionModel.events_to_midi_bytes = to_midi_saving

    print(f"Loading model ({args.model})…", flush=True)
    model = TranscriptionModel.load_model(weights_path=args.model, device=args.device)
    web_dir = Path(muscriptor.__file__).resolve().parent / "web_dist"
    app = create_app(model, web_dir=web_dir if web_dir.is_dir() else None)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
