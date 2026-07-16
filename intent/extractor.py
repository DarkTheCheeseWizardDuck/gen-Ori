import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

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
def extract_intent(user_input: str) -> dict:
    """Extract structured origami intent from a natural language request."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_input
                }
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
        return json.loads(raw)

    except json.JSONDecodeError:
        raise RuntimeError(
            "Groq/Qwen did not return valid JSON.\n\nReturned text:\n" + raw
        )


# ==========================================================
# CLI
# ==========================================================
def main():
    user_input = input("Origami request: ")

    intent = extract_intent(user_input)

    print("\nExtracted Intent:\n")
    print(json.dumps(intent, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()