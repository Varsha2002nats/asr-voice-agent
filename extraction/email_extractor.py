import re
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# ---------------------------------------------------------
# Load environment
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, "..", ".env")
load_dotenv(ENV_PATH)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------
# Normalization utilities
# ---------------------------------------------------------
def normalize_email_text(text: str) -> str:
    """Normalize spoken email into a machine-readable form."""
    text = text.lower()

    # spoken operators → symbols
    text = re.sub(r'\s*at\s*', '@', text)
    text = re.sub(r'\s*dot\s*', '.', text)
    text = re.sub(r'\s*underscore\s*', '_', text)
    text = re.sub(r'\s*(?:dash|hyphen)\s*', '-', text)

    # Remove “x for x-ray”
    text = re.sub(r'\b([a-zA-Z])\s*for\s*\w+\b', r'\1', text)

    # digit words → numbers
    digit_map = {
        "zero": "0", "oh": "0", "double o": "00",
        "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6",
        "seven": "7", "eight": "8", "nine": "9"
    }
    for word, digit in digit_map.items():
        text = re.sub(rf"\b{word}\b", digit, text)

    # remove all spaces
    text = re.sub(r"\s+", "", text)

    return text


def normalize_spelled_out(text: str) -> str:
    """Convert T-H-E into "the"."""
    words = text.split()
    result = []
    for word in words:
        if re.match(r"^[A-Za-z](?:-[A-Za-z])+$", word):
            cleaned = "".join(word.split("-")).lower()
            result.append(cleaned)
        else:
            result.append(word)
    return " ".join(result)


# ---------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
SPELLED_PATTERN = re.compile(r"\b(?:[A-Za-z]-){2,}[A-Za-z]\b")


# ---------------------------------------------------------
# GPT wrapper for email reconstruction
# ---------------------------------------------------------
def ai_reconstruct_email(local_spelled, spoken_chunk):
    """
    Use GPT ONLY to join spelled letters + spoken chunk.
    It must not hallucinate or invent symbols.
    """
    system = """
You reconstruct email addresses from spelled letters and spoken fragments.

STRICT RULES:
- Use ONLY letters, digits, dash, underscore, and dots present in the input.
- DO NOT invent characters.
- DO NOT hallucinate domains.
- If the spoken part contains a domain, use exactly that domain.
- If domain missing, choose from: gmail.com, yahoo.com, icloud.com, hotmail.com, outlook.com, fastmail.com.
- Produce exactly ONE valid RFC-style email.
- Output JSON ONLY: {"email": "..."}.
"""

    user = f"""
Spelled letters:
{local_spelled}

Spoken chunk:
{spoken_chunk}

Reconstruct the exact intended email, combining spelled letters + digits + domain.
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        )
        msg = r.choices[0].message.content.strip()
        m = re.search(r'"email"\s*:\s*"([^"]+)"', msg)
        if m:
            return m.group(1).lower().strip()
    except Exception as e:
        print("\n[AI ERROR reconstructing email]:", e)

    return ""


# ---------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------
def extract_email_only(transcript: str):
    """
    Returns:
    {
        spoken: raw spoken chunk,
        spelled_raw: spelled letters (T-O-M),
        final_email: best reconstructed email
    }
    """

    # -----------------------------------
    # 1. Spoken email chunk
    # -----------------------------------
    spoken_chunk = ""
    for line in transcript.lower().splitlines():
        if "email" in line or "mail" in line:
            spoken_chunk = line
            break

    spoken_chunk = normalize_email_text(normalize_spelled_out(spoken_chunk))

    # -----------------------------------
    # 2. Spelled letter groups (R-A-C-H-E-L)
    # -----------------------------------
    spelled_groups = SPELLED_PATTERN.findall(transcript)
    spelled_raw = " ".join(spelled_groups)

    # -----------------------------------
    # 3. AI reconstruction
    # -----------------------------------
    final_email = ai_reconstruct_email(spelled_raw, spoken_chunk)

    # -----------------------------------
    # 4. Try strict regex fallback (if AI fails)
    # -----------------------------------
    fulltext_norm = normalize_email_text(normalize_spelled_out(transcript))
    m = EMAIL_REGEX.search(fulltext_norm)
    if not final_email and m:
        final_email = m.group(0)

    # -----------------------------------
    # 5. Fallback to safe placeholder
    # -----------------------------------
    if not final_email:
        final_email = "noemail@example.com"

    return {
        "spoken": spoken_chunk,
        "spelled_raw": spelled_raw,
        "final_email": final_email,
    }
