#!/usr/bin/env python3
"""
The Movies (Working Title) — AI Film Studio Simulation
FastAPI server handling all Gemini API calls.

Port: 8035
APIs:
  Gemini text model resolved live                  — logline + scene breakdown
  Gemini image model resolved live                 — character portraits
  Veo 3.1 fast    (veo-3.1-fast-generate-preview) — scene video clips (4/6/8s; generate_audio is Vertex-only)
  Lyria 3         (models/lyria-realtime-exp)   — film score (via v1alpha)

Model naming note: gemini-2.5-flash has no -latest suffix; gemini-flash-latest is
the family-wide alias. Preview/experimental models use their full versioned IDs.

Auth: GOOGLE_API_KEY from /srv/containers/edq/.env
"""

import asyncio
import base64
import json
import os
import time
import uuid
import wave
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, '/srv/containers/edq')
from scripts import provider_models

load_dotenv('/srv/containers/edq/.env')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not found in /srv/containers/edq/.env")

from google import genai
from google.genai import types

# Standard client: Gemini text + Nano Banana 2 image + Veo 3.1 video (v1beta)
client = genai.Client(api_key=GOOGLE_API_KEY)

# Lyria client: Lyria RealTime requires v1alpha API
lyria_client = genai.Client(
    api_key=GOOGLE_API_KEY,
    http_options={'api_version': 'v1alpha'}
)

# ── Model resolution ─────────────────────────────────────────────────────────
# Text/image models are discovered live from the current Google key. Video/music
# models are still preview/specialized APIs, so the resolver exposes conservative
# fallback IDs until Google provides richer discovery metadata for them.
def google_model(task: str, modality: str | None = None) -> str:
    resolved = provider_models.resolve_model('google', task, modality=modality)
    if not resolved.get('model'):
        raise RuntimeError(f'No Google model available for {task}')
    return resolved['model']


def model_status():
    return provider_models.status_payload('The Movies', providers=['google'], default_provider='google')

PORT = 8035
MEDIA_DIR = Path("/srv/containers/edq/media")
OUTPUT_DIR = Path("/home/edq/ai_generated/the_movies")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="The Movies")
jobs: dict = {}


# ── Request / Response models ─────────────────────────────────────────────────

class ConceptRequest(BaseModel):
    title: str
    genre: str
    num_scenes: int

class PortraitRequest(BaseModel):
    role_type: str   # "lead" | "support" | "villain"
    tier: str        # "A" | "B" | "C"
    genre: str
    actor_name: str

class Scene(BaseModel):
    label: str
    description: str

class CastMember(BaseModel):
    role_type: str
    tier: str
    actor_name: str

class BudgetAllocation(BaseModel):
    cast: int       # 0–100
    sets: int
    music: int
    promotion: int

class ProduceRequest(BaseModel):
    title: str
    genre: str
    scenes: list[Scene]
    cast: list[CastMember]
    budget: BudgetAllocation
    modifier: str
    num_scenes: int


# ── Music prompt tables ───────────────────────────────────────────────────────

GENRE_MUSIC = {
    "Drama":        "emotional orchestral film score, strings and piano, dramatic tension",
    "Action":       "epic action film score, intense percussion, brass, driving rhythm",
    "Comedy":       "lighthearted playful film score, pizzicato strings, upbeat jazz",
    "Holiday":      "warm festive film score, orchestral, heartwarming and joyful",
    "Prestige":     "sophisticated prestige drama score, minimalist piano, contemplative",
    "Experimental": "avant-garde experimental film score, unconventional sounds, atmospheric",
}

MODIFIER_MOOD = {
    "Smooth Production":    "polished, professional, confident",
    "Inspired Chaos":       "dynamic, unpredictable, wildly creative",
    "Troubled Shoot":       "tense, uncertain, melancholic undertones",
    "Breakout Performance": "triumphant, soaring, emotionally powerful",
    "Weak Script":          "somewhat flat, searching, unresolved",
    "Audience Buzz":        "energetic, crowd-pleasing, exciting",
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    return FileResponse(MEDIA_DIR / "the_movies_game.html")


@app.get("/api/status")
async def api_status():
    return model_status()

def title_slug(title: str) -> str:
    """First two words of title, lowercased, joined with underscore."""
    words = title.strip().split()[:2]
    return '_'.join(w.lower() for w in words if w) or "film"

@app.get("/generated/{filepath:path}")
async def serve_generated(filepath: str):
    path = (OUTPUT_DIR / filepath).resolve()
    # Safety: must stay within OUTPUT_DIR
    if not str(path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(403, "Access denied")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)

@app.post("/api/concept")
async def generate_concept(req: ConceptRequest):
    scene_label_sets = {
        1: ["Setup"],
        2: ["Setup", "Resolution"],
        3: ["Setup", "Conflict", "Resolution"],
        4: ["Setup", "Rising Action", "Climax", "Resolution"],
        5: ["Setup", "Rising Action", "Conflict", "Climax", "Resolution"],
        6: ["Opening", "Setup", "Rising Action", "Conflict", "Climax", "Resolution"],
    }
    labels = scene_label_sets.get(req.num_scenes, ["Scene"] * req.num_scenes)

    prompt = f"""You are a Hollywood script doctor. Generate content for a {req.genre} short film titled "{req.title}".

Return ONLY valid JSON in this exact format, no markdown fences:
{{
  "logline": "A one to two sentence logline.",
  "scenes": [
    {{"label": "Setup", "description": "Visual scene description in 1-2 sentences. Describe what the camera sees, no character names. Under 40 words."}}
  ]
}}

Generate exactly {req.num_scenes} scene(s) with these labels in order: {labels}.
Each scene description should be vivid, visual, and suitable as a Veo video generation prompt.
Genre tone: {req.genre}."""

    response = client.models.generate_content(
        model=google_model('analysis'),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.9,
        )
    )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        raise HTTPException(500, f"Failed to parse Gemini response: {response.text[:200]}")


@app.post("/api/portrait")
async def generate_portrait(req: PortraitRequest):
    tier_desc = {
        "A": "glamorous, polished, A-list celebrity,",
        "B": "professional, competent actor,",
        "C": "quirky, unconventional independent actor,",
    }
    role_desc = {
        "lead":    "leading protagonist",
        "support": "supporting character",
        "villain": "compelling antagonist",
    }

    prompt = (
        f"Cinematic character portrait. {tier_desc.get(req.tier, '')} "
        f"{role_desc.get(req.role_type, 'actor')} for a {req.genre} film. "
        f"Professional headshot, dramatic studio lighting, film photography aesthetic, "
        f"high contrast, sharp focus. No text, no watermarks, photorealistic."
    )

    # gemini-3.1-flash-image-preview uses generateContent with IMAGE modality,
    # not the Imagen generate_images API.
    response = client.models.generate_content(
        model=google_model('image_generation'),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
    )

    candidates = response.candidates or []
    if not candidates or not candidates[0].content.parts:
        raise HTTPException(500, "No portrait generated")

    image_part = next(
        (p for p in candidates[0].content.parts if getattr(p, 'inline_data', None)),
        None
    )
    if not image_part:
        raise HTTPException(500, "No image part in portrait response")

    mime = image_part.inline_data.mime_type or "image/png"
    b64 = base64.b64encode(image_part.inline_data.data).decode()
    return {"portrait_data": f"data:{mime};base64,{b64}"}


@app.post("/api/produce")
async def produce_film(req: ProduceRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": req.num_scenes,
        "current_scene": 0,
        "clip_urls": [],
        "score_url": None,
        "error": None,
    }
    background_tasks.add_task(run_production, job_id, req)
    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


# ── Production pipeline ───────────────────────────────────────────────────────

async def generate_score(job_id: str, genre: str, modifier: str, film_duration: float, job_dir: Path):
    """Record Lyria RealTime audio for film_duration seconds, save as WAV."""
    try:
        base_prompt = GENRE_MUSIC.get(genre, "cinematic film score")
        mood = MODIFIER_MOOD.get(modifier, "balanced")
        full_prompt = f"{base_prompt}, {mood} mood, instrumental, no lyrics"

        audio_chunks: list[bytes] = []

        async def collect():
            async with lyria_client.aio.live.music.connect(model=google_model('music_generation', modality='audio')) as session:
                await session.set_weighted_prompts(
                    prompts=[types.WeightedPrompt(text=full_prompt, weight=1.0)]
                )
                await session.play()
                async for msg in session.receive():
                    sc = getattr(msg, 'server_content', None)
                    if sc and getattr(sc, 'audio_chunks', None):
                        for chunk in sc.audio_chunks:
                            audio_chunks.append(chunk.data)

        try:
            await asyncio.wait_for(collect(), timeout=film_duration + 10)
        except asyncio.TimeoutError:
            pass  # Expected — we collected enough

        if not audio_chunks:
            jobs[job_id]["score_url"] = None
            return

        score_path = job_dir / "score.wav"

        with wave.open(str(score_path), 'wb') as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)   # Int16
            wav_file.setframerate(48000)
            for chunk in audio_chunks:
                wav_file.writeframes(chunk)

        jobs[job_id]["score_url"] = f"/generated/{job_dir.name}/score.wav"

    except Exception as e:
        jobs[job_id]["score_url"] = None
        print(f"[score] Error: {e}")


GENRE_AUDIO = {
    "Drama":        "soft orchestral swell, ambient room tone, subtle emotional underscore",
    "Action":       "tires screeching, gunshots, rapid footsteps, debris crashing",
    "Comedy":       "light upbeat background music, laughter, playful sound effects",
    "Holiday":      "warm festive ambient music, gentle wind, fireplace crackling",
    "Prestige":     "quiet contemplative atmosphere, distant city hum, sparse piano notes",
    "Experimental": "unsettling ambient drone, distorted electronic sounds, eerie silence",
}

def sync_generate_clip(description: str, genre: str, scene_label: str, output_path: str):
    """Synchronous Veo clip generation (runs in thread executor).

    Veo 3.x generates audio automatically — include SFX, ambient, and dialogue
    cues directly in the prompt. No generate_audio parameter needed or supported.
    """
    audio_cue = GENRE_AUDIO.get(genre, "cinematic ambient sound design")
    prompt = (
        f"{genre} film, {scene_label} scene: {description} "
        f"Cinematic cinematography, film grain, professional lighting. "
        f"Audio: {audio_cue}."
    )

    operation = client.models.generate_videos(
        model=google_model('video_generation', modality='video'),
        prompt=prompt,
        config=types.GenerateVideosConfig(
            duration_seconds=8,
            aspect_ratio="16:9",
            number_of_videos=1,
        )
    )

    while not operation.done:
        time.sleep(10)
        operation = client.operations.get(operation)

    # SDK uses operation.result (not .response) per google-genai tests
    if not operation.result.generated_videos:
        raise ValueError("No video returned by Veo")

    video = operation.result.generated_videos[0].video
    if video.video_bytes:
        # Inline bytes path
        video.save(output_path)
    elif video.uri:
        # URI path — Gemini API file URIs require the API key to download
        import urllib.request
        sep = '&' if '?' in video.uri else '?'
        auth_uri = f"{video.uri}{sep}key={GOOGLE_API_KEY}"
        urllib.request.urlretrieve(auth_uri, output_path)
    else:
        raise ValueError("Veo returned video with neither bytes nor URI")


async def run_production(job_id: str, req: ProduceRequest):
    """Async production orchestrator: Lyria score + Veo clips in parallel."""
    try:
        jobs[job_id]["status"] = "starting"

        # Per-movie output directory: first_two_words_<job8>/
        slug = title_slug(req.title)
        job_dir = OUTPUT_DIR / f"{slug}_{job_id[:8]}"
        job_dir.mkdir(parents=True, exist_ok=True)

        film_duration = req.num_scenes * 8.0  # 8 sec per Veo clip

        # Start Lyria score recording concurrently with Veo generation.
        # Lyria records for film_duration seconds; Veo clips are generated in sequence.
        score_task = asyncio.create_task(
            generate_score(job_id, req.genre, req.modifier, film_duration, job_dir)
        )

        clip_urls: list = []
        loop = asyncio.get_running_loop()

        for i, scene in enumerate(req.scenes):
            jobs[job_id]["status"] = "filming"
            jobs[job_id]["current_scene"] = i + 1

            clip_path = str(job_dir / f"clip_{i}.mp4")

            try:
                await loop.run_in_executor(
                    None,
                    sync_generate_clip,
                    scene.description,
                    req.genre,
                    scene.label,
                    clip_path,
                )
                clip_urls.append(f"/generated/{job_dir.name}/clip_{i}.mp4")
            except Exception as e:
                print(f"[clip {i}] Error: {e}")
                clip_urls.append(None)

            jobs[job_id]["progress"] = i + 1

        jobs[job_id]["status"] = "recording_score"
        await score_task

        jobs[job_id]["clip_urls"] = clip_urls
        jobs[job_id]["status"] = "complete"

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        print(f"[production] Fatal error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🎬 The Movies starting on http://0.0.0.0:{PORT}")
    print(f"   Access: http://192.168.7.226:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
