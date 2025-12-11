import os
import json
from pathlib import Path
import subprocess
import tempfile
from openai import OpenAI
from dotenv import load_dotenv

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Folder where ALL audio folders exist
DATASET_DIR = Path("audio_dataset")   


def convert_to_clean_wav(input_path):
    """
    Normalize audio for Whisper transcription.
    """
    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ac", "1",
        "-ar", "16000",
        temp_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return temp_wav


def transcribe_audio(audio_path):
    """
    Use OpenAI Whisper to transcribe speech.
    """
    try:
        clean = convert_to_clean_wav(audio_path)

        with open(clean, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", f.read())
            )

        return resp.text.strip()

    except Exception as e:
        print(f"[ERROR] Transcribing {audio_path}: {e}")
        return ""


def process_folder(folder: Path):
    """
    Finds the audio file, transcribes it, and writes transcript.txt
    """
    wav_file = None
    for file in os.listdir(folder):
        if file.lower().endswith(".wav"):
            wav_file = folder / file
            break

    if not wav_file:
        print(f"Skipping {folder} (missing .wav)")
        return

    print(f"\nTranscribing: {wav_file.name}")

    transcript = transcribe_audio(wav_file)
    print("Transcript:", transcript)

    # Save transcript.txt
    transcript_path = folder / "transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")


def main():
    print("=== Generating transcripts for dataset ===")

    for folder in DATASET_DIR.iterdir():
        if folder.is_dir():
            process_folder(folder)

    print("\n✓ All transcripts generated successfully.")
    print("✓ Now run:  python extraction/extract_from_transcripts.py")


if __name__ == "__main__":
    main()
