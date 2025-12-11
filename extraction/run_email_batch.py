import os
import json
from pathlib import Path
import csv
from email_extractor import extract_email_only

DATASET = Path("audio_dataset")
OUTPUT = "email_evals1.csv"

rows = []
folders = [f for f in DATASET.iterdir() if f.is_dir()]
total = len(folders)

print(f"Processing {total} folders...\n")

for idx, folder in enumerate(folders, start=1):
    print(f"[{idx}/{total}] → {folder.name}")

    transcript_path = folder / "transcript.txt"
    json_files = [f for f in folder.iterdir() if f.suffix.lower() == ".json"]

    if not transcript_path.exists() or len(json_files) == 0:
       print(f"   Skipping {folder.name} (missing transcript or json)")
       continue

    json_path = json_files[0] 

    transcript = transcript_path.read_text()
    gt = json.load(open(json_path))["email"].lower()

    extracted = extract_email_only(transcript)

    rows.append({
        "folder": folder.name,
        "groundtruth_email": gt,
        "extracted_email": extracted["final_email"],
        "spoken_chunk": extracted["spoken"],
        "spelled_raw": extracted["spelled_raw"],
        "transcript": transcript,
    })

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "folder", "groundtruth_email",
            "extracted_email", "spoken_chunk",
            "spelled_raw", "transcript"
        ]
    )
    writer.writeheader()
    writer.writerows(rows)

print("\nDONE → Saved:", OUTPUT)
