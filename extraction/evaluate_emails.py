import os
import json
import csv
from pathlib import Path

from email_extractor import extract_email   

DATASET_DIR = Path("audio_dataset")
OUTPUT_CSV = "email_eval.csv"


def load_groundtruth(json_path):
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        return data.get("email", "").strip().lower()
    except:
        return ""


def load_transcript(folder):
    txt_path = Path(folder) / "transcript.txt"
    if txt_path.exists():
        return txt_path.read_text().strip()
    return ""


def process_folder(folder_path):
    folder = Path(folder_path)
    json_file = None

    # locate groundtruth JSON
    for f in folder.iterdir():
        if f.suffix.lower() == ".json":
            json_file = f
            break

    if json_file is None:
        print(f"Skipping {folder.name} (no groundtruth json)")
        return None

    # load transcript.txt
    transcript = load_transcript(folder)
    if not transcript:
        print(f"Skipping {folder.name} (no transcript.txt found)")
        return None

    # groundtruth email
    gt_email = load_groundtruth(json_file)

    # run email extraction
    extracted = extract_email(transcript)

    return {
        "folder": folder.name,
        "groundtruth_email": gt_email,
        "extracted_email": extracted["final_email"],
        "spoken_chunk": extracted["spoken"],
        "spelled_raw": extracted["spelled_raw"],
        "transcript": transcript,
    }


def main():
    rows = []

    for folder in DATASET_DIR.iterdir():
        if folder.is_dir():
            result = process_folder(folder)
            if result:
                rows.append(result)

    # save output CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "folder",
                "groundtruth_email",
                "extracted_email",
                "spoken_chunk",
                "spelled_raw",
                "transcript",
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print("\nSaved →", OUTPUT_CSV)


if __name__ == "__main__":
    main()
