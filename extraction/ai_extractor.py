import re
import os
from openai import OpenAI
from dotenv import load_dotenv

# ---------------------------------------------------------
# Load .env from parent directory
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, "..", ".env")
load_dotenv(ENV_PATH)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------
# AI safe wrapper
# ---------------------------------------------------------
def ask_ai(system, user):
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("\nAI ERROR:", e)
        return ""


# ---------------------------------------------------------
# JSON-based NAME reconstruction
# ---------------------------------------------------------
def ai_reconstruct_name(raw_spelled):
    system = "You reconstruct human names from spelled-out letters. Follow rules strictly."
    user = f"""
Interpret the following spelled-out name:

"{raw_spelled}"

Rules:
- DO NOT invent or remove letters.
- Only add spacing and capitalization.
- DO NOT repeat the name twice.
- If unsure, return the capitalized form exactly.
- Examples:
    t-o-m-m-y-g-o-a-t → Tommy Goat
    e-m-i-l-y-s-m-y-t-h → Emily Smyth
    n-a-t-h-a-n-d-c-a-r-t-e-r → Nathan D Carter

Output JSON ONLY:
{{
  "name": ""
}}
"""
    reply = ask_ai(system, user)

    match = re.search(r'"name"\s*:\s*"([^"]*)"', reply)
    if match:
        return match.group(1).strip()

    return ""


# ---------------------------------------------------------
# JSON-based EMAIL reconstruction
# ---------------------------------------------------------
def ai_reconstruct_email(spelled_local, spoken_domain):
    system = "Reconstruct emails from spelled-out local-part and optional domain."
    user = f"""
Spelled local-part: "{spelled_local}"
Spoken domain: "{spoken_domain}"

Rules:
- Reconstruct EXACTLY one email.
- Only infer standard domains if missing (gmail.com, yahoo.com, icloud.com).
- Do NOT invent letters.
- Email must be in format local@domain.

Output JSON ONLY:
{{
  "email": ""
}}
"""
    reply = ask_ai(system, user)

    match = re.search(r'"email"\s*:\s*"([^"]*)"', reply)
    if match:
        return match.group(1).strip().lower()

    return ""


# ---------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------
# DASH-BASED SPELLED LETTER SEQUENCES (accurate!)
SPELLED_DASH_RE = re.compile(
    r"\b(?:[A-Za-z]-){2,}[A-Za-z]\b"
)

# SPOKEN NAME
NAME_SPOKEN_RE = re.compile(
    r"(?:my name is|this is)\s+([A-Za-z][A-Za-z\s.'-]+?)(?:[,.]|$)",
    re.IGNORECASE
)

# SPOKEN EMAIL
EMAIL_SPOKEN_RE = re.compile(
    r"(?:my email is|email is)\s+([\w\.-]+)\s*(?:at)\s*([\w\.-]+)",
    re.IGNORECASE
)


# ---------------------------------------------------------
# Normalizers
# ---------------------------------------------------------
def normalize_name(n):
    return " ".join(p.capitalize() for p in n.strip().split())


def normalize_email(local, domain):
    local = local.replace("-", "").replace(" ", "").lower()
    domain = domain.replace(" ", "").lower()

    domain = domain.replace("dot", ".")

    if "." not in domain:
        domain += ".com"

    return f"{local}@{domain}"


# ---------------------------------------------------------
# MAIN EXTRACTION FUNCTION
# ---------------------------------------------------------
def extract_all(transcript):

    # -------------------------------
    # 1. SPOKEN NAME
    # -------------------------------
    spoken_name_ai = ""
    m = NAME_SPOKEN_RE.search(transcript)
    if m:
        raw_spoken = m.group(1).strip()
        spoken_name_ai = ask_ai(
            "You receive ONLY the spoken name. Output a single clean formatted name.",
            raw_spoken
        )
        spoken_name_ai = normalize_name(spoken_name_ai)

    # -------------------------------
    # 2. SPELLED NAME (dash groups)
    # -------------------------------
    spelled_groups = SPELLED_DASH_RE.findall(transcript)
    spelled_raw = " ".join(spelled_groups)

    spelled_ai = ""
    if spelled_raw:
        spelled_ai = ai_reconstruct_name(spelled_raw)
        spelled_ai = normalize_name(spelled_ai)

    # Decide best final name
    final_name = spelled_ai if spelled_ai else spoken_name_ai

    # -------------------------------
    # 3. SPOKEN EMAIL
    # -------------------------------
    spoken_email_local = ""
    spoken_email_domain = ""
    spoken_email = ""

    em = EMAIL_SPOKEN_RE.search(transcript)
    if em:
        spoken_email_local = em.group(1)
        spoken_email_domain = em.group(2)
        spoken_email = normalize_email(spoken_email_local, spoken_email_domain)

    # -------------------------------
    # 4. AI-SPELLED EMAIL
    # -------------------------------
    spelled_email_raw = spelled_raw  # local-part spelled groups

    spelled_email_ai = ""
    if spelled_email_raw:
        spelled_email_ai = ai_reconstruct_email(spelled_email_raw, spoken_email_domain)

    # Final email decision
    final_email = spelled_email_ai if spelled_email_ai else spoken_email

    return {
        "spoken_name": spoken_name_ai,
        "spelled_raw": spelled_raw,
        "spelled_ai": spelled_ai,
        "final_name": final_name,

        "spoken_email_local": spoken_email_local,
        "spoken_email_domain": spoken_email_domain,
        "spoken_email": spoken_email,

        "spelled_email_raw": spelled_email_raw,
        "spelled_email_ai": spelled_email_ai,

        "final_email": final_email,
    }
