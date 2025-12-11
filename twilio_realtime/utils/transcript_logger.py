"""
Utilities for extracting and logging name and email from call transcripts.
"""

import re
import json
import csv
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

system_prompt = """
You are an assistant that extracts specific data from a call transcript.
Extract the final confirmed name and email from the conversation, considering both user statements and assistant confirmations.
Return only the data in pure JSON format with two keys: "name" and "email".
Do not alter the user’s name or email in any way. Use the exact input provided by the user.
If the email contains spoken phrases (e.g., "at", "dot"), normalize them to standard format (e.g., "@", ".") and ensure the email uses digits for numbers (e.g., 'thirteen' as '13').
Example:
User says: "v n a t a zero zero one at g mail dot com"
Return: {"name": "<name>", "email": "vnata001@gmail.com"}
"""

def get_user_only_transcript(transcript: str) -> str:
    return "\n".join([line for line in transcript.splitlines() if "USER:" in line])

def get_transcripted_name(transcript: str) -> str:
    user_lines = [line for line in transcript.splitlines() if "USER:" in line]

    for line in reversed(user_lines):
        match = re.search(r"(?:my name is|this is|i am)\s(.+)", line, re.IGNORECASE)
        if match:
            return match.group(1).rstrip(".")  # Remove trailing period if present

    assistant_lines = transcript.splitlines()
    for i, line in enumerate(assistant_lines):
        if "ASSISTANT:" in line and "your name is" in line.lower():
            name_match = re.search(r"your name is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", line)
            if name_match:
                for j in range(i + 1, min(i + 4, len(assistant_lines))):
                    if "USER:" in assistant_lines[j] and any(x in assistant_lines[j].lower() for x in ["yes", "yeah", "correct", "that's right", "yep"]):
                        return name_match.group(1)

    return "Unnamed User"

def normalize_email_text(text: str) -> str:
    text = text.lower()

    # Normalize email terms
    text = re.sub(r'\s*at\s*', '@', text)
    text = re.sub(r'\s*dot\s*', '.', text)
    text = re.sub(r'\s*underscore\s*', '_', text)
    text = re.sub(r'\s*hyphen\s*|-|\s*dash\s*', '-', text)

    # Handle phonetics like "z for zebra"
    text = re.sub(r'\b([a-zA-Z])\s*for\s*\w+\b', r'\1', text)

    # Convert digits
    digit_map = {
        "zero": "0", "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6", "seven": "7",
        "eight": "8", "nine": "9", "oh": "0", "double o": "00"
    }
    for word, digit in digit_map.items():
        text = re.sub(rf"\b{word}\b", digit, text)

    text = re.sub(r'\s+', '', text)  # remove all spaces
    return text

def normalize_spelled_out(text: str) -> str:
    """Convert spelled-out sequences like T-H-E to the."""
    words = text.split()
    result = []
    for word in words:
        if re.match(r"^[A-Z](?:-[A-Z])+$", word):
            cleaned = "".join(word.split("-")).lower()
            result.append(cleaned)
        else:
            result.append(word)
    return " ".join(result)

def get_transcripted_email(transcript: str) -> str:
    user_lines = [line.replace("USER:", "").strip() for line in transcript.splitlines() if "USER:" in line]

    # Combine all user lines into one string
    joined = " ".join(user_lines)

    # Handle spelled-out sequences
    joined = normalize_spelled_out(joined)

    # Normalize common spoken substitutions
    normalized_joined = normalize_email_text(joined)

    # DEBUG: See what we're matching
    print("[DEBUG] USER email string before spelled-out normalization:", joined)
    print("[DEBUG] Normalized USER email string:", normalized_joined)

    # Try matching complete email from normalized user text
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", normalized_joined)
    if match:
        return match.group(0)

    # Priority 2: Search individual lines that mention "email" or "address"
    for line in reversed(user_lines):
        if any(x in line.lower() for x in ["email", "mail", "my email is", "address is", "this is"]):
            normalized_line = normalize_spelled_out(line)
            normalized_line = normalize_email_text(normalized_line)
            match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", normalized_line)
            if match:
                return match.group(0)

    # Priority 3: Assistant-quoted email with user confirmation
    assistant_lines = transcript.splitlines()
    for i, line in enumerate(assistant_lines):
        if "ASSISTANT:" in line and any(keyphrase in line.lower() for keyphrase in ["email address is", "your email is", "let me confirm, your email"]):
            normalized = normalize_spelled_out(line)
            normalized = normalize_email_text(normalized)
            match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", normalized)
            if match:
                for j in range(i + 1, min(i + 4, len(assistant_lines))):
                    if "USER:" in assistant_lines[j] and any(word in assistant_lines[j].lower() for word in ["yes", "yeah", "correct", "that's right", "yep"]):
                        return match.group(0)

    # Final fallback
    return "noemail@example.com"

def extract_assistant_suggested_email(transcript: str) -> str:
    lines = transcript.splitlines()
    for i, line in enumerate(lines):
        if "ASSISTANT:" in line and any(keyphrase in line.lower() for keyphrase in ["email address is", "your email is", "let me confirm, your email"]):
            # Try to extract the email part after "is" or similar
            normalized = line.lower()
            for keyphrase in ["email address is", "your email is", "let me confirm, your email"]:
                if keyphrase in normalized:
                    # Find the position after the keyphrase and extract potential email
                    start_pos = normalized.find(keyphrase) + len(keyphrase)
                    potential_email = normalized[start_pos:].strip(", ").strip()
                    # Normalize the potential email
                    normalized_email = normalize_email_text(potential_email)
                    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", normalized_email)
                    if match:
                        for j in range(i + 1, min(i + 4, len(lines))):
                            if "USER:" in lines[j] and any(word in lines[j].lower() for word in ["yes", "yeah", "correct", "that's right", "yep"]):
                                return match.group(0)
    return ""

def extract_assistant_suggested_name(transcript: str) -> str:
    lines = transcript.splitlines()
    for line in reversed(lines):
        if "ASSISTANT:" in line and "your name is" in line.lower():
            match = re.search(r"your name is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", line)
            if match:
                return match.group(1)
    return ""

def extract_name_email(transcript: str) -> dict:
    gpt_name, gpt_email = "", ""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        extracted = json.loads(content)
        gpt_name = extracted.get("name", "").strip()
        gpt_email = extracted.get("email", "").strip()

    except Exception as e:
        print(f"GPT extraction failed: {e}")

    fallback_name = get_transcripted_name(transcript)
    fallback_email = get_transcripted_email(transcript)

    return {
        "transcripted_name": fallback_name,
        "transcripted_email": fallback_email,
        "gpt_name": gpt_name or fallback_name,
        "gpt_email": gpt_email or fallback_email
    }

def confirm_and_log(call_id: str, transcript: str, attempt_number: int = 1):
    data = extract_name_email(transcript)

    assistant_suggested_name = extract_assistant_suggested_name(transcript)
    assistant_suggested_email = extract_assistant_suggested_email(transcript)

    # Determine attempt numbers for name and email
    lines = transcript.splitlines()
    name_no_count = 0
    email_no_count = 0
    in_name_confirmation = False
    in_email_confirmation = False

    for i, line in enumerate(lines):
        if "ASSISTANT:" in line and "your name is" in line.lower():
            in_name_confirmation = True
            in_email_confirmation = False
        elif "ASSISTANT:" in line and any(keyphrase in line.lower() for keyphrase in ["email address is", "your email is", "let me confirm, your email"]):
            in_name_confirmation = False
            in_email_confirmation = True
        elif "USER:" in line and "no" in line.lower():
            if in_name_confirmation:
                name_no_count += 1
            elif in_email_confirmation:
                email_no_count += 1

    name_attempt_number = "none" if name_no_count >= 2 or data["gpt_name"] != assistant_suggested_name else (2 if name_no_count == 1 else 1)
    email_attempt_number = "none" if email_no_count >= 2 or data["gpt_email"] != assistant_suggested_email else (2 if email_no_count == 1 else 1)

    # Determine confirmation status
    name_status = "confirmed" if data["gpt_name"] == assistant_suggested_name else "corrected"
    email_status = "confirmed" if data["gpt_email"] == assistant_suggested_email else "corrected"

    # Calculate confidence scores (heuristic: 1.0 if all match, 0.75 if two match, 0.5 otherwise)
    name_confidence = 1.0 if data["transcripted_name"] == data["gpt_name"] == assistant_suggested_name else (0.75 if data["gpt_name"] == assistant_suggested_name else 0.5)
    email_confidence = 1.0 if data["transcripted_email"] == data["gpt_email"] == assistant_suggested_email else (0.75 if data["gpt_email"] == assistant_suggested_email else 0.5)

    # print(f"\nTranscripted Name: {data['transcripted_name']}")
    # print(f"Transcripted Email: {data['transcripted_email']}")
    # print(f"Assistant Suggested Name: {assistant_suggested_name}")
    # print(f"Assistant Suggested Email: {assistant_suggested_email}")
    print("\n")
    print(f"GPT Captured Name: {data['gpt_name']}")
    print(f"GPT Captured Email: {data['gpt_email']}")
    print("\n")
    print(f"Name Attempt: {name_attempt_number} | Email Attempt: {email_attempt_number} | "
      f"Name Status: {name_status} | Email Status: {email_status} | "
      f"Name Confidence: {name_confidence:.2f} | Email Confidence: {email_confidence:.2f}")
    print("\n")
    actual_name = input("Actual Name (press Enter to accept): ").strip() or data["gpt_name"]
    actual_email = input("Actual Email (press Enter to accept): ").strip() or assistant_suggested_email or data["gpt_email"]

    # Update status based on actual input
    name_status = "confirmed" if actual_name == data["gpt_name"] else "corrected"
    email_status = "confirmed" if actual_email == data["gpt_email"] else "corrected"

    row = {
        "call_id": call_id,
        "assistant_suggested_name": assistant_suggested_name,
        "transcripted_name": data["transcripted_name"],
        "gpt_name": data["gpt_name"],
        "actual_name": actual_name,
        "assistant_suggested_email": assistant_suggested_email,
        "transcripted_email": data["transcripted_email"],
        "gpt_email": data["gpt_email"],
        "actual_email": actual_email,
        "name_attempt_number": name_attempt_number,
        "email_attempt_number": email_attempt_number,
        "name_status": name_status,
        "email_status": email_status,
        "name_confidence": name_confidence,
        "email_confidence": email_confidence
    }

    file = "openai_calls2.csv"
    file_exists = os.path.isfile(file)
    fieldnames = [
        "call_id",
        "assistant_suggested_name",
        "transcripted_name",
        "gpt_name",
        "actual_name",
        "assistant_suggested_email",
        "transcripted_email",
        "gpt_email",
        "actual_email",
        "name_attempt_number",
        "email_attempt_number",
        "name_status",
        "email_status",
        "name_confidence",
        "email_confidence"
    ]

    with open(file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print("Saved to CSV.")