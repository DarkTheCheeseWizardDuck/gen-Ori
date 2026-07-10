import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

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

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY not found. Please create a .env file."
    )

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

# -----------------------------
# User input
# -----------------------------
user_input = input("Origami request: ")

# -----------------------------
# Call Gemini
# -----------------------------
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            system_prompt,
            user_input
        ]
    )

except Exception as e:
    print("\nGemini API call failed:")
    print(e)
    exit()

# -----------------------------
# Raw response
# -----------------------------
raw = response.text.strip()
if DEBUG:
    print("\n===== RAW RESPONSE =====")
    print(raw)
    print("========================\n")

# -----------------------------
# Remove Markdown code fences
# -----------------------------
if raw.startswith("```"):
    lines = raw.splitlines()

    if lines[0].startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]

    raw = "\n".join(lines).strip()

# -----------------------------
# Parse JSON
# -----------------------------
try:
    intent = json.loads(raw)

except json.JSONDecodeError:
    print("Gemini did not return valid JSON.")
    print("\nReturned text:\n")
    print(raw)
    exit()

# -----------------------------
# Display
# -----------------------------
print("Extracted Intent:\n")
print(json.dumps(intent, indent=4, ensure_ascii=False))