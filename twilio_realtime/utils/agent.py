"""
Interactive CLI that converses to obtain a caller's name and email.
- Up to 3 attempts to capture spoken inputs (you can paste transcripts or type).
- If not confirmed after 3 attempts, falls back to manual text entry.
- Appends confirmed results to contacts.csv in the script directory.
"""
import re
import csv
import os
from datetime import datetime

CSV_PATH = os.path.join(os.path.dirname(__file__), "contacts.csv")


def _collapse_spelled_sequences(words):
    # Collapse sequences of single-letter tokens like "v n a t a" or "v-n-a"
    out = []
    buffer = []
    for w in words:
        clean = w.strip(" -").lower()
        if re.fullmatch(r"[a-zA-Z]", clean):
            buffer.append(clean)
            continue
        # if token contains only single letters separated by hyphens (e.g. v-n-a)
        if re.fullmatch(r"(?:[A-Za-z]-)+[A-Za-z]", w):
            out.append(re.sub(r"[-\s]", "", w))
            continue
        if buffer:
            out.append("".join(buffer))
            buffer = []
        out.append(w)
    if buffer:
        out.append("".join(buffer))
    return out


def normalize_spelled_out(text: str) -> str:
    # Break into words and collapse spelled-out sequences
    words = re.split(r"\s+", text.strip())
    collapsed = _collapse_spelled_sequences(words)
    return " ".join(collapsed)


_DIGIT_MAP = {
    "zero": "0", "oh": "0", "o": "0",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12",
    "double": "",  # handled as "double o" below
    "doubleo": "00", "double-o": "00", "double0": "00"
}


def normalize_email_text(text: str) -> str:
    s = text.lower()
    # collapse spelled sequences first
    s = normalize_spelled_out(s)
    # common word -> symbol
    s = re.sub(r"\b(at|@)\b", "@", s)
    s = re.sub(r"\b(dot|period)\b", ".", s)
    s = re.sub(r"\b(underscore)\b", "_", s)
    s = re.sub(r"\b(hyphen|dash)\b", "-", s)
    # handle "double o" or "double zero"
    s = re.sub(r"\bdouble\s+o\b", "00", s)
    s = re.sub(r"\bdouble\s+zero\b", "00", s)
    # convert digit words
    for word, digit in _DIGIT_MAP.items():
        s = re.sub(rf"\b{re.escape(word)}\b", digit, s)
    # remove filler words and spaces between email parts
    s = re.sub(r"[,\s]+", "", s)
    return s


def extract_email(text: str) -> str:
    if not text:
        return ""
    normalized = normalize_email_text(text)
    # simple RFC-lite pattern
    m = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", normalized)
    if m:
        return m.group(0)
    # try to salvage by allowing missing dot (e.g. gmailcom) by looking for common hosts
    for host in ("gmail", "yahoo", "outlook", "hotmail", "icloud"):
        m2 = re.search(rf"([\w\.-]+@{host})(?:com|\.com)?", normalized)
        if m2:
            return m2.group(1) + ".com"
    return ""


def extract_name(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    # common name declarations
    patterns = [
        r"(?:my name is|this is|i am|i'm|it's)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
        r"(?:my name is|this is|i am|i'm|it's)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
    ]
    for pat in patterns:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            # preserve casing if user typed mixed case; otherwise title-case
            if any(c.isupper() for c in name[1:]):
                return name
            return name.title()
    # fallback: if user provided a short token, return it title-cased
    token = s.split()[0]
    if 1 < len(token) <= 40:
        return token.title()
    return ""


def save_contact(name: str, email: str, attempts: int, confirmed: bool):
    header_needed = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(["timestamp", "name", "email", "attempts", "confirmed"])
        writer.writerow([datetime.utcnow().isoformat(), name, email, attempts, "yes" if confirmed else "no"])
    print(f"Saved to {CSV_PATH}")


def yesno_prompt(prompt: str) -> bool:
    resp = input(prompt + " (y/n): ").strip().lower()
    return resp in ("y", "yes")


def run_conversation():
    print("Contact capture conversation. You may paste a short transcript or type the values.")
    attempts_allowed = 3
    for attempt in range(1, attempts_allowed + 1):
        print(f"\nAttempt {attempt} of {attempts_allowed}")
        name_input = input("Enter what the user said for their NAME (or just type the name): ").strip()
        email_input = input("Enter what the user said for their EMAIL (or just type the email): ").strip()

        name_candidate = extract_name(name_input) or name_input.strip().title()
        email_candidate = extract_email(email_input) or email_input.strip()

        # Basic email validation
        email_valid = bool(re.fullmatch(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", email_candidate))

        print("\nI captured:")
        print(f"  Name : {name_candidate or 'Unnamed User'}")
        print(f"  Email: {email_candidate or 'noemail@example.com'} {'(looks valid)' if email_valid else '(may be invalid)'}")

        if yesno_prompt("Is this correct"):
            save_contact(name_candidate or "Unnamed User", email_candidate or "noemail@example.com", attempt, True)
            print("Confirmed. Done.")
            return
        else:
            print("Okay, let's try again.")

    # After attempts exhausted, ask for manual entry
    print("\nCould not confirm after 3 attempts. Please enter the values manually.")
    manual_name = input("Enter NAME: ").strip()
    manual_email = input("Enter EMAIL: ").strip()
    if not manual_name:
        manual_name = "Unnamed User"
    if not manual_email:
        manual_email = "noemail@example.com"

    print(f"\nYou entered:\n  Name: {manual_name}\n  Email: {manual_email}")
    if yesno_prompt("Confirm and save these"):
        save_contact(manual_name, manual_email, attempts_allowed, True)
        print("Saved. Done.")
    else:
        save_contact(manual_name, manual_email, attempts_allowed, False)
        print("Saved unconfirmed entry. Done.")


if __name__ == "__main__":
    run_conversation()