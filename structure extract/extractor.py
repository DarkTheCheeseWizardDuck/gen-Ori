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
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError("GROQ_API_KEY not found. Please create a .env file.")

if not model:
    raise ValueError("GROQ_MODEL not found. Please create a .env file.")

client = Groq(api_key=api_key)

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
def extract_structure(user_input: str) -> dict:
    """Extract structure from a natural language request."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.2,
        )

    except Exception as e:
        raise RuntimeError(f"Groq API call failed:\n{e}")

    raw = response.choices[0].message.content.strip()

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