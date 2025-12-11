import os
import json
import csv
from pathlib import Path
from ai_extractor import extract_all

# --------------------------
# CONFIG
# --------------------------
DATASET_DIR = Path("audio_dataset")
OUTPUT_CSV = "extracted_results_all.csv"


# --------------------------
# Load transcript
# --------------------------
def load_transcript(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except:
        return ""


# --------------------------
# Load ground truth
# --------------------------
def load_groundtruth(folder):
    for file in Path(folder).iterdir():
        if file.suffix.lower() == ".json":
            try:
                data = json.loads(file.read_text())
                return data.get("name", ""), data.get("email", "")
            except:
                return "", ""
    return "", ""


# --------------------------
# Process a single folder
# --------------------------
def process_folder(folder_path):
    folder = Path(folder_path)
    transcript_path = folder / "transcript.txt"

    if not transcript_path.exists():
        print(f"Missing transcript in {folder.name}, skipping.")
        return None

    transcript = load_transcript(transcript_path)
    gt_name, gt_email = load_groundtruth(folder)

    ex = extract_all(transcript)

    return {
        "folder": folder.name,

        "groundtruth_name": gt_name,
        "groundtruth_email": gt_email,

        "spoken_name": ex["spoken_name"],
        "spoken_email_local": ex["spoken_email_local"],
        "spoken_email_domain": ex["spoken_email_domain"],
        "spoken_email": ex["spoken_email"],

        "spelled_raw": ex["spelled_raw"],
        "spelled_ai": ex["spelled_ai"],

        "spelled_email_raw": ex["spelled_email_raw"],
        "spelled_email_ai": ex["spelled_email_ai"],

        "final_name": ex["final_name"],
        "final_email": ex["final_email"],

        "transcript": transcript,
    }


# --------------------------
# MAIN
# --------------------------
def main():
    rows = []

    for folder in DATASET_DIR.iterdir():
        if folder.is_dir():
            print(f"Processing: {folder.name}")
            row = process_folder(folder)
            if row:
                rows.append(row)

    fieldnames = [
        "folder",
        "groundtruth_name",
        "groundtruth_email",

        "spoken_name",
        "spoken_email_local",
        "spoken_email_domain",
        "spoken_email",

        "spelled_raw",
        "spelled_ai",

        "spelled_email_raw",
        "spelled_email_ai",

        "final_name",
        "final_email",

        "transcript"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExtraction complete → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
