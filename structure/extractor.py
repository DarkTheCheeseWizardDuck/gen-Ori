import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

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
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found. Please create a .env file.")

if not model:
    raise ValueError("GEMINI_MODEL not found. Please create a .env file.")

client = genai.Client(api_key=api_key)

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
def extract_intent(user_input: str) -> dict:
    """Extract structured origami intent from a natural language request."""

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                system_prompt,
                user_input
            ],
            config={
                "temperature": 0.2
            }
        )

    except Exception as e:
        raise RuntimeError(f"Gemini API call failed:\n{e}")

    raw = response.text.strip()

    if DEBUG:
        print("\n===== RAW RESPONSE =====")
        print(raw)
        print("========================\n")

    # Remove Markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()

        if lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        raw = "\n".join(lines).strip()

    try:
        intent = json.loads(raw)
        return intent

    except json.JSONDecodeError:
        raise RuntimeError(
            "Gemini did not return valid JSON.\n\nReturned text:\n" + raw
        )