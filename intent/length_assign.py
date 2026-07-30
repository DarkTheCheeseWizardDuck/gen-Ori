import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL")

with open(CURRENT_DIR / "length_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def assign_length_weights(intent: dict) -> dict:
    """
    Fill the length_weight field for every part.
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            SYSTEM_PROMPT,
            json.dumps(intent, ensure_ascii=False)
        ],
        config={
            "temperature": 0.2
        }
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()

    return json.loads(raw)