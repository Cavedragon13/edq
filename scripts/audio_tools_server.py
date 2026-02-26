#!/usr/bin/env python3
"""
Audio Processing Suite - Native UI Server
Port: 8126 (dev) → 8026 (production after approval)

Three tools:
  1. Karaoke: vocal / instrumental separation
  2. Dereverb: remove room reverb from vocals
  3. ASR: speech-to-text with timestamps (EN / ZH / YUE)

API:
  GET  /                 → audio_tools.html
  GET  /audio/{filename} → serve saved audio files
  POST /api/karaoke      → file → {vocals, instrumental, status}
  POST /api/dereverb     → file → {dry, status}
  POST /api/transcribe   → file + language → {transcript}
"""

import sys
import os
import tempfile
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse

# SoulX-Singer imports
SOULX_PROJECT = "/srv/containers/edq/projects/SoulX-Singer"
if SOULX_PROJECT not in sys.path:
    sys.path.insert(0, SOULX_PROJECT)

PREPROCESS_BASE = "/srv/containers/edq/models/SoulX-Singer-Preprocess"
SEP_MODEL  = f"{PREPROCESS_BASE}/mel-band-roformer-karaoke/mel_band_roformer_karaoke_becruily.ckpt"
SEP_CONFIG = f"{PREPROCESS_BASE}/mel-band-roformer-karaoke/config_karaoke_becruily.yaml"
DER_MODEL  = f"{PREPROCESS_BASE}/dereverb_mel_band_roformer/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"
DER_CONFIG = f"{PREPROCESS_BASE}/dereverb_mel_band_roformer/dereverb_mel_band_roformer_anvuew.yaml"
ZH_MODEL   = f"{PREPROCESS_BASE}/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
EN_MODEL   = f"{PREPROCESS_BASE}/parakeet-tdt-0.6b-v2/parakeet-tdt-0.6b-v2.nemo"

OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/audio-tools"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_DIR = Path("/srv/containers/edq/media")

_separator   = None
_transcriber = None


def get_separator():
    global _separator
    if _separator is not None:
        return _separator, None
    try:
        from preprocess.tools import VocalSeparator
        print("Loading separation models…")
        _separator = VocalSeparator(
            sep_model_path=SEP_MODEL, sep_config_path=SEP_CONFIG,
            der_model_path=DER_MODEL, der_config_path=DER_CONFIG,
            device="cuda", verbose=True
        )
        return _separator, None
    except Exception as e:
        import traceback
        return None, f"{e}\n{traceback.format_exc()}"


def get_transcriber():
    global _transcriber
    if _transcriber is not None:
        return _transcriber, None
    try:
        from preprocess.tools import LyricTranscriber
        print("Loading ASR models…")
        _transcriber = LyricTranscriber(
            zh_model_path=ZH_MODEL, en_model_path=EN_MODEL,
            device="cuda", verbose=True
        )
        return _transcriber, None
    except Exception as e:
        import traceback
        return None, f"{e}\n{traceback.format_exc()}"


def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


app = FastAPI(title="Audio Processing Suite")


@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "audio_tools.html")


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serve saved audio files from OUTPUT_DIR only."""
    path = (OUTPUT_DIR / filename).resolve()
    if not str(path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(path))


async def save_upload(upload: UploadFile) -> str:
    """Save uploaded audio to a temp file, return path."""
    suffix = Path(upload.filename or "audio").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(await upload.read())
        return f.name


@app.post("/api/karaoke")
async def api_karaoke(file: UploadFile = File(...)):
    import soundfile as sf
    path = await save_upload(file)
    separator, err = get_separator()
    if err:
        return JSONResponse({"error": err}, status_code=500)
    try:
        result = separator.process(path)
        t = ts()
        vpath = OUTPUT_DIR / f"vocals_{t}.wav"
        ipath = OUTPUT_DIR / f"instrumental_{t}.wav"
        sf.write(str(vpath), result.vocals.T,         result.sample_rate)
        sf.write(str(ipath), result.accompaniment.T,  result.sample_rate)
        return JSONResponse({
            "vocals":        f"/audio/{vpath.name}",
            "instrumental":  f"/audio/{ipath.name}",
            "sample_rate":   result.sample_rate,
        })
    except Exception as e:
        import traceback
        return JSONResponse({"error": f"{e}\n{traceback.format_exc()}"}, status_code=500)
    finally:
        os.unlink(path)


@app.post("/api/dereverb")
async def api_dereverb(file: UploadFile = File(...)):
    import soundfile as sf
    path = await save_upload(file)
    separator, err = get_separator()
    if err:
        return JSONResponse({"error": err}, status_code=500)
    try:
        result = separator.process(path)
        t = ts()
        dpath = OUTPUT_DIR / f"dry_vocals_{t}.wav"
        sf.write(str(dpath), result.vocals_dereverbed.T, result.sample_rate)
        return JSONResponse({
            "dry":        f"/audio/{dpath.name}",
            "sample_rate": result.sample_rate,
        })
    except Exception as e:
        import traceback
        return JSONResponse({"error": f"{e}\n{traceback.format_exc()}"}, status_code=500)
    finally:
        os.unlink(path)


@app.post("/api/transcribe")
async def api_transcribe(
    file:     UploadFile = File(...),
    language: str        = Form("Mandarin (Chinese)"),
):
    import soundfile as sf
    path = await save_upload(file)
    transcriber, err = get_transcriber()
    if err:
        return JSONResponse({"error": err}, status_code=500)
    try:
        # Convert to 16kHz wav if needed
        if not path.endswith(".wav"):
            import librosa
            audio, sr = librosa.load(path, sr=16000, mono=True)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sf.write(tmp.name, audio, sr)
            os.unlink(path)
            path = tmp.name

        lang_map = {
            "Mandarin (Chinese)": "Mandarin",
            "Cantonese":          "Cantonese",
            "English":            "English",
        }
        lang = lang_map.get(language, "Mandarin")
        words, durs = transcriber.process(path, language=lang)

        # Build segments with timestamps
        segments = []
        current_time = 0.0
        current_words = []
        seg_start = 0.0
        for word, dur in zip(words, durs):
            if word == "<SP>":
                if current_words:
                    segments.append({
                        "start": round(seg_start, 2),
                        "end":   round(current_time + dur, 2),
                        "text":  " ".join(current_words),
                    })
                    current_words = []
                    seg_start = current_time + dur
            else:
                if not current_words:
                    seg_start = current_time
                current_words.append(word)
            current_time += dur
        if current_words:
            segments.append({
                "start": round(seg_start, 2),
                "end":   round(current_time, 2),
                "text":  " ".join(current_words),
            })

        return JSONResponse({"segments": segments, "language": language})
    except Exception as e:
        import traceback
        return JSONResponse({"error": f"{e}\n{traceback.format_exc()}"}, status_code=500)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    port = 8026
    print(f"🎵 Audio Processing Suite (native UI) → http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
