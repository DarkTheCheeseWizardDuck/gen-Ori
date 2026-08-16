import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

try:
    from .models import StructureValidationError, validate_length_assignment, validate_structure
except ImportError:  # Supports `python structure/length_assign.py`.
    from models import StructureValidationError, validate_length_assignment, validate_structure


ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL")
MAX_LENGTH_ASSIGNMENT_ATTEMPTS = 3

with open(CURRENT_DIR / "length_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def assign_length_weights(intent: dict) -> dict:
    """
    Fill the length_weight field for every part.
    """
    try:
        from .extractor import clean_response
    except ImportError:  # Supports `python structure/length_assign.py`.
        from extractor import clean_response

    validated_input = validate_structure(intent)

    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(validated_input, ensure_ascii=False)},
    ]
    last_error: StructureValidationError | None = None
    last_raw = ""

    for attempt in range(1, MAX_LENGTH_ASSIGNMENT_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=conversation,
                temperature=0.2,
            )
        except Exception as error:
            raise RuntimeError(f"Groq API call failed on attempt {attempt}:\n{error}") from error

        last_raw = clean_response(response.choices[0].message.content, expect_json=True)

        try:
            candidate = json.loads(last_raw)
            return validate_length_assignment(validated_input, candidate)
        except json.JSONDecodeError as error:
            last_error = StructureValidationError(
                f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
            )
        except StructureValidationError as error:
            last_error = error

        if attempt == MAX_LENGTH_ASSIGNMENT_ATTEMPTS:
            break

        conversation.extend(
            [
                {"role": "assistant", "content": last_raw},
                {
                    "role": "user",
                    "content": (
                        "Your previous response was rejected. Return a complete replacement "
                        "that is ONLY valid JSON. Preserve every semantic field exactly and "
                        "change only length_weight values. Do not explain or use markdown. "
                        "Validation error: " + str(last_error)
                    ),
                },
            ]
        )

    raise RuntimeError(
        f"LLM returned an invalid length assignment after "
        f"{MAX_LENGTH_ASSIGNMENT_ATTEMPTS} attempts. Last validation error: {last_error}\n\n"
        f"Last response:\n{last_raw}"
    ) from last_error
