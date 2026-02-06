#!/usr/bin/env python3
"""
Qwen3-Audiobook-Converter - Document to Audiobook
Gradio Interface for Dragonsuite

Converts PDF, EPUB, DOCX, DOC, TXT files to audiobooks using Qwen3-TTS.
Requires Qwen3-TTS service running on port 8009.
"""

import gc
import io
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import gradio as gr

# Configuration
OUTPUT_DIR = Path(os.path.expanduser("~/ai_generated/qwen3-audiobook"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TTS_PORT = 8009
TTS_URL = f"http://localhost:{TTS_PORT}"

# Available speakers (must match Qwen3-TTS)
SPEAKERS = [
    "Aiden", "Dylan", "Eric", "Ono_anna", "Ryan",
    "Serena", "Sohee", "Uncle_fu", "Vivian"
]

LANGUAGES = [
    "Auto", "Chinese", "English", "Japanese", "Korean",
    "French", "German", "Spanish", "Portuguese", "Russian"
]

# Dragon favicon as base64 SVG
DRAGON_FAVICON = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="dragonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#F59E0B"/>
      <stop offset="100%" style="stop-color:#EF4444"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30" fill="url(#dragonGrad)"/>
  <path d="M20 42 Q25 35 32 38 Q39 35 44 42 L42 38 Q38 32 32 35 Q26 32 22 38 Z" fill="#fff" opacity="0.9"/>
  <circle cx="24" cy="28" r="4" fill="#fff"/>
  <circle cx="40" cy="28" r="4" fill="#fff"/>
  <circle cx="25" cy="28" r="2" fill="#1a1a2e"/>
  <circle cx="41" cy="28" r="2" fill="#1a1a2e"/>
  <path d="M15 18 Q20 12 25 16" stroke="#fff" stroke-width="2" fill="none"/>
  <path d="M49 18 Q44 12 39 16" stroke="#fff" stroke-width="2" fill="none"/>
  <text x="32" y="52" text-anchor="middle" fill="#fff" font-size="7" font-weight="bold">BOOK</text>
</svg>
"""


def check_tts_service():
    """Check if Qwen3-TTS service is running."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(TTS_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError):
        return False


def extract_text_from_file(file_path: str) -> str:
    """Extract text from various document formats."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    text = ""

    if suffix == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    elif suffix == ".pdf":
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
        except ImportError:
            raise gr.Error("PyPDF2 not installed. Run: pip install PyPDF2")

    elif suffix == ".epub":
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup

            book = epub.read_epub(str(file_path))
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    text += soup.get_text() + "\n\n"
        except ImportError:
            raise gr.Error("ebooklib/beautifulsoup4 not installed. Run: pip install ebooklib beautifulsoup4")

    elif suffix in [".docx", ".doc"]:
        try:
            from docx import Document
            doc = Document(str(file_path))
            for para in doc.paragraphs:
                text += para.text + "\n"
        except ImportError:
            raise gr.Error("python-docx not installed. Run: pip install python-docx")

    else:
        raise gr.Error(f"Unsupported file format: {suffix}")

    return text.strip()


def clean_text(text: str) -> str:
    """Clean and normalize text for TTS."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove special characters that don't work well with TTS
    text = re.sub(r"[^\w\s.,!?;:'\"-]", " ", text)

    # Fix spacing around punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])\s*", r"\1 ", text)

    # Remove multiple spaces
    text = re.sub(r" +", " ", text)

    return text.strip()


def chunk_text(text: str, max_words: int = 1200) -> list[str]:
    """Split text into chunks for TTS processing."""
    # Split by sentences first
    sentence_endings = r"(?<=[.!?])\s+"
    sentences = re.split(sentence_endings, text)

    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)

        if current_word_count + word_count > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def generate_audio_chunk(text: str, speaker: str, language: str, instruct: str = None):
    """Generate audio for a single chunk using Qwen3-TTS API."""
    try:
        from gradio_client import Client

        client = Client(TTS_URL)

        # Call the TTS endpoint
        result = client.predict(
            text=text,
            language=language if language != "Auto" else "Auto",
            speaker=speaker,
            instruct=instruct or "",
            api_name="/generate_tts",
        )

        # Result should be (audio_tuple, file_path)
        if isinstance(result, tuple) and len(result) >= 1:
            audio_data = result[0]
            return audio_data
        return result

    except Exception as e:
        raise gr.Error(f"TTS generation failed: {e}")


def convert_to_audiobook(
    file,
    speaker: str,
    language: str,
    style_instruct: str,
    words_per_chunk: int,
    progress=gr.Progress(track_tqdm=True),
):
    """Convert document to audiobook."""
    if file is None:
        return None, None, "Please upload a document"

    # Check TTS service
    if not check_tts_service():
        return None, None, f"Qwen3-TTS service not running on port {TTS_PORT}.\nStart it first: bash scripts/start_qwen3_tts.sh"

    try:
        # Extract text
        progress(0, desc="Extracting text...")
        text = extract_text_from_file(file.name)

        if not text:
            return None, None, "No text extracted from document"

        # Clean text
        text = clean_text(text)
        total_words = len(text.split())

        # Chunk text
        progress(0.1, desc="Chunking text...")
        chunks = chunk_text(text, max_words=words_per_chunk)

        status = f"Extracted {total_words} words in {len(chunks)} chunks\n"
        status += f"Speaker: {speaker}, Language: {language}\n\n"

        # Generate audio for each chunk
        audio_segments = []
        for i, chunk in enumerate(chunks):
            progress((0.1 + 0.8 * (i / len(chunks))), desc=f"Generating chunk {i+1}/{len(chunks)}...")
            print(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk.split())} words)")

            try:
                audio_result = generate_audio_chunk(chunk, speaker, language, style_instruct)
                if audio_result:
                    audio_segments.append(audio_result)
            except Exception as e:
                print(f"Chunk {i+1} failed: {e}")
                status += f"Warning: Chunk {i+1} failed: {e}\n"

        if not audio_segments:
            return None, None, status + "No audio generated. Check TTS service."

        # Combine audio segments
        progress(0.9, desc="Combining audio...")

        try:
            from pydub import AudioSegment
            import numpy as np

            combined = None
            sample_rate = 24000  # Default Qwen3-TTS sample rate

            for seg in audio_segments:
                if isinstance(seg, tuple) and len(seg) == 2:
                    sr, wav = seg
                    sample_rate = sr
                    # Convert numpy to AudioSegment
                    if isinstance(wav, np.ndarray):
                        # Normalize to int16
                        wav_int16 = (wav * 32767).astype(np.int16)
                        audio_seg = AudioSegment(
                            wav_int16.tobytes(),
                            frame_rate=sr,
                            sample_width=2,
                            channels=1,
                        )
                        if combined is None:
                            combined = audio_seg
                        else:
                            combined += audio_seg

            if combined is None:
                return None, None, status + "Failed to combine audio segments"

            # Save as MP3
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"audiobook_{timestamp}.mp3"
            combined.export(str(output_path), format="mp3", bitrate="192k")

            # Also create WAV for Gradio player
            wav_path = OUTPUT_DIR / f"audiobook_{timestamp}.wav"
            combined.export(str(wav_path), format="wav")

            status += f"\nAudiobook saved to: {output_path}"
            duration = len(combined) / 1000  # ms to seconds
            status += f"\nDuration: {int(duration // 60)}:{int(duration % 60):02d}"

            progress(1.0, desc="Complete!")

            return str(wav_path), str(output_path), status

        except ImportError:
            # Fallback: return first segment only
            status += "\npydub not installed - returning first segment only"
            if audio_segments and isinstance(audio_segments[0], tuple):
                return audio_segments[0], None, status
            return None, None, status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, f"Error: {str(e)}"


def preview_document(file):
    """Preview extracted text from document."""
    if file is None:
        return "No file uploaded", 0

    try:
        text = extract_text_from_file(file.name)
        text = clean_text(text)
        words = len(text.split())

        # Show first 2000 characters
        preview = text[:2000]
        if len(text) > 2000:
            preview += "\n\n... [truncated] ..."

        return preview, words
    except Exception as e:
        return f"Error: {str(e)}", 0


def create_interface():
    """Create the Gradio interface."""

    with gr.Blocks(title="Qwen3 Audiobook Converter") as demo:
        gr.HTML(f"""
        <div style="text-align: center; margin-bottom: 1rem;">
            <div style="display: inline-block; width: 48px; height: 48px; margin-bottom: 0.5rem;">
                {DRAGON_FAVICON}
            </div>
            <h1 style="margin: 0;">Qwen3 Audiobook Converter</h1>
            <p style="color: #666; margin: 0.5rem 0;">Convert Documents to Audiobooks with AI Voice</p>
        </div>
        """)

        # Service status check
        service_running = check_tts_service()
        status_color = "#10B981" if service_running else "#EF4444"
        status_text = "Running" if service_running else "Not Running"

        gr.HTML(f"""
        <div style="text-align: center; padding: 0.5rem; background: {'#ECFDF5' if service_running else '#FEF2F2'}; border-radius: 8px; margin-bottom: 1rem;">
            <p style="margin: 0; color: {status_color};">
                <strong>Qwen3-TTS Service:</strong> {status_text}
                {'' if service_running else ' - Start with: <code>bash scripts/start_qwen3_tts.sh</code>'}
            </p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(
                    label="Upload Document",
                    file_types=[".pdf", ".epub", ".docx", ".doc", ".txt"],
                    type="filepath",
                )

                preview_btn = gr.Button("Preview Text", variant="secondary")

                with gr.Accordion("Text Preview", open=False):
                    text_preview = gr.Textbox(
                        label="Extracted Text",
                        lines=10,
                        interactive=False,
                    )
                    word_count = gr.Number(
                        label="Word Count",
                        interactive=False,
                    )

                speaker = gr.Dropdown(
                    choices=SPEAKERS,
                    value="Ryan",
                    label="Speaker Voice",
                )

                language = gr.Dropdown(
                    choices=LANGUAGES,
                    value="Auto",
                    label="Language",
                )

                style_instruct = gr.Textbox(
                    label="Style Instruction (Optional)",
                    lines=2,
                    placeholder="e.g., Read in a calm, storytelling tone",
                )

                words_per_chunk = gr.Slider(
                    minimum=500,
                    maximum=2000,
                    value=1200,
                    step=100,
                    label="Words per Chunk",
                    info="Smaller chunks = more stable but more API calls",
                )

                convert_btn = gr.Button("Convert to Audiobook", variant="primary", size="lg")

            with gr.Column(scale=1):
                audio_output = gr.Audio(
                    label="Audiobook Preview",
                    type="filepath",
                )

                mp3_output = gr.File(
                    label="Download MP3",
                )

                status_output = gr.Textbox(
                    label="Status",
                    lines=8,
                    interactive=False,
                )

        # Event handlers
        preview_btn.click(
            fn=preview_document,
            inputs=[file_input],
            outputs=[text_preview, word_count],
        )

        convert_btn.click(
            fn=convert_to_audiobook,
            inputs=[
                file_input,
                speaker,
                language,
                style_instruct,
                words_per_chunk,
            ],
            outputs=[audio_output, mp3_output, status_output],
        )

        gr.HTML(f"""
        <div style="text-align: center; margin-top: 1rem; padding: 1rem; background: #FFF7ED; border-radius: 8px;">
            <p style="margin: 0; color: #C2410C;">
                <strong>Output directory:</strong> ~/ai_generated/qwen3-audiobook/
            </p>
            <p style="margin: 0.5rem 0 0 0; color: #EA580C; font-size: 0.9em;">
                Requires Qwen3-TTS running on port {TTS_PORT}
            </p>
        </div>
        """)

        gr.Markdown("""
        ---
        **Supported Formats:** PDF, EPUB, DOCX, DOC, TXT |
        **TTS Backend:** [Qwen3-TTS](https://huggingface.co/collections/Qwen/qwen3-tts) |
        **Output:** MP3 Audiobook
        """)

    return demo


if __name__ == "__main__":
    print("Qwen3 Audiobook Converter")
    print("=========================")
    print(f"TTS Service: {TTS_URL}")
    print(f"Output directory: {OUTPUT_DIR}")

    if not check_tts_service():
        print(f"\nWarning: Qwen3-TTS not running on port {TTS_PORT}")
        print("Start it first: bash scripts/start_qwen3_tts.sh")

    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=8014,
        share=False,
        show_error=True,
        allowed_paths=[str(OUTPUT_DIR)],
        theme=gr.themes.Soft(primary_hue="orange", secondary_hue="red"),
    )
