#!/usr/bin/env python3
"""
Vocab TTS Generator - Qwen3-TTS Edition
========================================

Generates English voiceover for vocab words using Qwen3-TTS.
Uses local Qwen3-TTS service on port 8009.

Usage:
    vocab_tts_qwen3.py --word reluctant --spelling "R-E-L-U-C-T-A-N-T"
    vocab_tts_qwen3.py --test  # Quick test with sample text
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Paths
AUDIO_OUTPUT_DIR = Path("/srv/containers/edq/projects/remotion-vocab/public/audio")
QWEN_TTS_URL = "http://127.0.0.1:8009"

# TTS Settings
DEFAULT_SPEAKER = "Aiden"  # Neutral adult male voice
DEFAULT_LANGUAGE = "English"
SAMPLE_RATE = 24000  # Qwen3-TTS default


def generate_script(word: str, spelling: str) -> str:
    """Generate the TTS script for a word.

    Args:
        word: The vocabulary word (e.g., "reluctant")
        spelling: Hyphenated spelling (e.g., "R-E-L-U-C-T-A-N-T")

    Returns:
        Script text for TTS
    """
    # Convert hyphenated spelling to comma-separated for speech
    # R-E-L-U-C-T-A-N-T → R, E, L, U, C, T, A, N, T
    spelling_spoken = spelling.replace("-", ", ")

    script = f"""Detention vocabulary time.
Today's word is {word}.
That's {word}, spelled {spelling_spoken}.
Detention continues."""

    return script


def generate_tts_gradio(text: str, output_file: Path, speaker: str = DEFAULT_SPEAKER) -> bool:
    """
    Generate TTS using Gradio API via HTTP requests.

    This is the primary method - it calls the running Qwen3-TTS Gradio service.

    Args:
        text: Text to convert to speech
        output_file: Path to save MP3/WAV file
        speaker: Speaker name (Aiden, Dylan, Eric, Ryan, Serena, etc.)

    Returns:
        True if successful, False otherwise
    """
    try:
        import requests
        import time

        print(f"  🔗 Connecting to Qwen3-TTS at {QWEN_TTS_URL}")
        print(f"  🎤 Speaker: {speaker}")
        print(f"  📝 Text length: {len(text)} characters")
        print(f"  ⏳ Generating audio...")

        # Step 1: Start the generation (Gradio v4+ API)
        call_url = f"{QWEN_TTS_URL}/gradio_api/call/generate_tts"

        # Payload matches the function signature: [text, language, speaker, instruct]
        payload = {
            "data": [
                text,                # Text to synthesize
                DEFAULT_LANGUAGE,    # Language ("English", "Auto", etc.)
                speaker,             # Speaker name
                ""                   # Style instruction (empty for neutral)
            ]
        }

        # Initiate the call
        init_response = requests.post(call_url, json=payload, timeout=30)

        if init_response.status_code != 200:
            print(f"  ❌ Failed to initiate generation: {init_response.status_code}")
            print(f"  Response: {init_response.text[:200]}")
            return False

        init_result = init_response.json()

        # Get event_id for polling
        if "event_id" not in init_result:
            print(f"  ❌ No event_id in response: {init_result}")
            return False

        event_id = init_result["event_id"]
        print(f"  📡 Generation started (event_id: {event_id})")

        # Step 2: Poll for results
        status_url = f"{QWEN_TTS_URL}/gradio_api/call/generate_tts/{event_id}"

        max_wait = 120  # 2 minutes max
        poll_interval = 2  # seconds
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_response = requests.get(status_url, timeout=10)

            if status_response.status_code != 200:
                continue

            # Gradio returns Server-Sent Events (SSE)
            # Parse line by line
            for line in status_response.text.strip().split('\n'):
                if not line.startswith('data: '):
                    continue

                data_json = line[6:]  # Remove "data: " prefix

                if not data_json.strip():
                    continue

                try:
                    event_data = json.loads(data_json)
                    if not event_data or not isinstance(event_data, dict):
                        continue
                except (json.JSONDecodeError, ValueError):
                    continue

                # Check if generation is complete
                if event_data.get('msg') == 'process_completed':
                    # Extract output data
                    output = event_data.get('output', {})
                    if 'data' not in output or len(output['data']) < 2:
                        print(f"  ❌ Unexpected output format: {output}")
                        return False

                    # Output format: [audio_array, file_path]
                    # We want the file_path (second element)
                    file_info = output['data'][1]

                    # File info is typically a dict or string
                    if isinstance(file_info, str):
                        audio_file_path = file_info
                    elif isinstance(file_info, dict) and 'name' in file_info:
                        audio_file_path = file_info['name']
                    else:
                        print(f"  ❌ Could not extract file path from: {file_info}")
                        return False

                    # Step 3: Download the generated file
                    file_url = f"{QWEN_TTS_URL}/file={audio_file_path}"
                    print(f"  📥 Downloading: {Path(audio_file_path).name}")

                    audio_response = requests.get(file_url, timeout=30)

                    if audio_response.status_code != 200:
                        print(f"  ❌ Failed to download: {audio_response.status_code}")
                        return False

                    # Save the file
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    # Save as WAV (Remotion supports it)
                    if output_file.suffix.lower() == '.mp3':
                        output_file = output_file.with_suffix('.wav')
                        print(f"  ℹ️ Saving as WAV (Remotion supports WAV)")

                    with open(output_file, 'wb') as f:
                        f.write(audio_response.content)

                    size_kb = output_file.stat().st_size / 1024
                    print(f"  ✓ Audio generated: {output_file.name}")
                    print(f"  📦 File size: {size_kb:.1f} KB")

                    return True

        print(f"  ❌ Timeout waiting for generation (>{max_wait}s)")
        return False

    except requests.exceptions.RequestException as e:
        print(f"  ❌ HTTP request error: {e}")
        print(f"  🔄 Trying direct Python API...")
        return generate_tts_direct(text, output_file, speaker)

    except Exception as e:
        print(f"  ❌ Gradio API error: {e}")
        import traceback
        traceback.print_exc()
        print(f"  🔄 Trying direct Python API...")
        return generate_tts_direct(text, output_file, speaker)


def generate_tts_venv_helper(text: str, output_file: Path, speaker: str = DEFAULT_SPEAKER) -> bool:
    """
    Generate TTS using direct Python API.

    Fallback method that directly imports and uses the Qwen3-TTS model.
    Requires the venv_qwen3_tts environment to be accessible.

    Args:
        text: Text to convert to speech
        output_file: Path to save audio file
        speaker: Speaker name

    Returns:
        True if successful, False otherwise
    """
    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel

        print(f"  🔧 Loading Qwen3-TTS model directly...")

        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32

        print(f"  🎮 Device: {device}, dtype: {dtype}")

        # Load model
        model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=dtype,
        )

        print(f"  🎤 Speaker: {speaker}")
        print(f"  ⏳ Generating audio...")

        # Generate audio
        with torch.no_grad():
            wavs, sr = model.generate_custom_voice(
                text=text.strip(),
                language="English",
                speaker=speaker.lower().replace(" ", "_"),
                instruct=None,  # No style instructions
                non_streaming_mode=True,
                max_new_tokens=4096,
            )

        # Save audio
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to appropriate format
        if output_file.suffix.lower() == '.mp3':
            # Save as WAV first, then convert
            temp_wav = output_file.with_suffix('.wav')
            sf.write(temp_wav, wavs, sr)

            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_wav(str(temp_wav))
                audio.export(str(output_file), format="mp3", bitrate="192k")
                temp_wav.unlink()  # Remove temp WAV
                print(f"  ✓ Converted to MP3")
            except ImportError:
                # Just use WAV
                output_file = temp_wav
                print(f"  ⚠️ pydub not installed, saved as WAV")
        else:
            # Save as WAV
            sf.write(str(output_file), wavs, sr)

        size_kb = output_file.stat().st_size / 1024
        print(f"  ✓ Audio generated: {output_file.name}")
        print(f"  📦 File size: {size_kb:.1f} KB")

        # Clean up
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return True

    except ImportError as e:
        print(f"  ❌ Missing dependencies: {e}")
        print(f"  💡 Make sure Qwen3-TTS is installed in venv_qwen3_tts")
        return False

    except Exception as e:
        print(f"  ❌ Direct API error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_qwen3_tts() -> bool:
    """Check if Qwen3-TTS service is running."""
    try:
        import requests
        response = requests.get(QWEN_TTS_URL, timeout=5)
        if response.status_code == 200:
            print(f"✓ Qwen3-TTS is running at {QWEN_TTS_URL}")
            return True
        else:
            print(f"⚠️ Qwen3-TTS returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Qwen3-TTS not reachable: {e}")
        print(f"\n💡 Start it with:")
        print(f"   bash /srv/containers/edq/scripts/start_qwen3_tts.sh")
        print(f"\n   Or use --direct to bypass Gradio API")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Vocab TTS Generator (Qwen3-TTS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate TTS for a vocab word
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T"

  # Use a different speaker
  %(prog)s --word reluctant --spelling "R-E-L-U-C-T-A-N-T" --speaker Ryan

  # Quick test with sample text
  %(prog)s --test

  # Check service status
  %(prog)s --check

Available Speakers:
  Aiden (default), Dylan, Eric, Ryan, Serena, Sohee, Uncle_fu, Vivian, Ono_anna
        """
    )

    parser.add_argument("--word", help="Vocabulary word to generate TTS for")
    parser.add_argument("--spelling", help="Hyphenated spelling (e.g., 'R-E-L-U-C-T-A-N-T')")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER,
                       help=f"Speaker voice (default: {DEFAULT_SPEAKER})")
    parser.add_argument("--output", help="Custom output filename (optional)")
    parser.add_argument("--test", action="store_true", help="Run quick test with sample text")
    parser.add_argument("--check", action="store_true", help="Check Qwen3-TTS service status")
    parser.add_argument("--direct", action="store_true",
                       help="Use direct Python API (bypass Gradio, slower)")

    args = parser.parse_args()

    # Check service status
    if args.check:
        check_qwen3_tts()
        return

    # Quick test
    if args.test:
        print("🧪 Running quick test...\n")
        test_text = "Detention vocabulary time. Today's word is test. That's test, spelled T, E, S, T. Detention continues."
        output_file = AUDIO_OUTPUT_DIR / "test_output.wav"

        if args.direct:
            success = generate_tts_direct(test_text, output_file, args.speaker)
        else:
            success = generate_tts_gradio(test_text, output_file, args.speaker)

        if success:
            print(f"\n✓ Test successful!")
            print(f"  Listen to: {output_file}")
        else:
            print(f"\n❌ Test failed")
            sys.exit(1)
        return

    # Validate required args
    if not args.word or not args.spelling:
        parser.print_help()
        print("\n❌ Error: --word and --spelling are required")
        sys.exit(1)

    # Check service (only if not using direct API)
    if not args.direct and not check_qwen3_tts():
        print("\n⚠️ Qwen3-TTS service not running. Use --direct flag to bypass.")
        sys.exit(1)

    # Generate script
    word = args.word.lower()
    script = generate_script(args.word, args.spelling)

    print(f"\n🎤 Generating TTS for: {args.word}")
    print(f"\n--- Script ---")
    print(script)
    print(f"--- End Script ---\n")

    # Determine output path
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = AUDIO_OUTPUT_DIR / f"{word}.mp3"

    # Generate TTS
    if args.direct:
        success = generate_tts_direct(script, output_file, args.speaker)
    else:
        success = generate_tts_gradio(script, output_file, args.speaker)

    if success:
        print(f"\n✓ TTS generation complete!")
        print(f"  Output: {output_file}")
        print(f"  Ready for Remotion rendering")
    else:
        print(f"\n❌ TTS generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
