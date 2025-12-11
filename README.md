# ASR Voice Agent (Structured Data Extraction) – Quick Start Guide

This repository contains a Twilio-connected real-time voice agent using Deepgram (demo mode) and OpenAI.
---

## 1. Environment Setup

Create a `.env` file in the project root (do not push this to GitHub).
Include the following keys:

```
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...

OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...

VOICE_PROVIDER=deepgram_demo
```

`VOICE_PROVIDER=deepgram_demo` selects the Deepgram STT + OpenAI reasoning demo mode.

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 2. Start the Server

Run:

```bash
python -m twilio_realtime.main
```

This loads:

- `main.py` – starts the FastAPI app
- `app.py` – creates the application
- `routes/root.py` – selects voice provider and attaches correct router
- `routes/deepgram_demo.py` – handles Twilio media stream + Deepgram + OpenAI
- `services/openai_service.py` – LLM reasoning and response generation
- `utils/agent.py` – conversation logic
- `utils/transcript_processor.py` – audio event handling
- `utils/transcript_logger.py` – logs and extracts final name/email
- `models/connection_store.py` – session tracking for each active call

---

## 3. Expose the Server Using Ngrok

In a new terminal:

```bash
ngrok http 5002
```

Copy the HTTPS forwarding URL.

---

## 4. Set Twilio Webhook

Use the webhook helper:

```bash
python utils/set_twilio_webhook.py https://YOUR-NGROK-URL
```

This configures your Twilio phone number to forward calls to:

```
POST https://YOUR-NGROK-URL/
```

---

## 5. Make a Call

Call your Twilio phone number.

The pipeline will run:

Audio → Twilio Media Stream → Deepgram STT → OpenAI reasoning → TTS audio reply → Caller

The agent will speak, listen, ask for name/email, confirm details, and log the transcript.

---

## Component Overview

| File / Folder | Purpose |
|---------------|---------|
| `main.py` | Entry point that starts the FastAPI server |
| `app.py` | Creates the FastAPI application instance |
| `config/settings.py` | Loads environment variables and provider settings |
| `config/prompts_simple.py` | System prompts used by the conversational agent |
| `routes/root.py` | Selects routing logic based on VOICE_PROVIDER |
| `routes/deepgram_demo.py` | Handles Twilio media stream + Deepgram demo STT |
| `services/openai_service.py` | Sends user text to OpenAI and returns responses |
| `models/connection_store.py` | Stores state per active call (WebSocket sessions) |
| `utils/agent.py` | Core agent logic for dialogue and message flow |
| `utils/transcript_processor.py` | Manages incoming transcription frames |
| `utils/transcript_logger.py` | Extracts final name/email and saves transcript |
| `utils/utils.py` | Misc helper functions |
| `utils/set_twilio_webhook.py` | Automatically configures Twilio webhook |

---

## Quick Start (6 Steps)

1. Add API keys to `.env`
2. Set `VOICE_PROVIDER=deepgram_demo`
3. Run server:
   ```bash
   python -m twilio_realtime.main
   ```
4. Start ngrok in new terminal:
   ```bash
   ngrok http 5002
   ```
5. Apply ngrok URL to Twilio:
   ```bash
   python utils/set_twilio_webhook.py https://YOUR-NGROK-URL
   ```
6. Call your Twilio phone number

The agent is now live.

---
# Audio Dataset Workflow - Evaluation Steps

## Step 1: Place Audio + Ground Truth Files

Create the directory structure:
```
audio_dataset/
├── sample_01/
│   ├── audio.wav
│   └── groundtruth.json
├── sample_02/
│   ├── audio.wav
│   └── groundtruth.json
└── ...
```

Audio requirements:
- Format: WAV
- Sample Rate: 16kHz
- Channels: Mono
- Duration: 10-60 seconds

Ground truth JSON format:
```json
{
    "name": "John Michael Smith",
    "email": "john.smith@gmail.com"
}
```

Important: Do NOT manually create `transcript.txt` files - they are generated automatically in Step 2.

---

## Step 2: Generate Transcripts

Run the transcription script:
```bash
python transcription/process_audio_dataset.py
```

This script:
- Converts audio to clean format
- Sends audio to Whisper for speech-to-text
- Generates `transcript.txt` in each folder
- Creates `processed_audio_dataset.csv` summary

Expected output structure:
```
audio_dataset/
├── sample_01/
│   ├── audio.wav
│   ├── groundtruth.json
│   └── transcript.txt (NEW)
├── sample_02/
│   ├── audio.wav
│   ├── groundtruth.json
│   └── transcript.txt (NEW)
└── ...
```

Sample transcript.txt:
```
CUSTOMER: My name is John Michael Smith. J-O-H-N M-I-C-H-A-E-L S-M-I-T-H.
AGENT: Your email address?
CUSTOMER: john dot smith at gmail dot com.
```

Troubleshooting:
- transcript.txt not created: Check audio file is readable
- Empty transcript: Audio file may be corrupted or silent
- API timeout: Check internet connection

---

## Step 3: Extract Spoken + Spelled Names and Emails

Run the extraction script:
```bash
python extraction/extract_from_transcripts.py
```

This script:
- Reads each folder in `audio_dataset/`
- Reads the generated `transcript.txt`
- Applies regex extraction
- Uses AI to reconstruct spelled-out sequences
- Saves results to `extracted_results_all.csv`

---

## Step 4: Evaluate Accuracy in Notebook

Open the evaluation notebook:
```bash
jupyter notebook evaluation/NLP_ASR_Evaluation.ipynb
```

Required files before running:
1. `extracted_results_all.csv` (from Step 3)
2. `email_evals.csv` (optional, generated during extraction)

Key notebook cells to run in order:

## Complete Workflow Example

```bash
# Setup
cd d:\nlp-voice-agent

# Step 1: Place files manually
# Create audio_dataset/ folders with audio.wav + groundtruth.json

# Step 2: Generate transcripts
python transcription/process_audio_dataset.py

# Step 3: Extract information
python extraction/extract_from_transcripts.py

# Step 4: Evaluate in notebook
jupyter notebook evaluation/NLP_ASR_Evaluation.ipynb
```

---

