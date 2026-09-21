import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Import assign_length_weights from the length assignment module.
from length_assign import assign_length_weights

DEBUG = False

# -----------------------------
# Paths
# -----------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent

# -----------------------------
# Load environment variables
# -----------------------------
# These are only used as a *fallback* for local/CLI use (e.g. running this
# file directly). When served through interface/server.py, the browser's
# API-key modal supplies api_key/model per-request instead, so nothing here
# should raise at import time.
load_dotenv(ROOT_DIR / ".env")

DEFAULT_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# -----------------------------
# Load schema
# -----------------------------
try:
    with open(CURRENT_DIR / "schema.json", "r", encoding="utf-8") as f:
        schema_dict = json.load(f)

    schema = json.dumps(schema_dict, indent=2)

except Exception as e:
    raise RuntimeError(f"Failed to load schema.json:\n{e}")

# -----------------------------
# Load prompt
# -----------------------------
try:
    with open(CURRENT_DIR / "prompt.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

except Exception as e:
    raise RuntimeError(f"Failed to load prompt.txt:\n{e}")

system_prompt = prompt_template.replace("{SCHEMA}", schema)


# ==========================================================
# Main extraction function
# ==========================================================
def extract_structure(user_input: str, api_key: str | None = None, model: str | None = None) -> dict:
    """Extract structure from a natural language request.

    api_key/model let the caller (e.g. the web interface, using the key the
    visitor typed into the API-key modal) override the .env fallback on a
    per-request basis. Nothing is cached across calls, so different
    visitors' keys never mix.
    """

    resolved_key = api_key or DEFAULT_API_KEY
    resolved_model = model or DEFAULT_MODEL

    if not resolved_key:
        raise ValueError("No Groq API key provided. Pass api_key= or set GROQ_API_KEY in .env.")

    client = Groq(api_key=resolved_key)

    try:
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.2,
            max_tokens=4096
            # response_format={"type": "json_object"}
        )

    except Exception as e:
        raise RuntimeError(f"Groq API call failed:\n{e}")

    raw = response.choices[0].message.content.strip()

    if DEBUG:
        print("\n===== RAW RESPONSE =====")
        print(raw)
        print("========================\n")

    # Remove thinking block if present (e.g. from reasoning models)
    if "</think>" in raw:
        raw = raw.split("</think>", 1)[1].strip()

    # Remove Markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()

        if lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        raw = "\n".join(lines).strip()

    try:
        structure = json.loads(raw)
        return structure

    except json.JSONDecodeError:
        raise RuntimeError(
            "Groq did not return valid JSON.\n\nReturned text:\n" + raw
        )


def main():
    """Run extraction directly from this module."""
    user_input = input("Origami request: ")
    result = extract_structure(user_input)

    print("\nExtracted structure:\n")
    print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()