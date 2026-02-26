#!/usr/bin/env python3
"""
Dragonsong - Lyria RealTime Music Generation
FastAPI server with WebSocket proxy to Google's Lyria RealTime API.

Port: 8029
API: Google Lyria RealTime (models/lyria-realtime-exp, v1alpha)
Auth: GOOGLE_API_KEY from /srv/containers/edq/.env

WebSocket protocol (browser → server, JSON):
  {type: "prompts", prompts: [{text, weight}]}
  {type: "config", bpm, density, brightness, guidance, temperature,
                   scale, mode, mute_bass, mute_drums, only_bass_and_drums}
  {type: "play"}
  {type: "pause"}
  {type: "stop"}

WebSocket protocol (server → browser):
  Binary: raw Int16 PCM chunks (48kHz stereo)
  JSON:   {type: "status", state, message}
  JSON:   {type: "error", message}
  JSON:   {type: "filtered", prompt}  (when Google blocks a prompt)
"""

import asyncio
import json
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv('/srv/containers/edq/.env')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not found in /srv/containers/edq/.env")

from google import genai
from google.genai import types

client = genai.Client(
    api_key=GOOGLE_API_KEY,
    http_options={'api_version': 'v1alpha'}
)

app = FastAPI(title="Dragonsong")

MEDIA_DIR = Path("/srv/containers/edq/media")


@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "dragonsong.html")


def build_config(cfg: dict) -> types.LiveMusicGenerationConfig:
    """Build LiveMusicGenerationConfig from a dict, ignoring None values."""
    kwargs = {}

    for field in ("bpm", "temperature", "density", "brightness", "guidance", "top_k", "seed"):
        val = cfg.get(field)
        if val is not None:
            kwargs[field] = val

    for field in ("mute_bass", "mute_drums", "only_bass_and_drums"):
        val = cfg.get(field)
        if val is not None:
            kwargs[field] = bool(val)

    scale_str = cfg.get("scale")
    if scale_str and scale_str != "SCALE_UNSPECIFIED":
        try:
            kwargs["scale"] = types.Scale[scale_str]
        except KeyError:
            pass

    mode_str = cfg.get("mode")
    if mode_str and mode_str != "MUSIC_GENERATION_MODE_UNSPECIFIED":
        try:
            kwargs["music_generation_mode"] = types.MusicGenerationMode[mode_str]
        except KeyError:
            pass

    return types.LiveMusicGenerationConfig(**kwargs)


async def send_status(ws: WebSocket, state: str, message: str = ""):
    await ws.send_text(json.dumps({"type": "status", "state": state, "message": message}))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await send_status(websocket, "connecting", "Opening Lyria session...")

    # Default state
    current_prompts = [types.WeightedPrompt(text="ambient electronic music", weight=1.0)]
    current_config = types.LiveMusicGenerationConfig(bpm=100, temperature=1.0)
    is_playing = False

    try:
        async with client.aio.live.music.connect(model='models/lyria-realtime-exp') as session:
            await send_status(websocket, "connected", "Session open. Set a prompt and press Play.")

            # Set initial prompts & config
            await session.set_weighted_prompts(prompts=current_prompts)
            await session.set_music_generation_config(config=current_config)

            # Task: stream audio chunks → browser
            async def stream_audio():
                async for message in session.receive():
                    sc = getattr(message, 'server_content', None)
                    if sc is None:
                        continue
                    chunks = getattr(sc, 'audio_chunks', None)
                    if chunks:
                        await websocket.send_bytes(chunks[0].data)
                    # Report filtered prompts
                    filtered = getattr(sc, 'filtered_prompt', None)
                    if filtered:
                        await websocket.send_text(json.dumps({
                            "type": "filtered",
                            "prompt": str(filtered)
                        }))

            stream_task = asyncio.create_task(stream_audio())

            # Main loop: receive browser commands
            try:
                while True:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                    msg_type = msg.get("type")

                    if msg_type == "prompts":
                        prompts_data = msg.get("prompts", [])
                        if prompts_data:
                            current_prompts = [
                                types.WeightedPrompt(
                                    text=p["text"],
                                    weight=float(p.get("weight", 1.0))
                                )
                                for p in prompts_data if p.get("text", "").strip()
                            ]
                            await session.set_weighted_prompts(prompts=current_prompts)
                            await send_status(websocket, "updated", "Prompt updated.")

                    elif msg_type == "config":
                        current_config = build_config(msg)
                        await session.set_music_generation_config(config=current_config)
                        await send_status(websocket, "updated", "Config updated.")

                    elif msg_type == "play":
                        await session.play()
                        is_playing = True
                        await send_status(websocket, "playing")

                    elif msg_type == "pause":
                        await session.pause()
                        is_playing = False
                        await send_status(websocket, "paused")

                    elif msg_type == "stop":
                        await session.stop()
                        is_playing = False
                        await send_status(websocket, "stopped")

            except WebSocketDisconnect:
                pass
            finally:
                stream_task.cancel()
                try:
                    await stream_task
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass


if __name__ == "__main__":
    port = 8029
    print(f"🎵 Dragonsong starting on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
