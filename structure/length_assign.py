import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

# Fallback for local/CLI use only -- see the matching note in extractor.py.
DEFAULT_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

with open(CURRENT_DIR / "length_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def assign_length_weights(intent: dict, api_key: str | None = None, model: str | None = None) -> dict:
    """
    Fill the length_weight field for every part.

    api_key/model override the .env fallback per-request (see extractor.py).
    """

    resolved_key = api_key or DEFAULT_API_KEY
    resolved_model = model or DEFAULT_MODEL

    if not resolved_key:
        raise ValueError("No Groq API key provided. Pass api_key= or set GROQ_API_KEY in .env.")

    client = Groq(api_key=resolved_key)

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(intent, ensure_ascii=False)}
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()

    return json.loads(raw)