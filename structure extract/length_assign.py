import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL")

with open(CURRENT_DIR / "length_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def assign_length_weights(intent: dict) -> dict:
    """
    Fill the length_weight field for every part.
    """

    response = client.chat.completions.create(
        model=MODEL,
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