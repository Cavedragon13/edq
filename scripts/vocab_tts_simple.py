#!/usr/bin/env python3
"""
Simple TTS generator using requests to call Fish Speech Gradio API directly.
"""

import sys
import json
import requests
from pathlib import Path

# Config
FISH_SPEECH_URL = "http://127.0.0.1:8003"
OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")


def generate_tts(text: str, output_file: str):
    """Generate TTS using Fish Speech Gradio API."""

    print(f"🎤 Generating TTS...")
    print(f"Text: {text}")
    print(f"Output: {output_file}")

    try:
        # Gradio API endpoint structure: /api/predict
        api_url = f"{FISH_SPEECH_URL}/api/predict"

        # Payload structure for Gradio
        # This may need adjustment based on Fish Speech's specific interface
        payload = {
            "fn_index": 0,  # Usually the first function
            "data": [
                text,  # Input text
                "english",  # Speaker/voice
                1.0,  # Speed
                None,  # Reference audio (optional)
            ],
            "session_hash": "test123"
        }

        print(f"Calling API...")
        response = requests.post(api_url, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            print(f"API Response: {result}")

            # Extract audio file path from result
            if "data" in result and len(result["data"]) > 0:
                audio_data = result["data"][0]

                # If it's a dict with 'name' field (file path)
                if isinstance(audio_data, dict) and "name" in audio_data:
                    temp_file = audio_data["name"]
                    print(f"Audio generated at: {temp_file}")

                    # Download the file
                    file_url = f"{FISH_SPEECH_URL}/file={temp_file}"
                    audio_response = requests.get(file_url)

                    if audio_response.status_code == 200:
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        output_path = OUTPUT_DIR / output_file

                        with open(output_path, 'wb') as f:
                            f.write(audio_response.content)

                        print(f"✓ Audio saved to: {output_path}")
                        print(f"  Size: {len(audio_response.content) / 1024:.1f} KB")
                        return True
                    else:
                        print(f"❌ Failed to download audio: {audio_response.status_code}")
                        return False
                else:
                    print(f"❌ Unexpected result format: {audio_data}")
                    return False
            else:
                print(f"❌ No data in response: {result}")
                return False
        else:
            print(f"❌ API error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: vocab_tts_simple.py <text> <output_filename>")
        print("Example: vocab_tts_simple.py 'Hello world' output.mp3")
        sys.exit(1)

    text = sys.argv[1]
    output_file = sys.argv[2]

    success = generate_tts(text, output_file)
    sys.exit(0 if success else 1)
