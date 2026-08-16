import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

try:
    from .models import StructureV1, StructureValidationError, validate_structure
except ImportError:  # Supports `python structure/extractor.py`.
    from models import StructureV1, StructureValidationError, validate_structure

DEBUG = False
MAX_STRUCTURE_ATTEMPTS = 3

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
# Load canonical schema from Pydantic
# -----------------------------
schema = json.dumps(StructureV1.model_json_schema(), indent=2)

# -----------------------------
# Load prompts
# -----------------------------
try:
    with open(CURRENT_DIR / "prompt.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

except Exception as e:
    raise RuntimeError(f"Failed to load prompt.txt:\n{e}")

system_prompt = prompt_template.replace("{SCHEMA}", schema)

def load_plan_prompt() -> str:
    """Load the optional interactive planning prompt from the current layout."""
    candidates = [CURRENT_DIR / "plan_prompt.txt", ROOT_DIR / "intent" / "plan_prompt.txt"]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    searched = "\n".join(str(path) for path in candidates)
    raise RuntimeError(f"Failed to find plan_prompt.txt. Searched:\n{searched}")


def clean_response(raw: str, expect_json: bool = False) -> str:
    """Helper to clean reasoning blocks and markdown formatting from LLM response."""
    raw = raw.strip()
    if "</think>" in raw:
        raw = raw.split("</think>", 1)[1].strip()

    if expect_json:
        import re

        def sanitize_json(text: str) -> str:
            # Remove single-line comments //...
            text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
            # Remove multi-line comments /*...*/
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
            return text.strip()

        # Try to find all markdown JSON code blocks first
        code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        for block in code_blocks:
            sanitized = sanitize_json(block)
            try:
                json.loads(sanitized)
                return sanitized
            except json.JSONDecodeError:
                pass

        # Fall back to matching outermost braces of the whole string
        first_brace = raw.find('{')
        last_brace = raw.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = raw[first_brace:last_brace+1]
            sanitized = sanitize_json(candidate)
            try:
                json.loads(sanitized)
                return sanitized
            except json.JSONDecodeError:
                pass

    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def _decode_structure_response(raw: str) -> dict:
    """Parse and validate one LLM response as a structure.v1 document."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StructureValidationError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return validate_structure(payload)


def request_valid_structure(messages: list[dict]) -> dict:
    """Request structure JSON, repairing schema failures at most twice."""
    conversation = list(messages)
    last_error: StructureValidationError | None = None
    last_raw = ""

    for attempt in range(1, MAX_STRUCTURE_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=conversation,
                temperature=0.2,
                max_tokens=4096,
            )
        except Exception as error:
            raise RuntimeError(f"Groq API call failed on attempt {attempt}:\n{error}") from error

        last_raw = clean_response(response.choices[0].message.content, expect_json=True)

        if DEBUG:
            print(f"\n===== RAW RESPONSE (attempt {attempt}) =====")
            print(last_raw)
            print("==========================================\n")

        try:
            return _decode_structure_response(last_raw)
        except StructureValidationError as error:
            last_error = error
            if attempt == MAX_STRUCTURE_ATTEMPTS:
                break

            conversation.extend(
                [
                    {"role": "assistant", "content": last_raw},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was rejected. Return a complete replacement "
                            "that is ONLY valid JSON matching genori.structure.v1. Do not explain "
                            "or use markdown. Validation error: " + str(error)
                        ),
                    },
                ]
            )

    raise RuntimeError(
        f"LLM returned an invalid genori.structure.v1 document after "
        f"{MAX_STRUCTURE_ATTEMPTS} attempts. Last validation error: {last_error}\n\n"
        f"Last response:\n{last_raw}"
    ) from last_error


# ==========================================================
# Main extraction function
# ==========================================================
def extract_structure(user_input: str) -> dict:
    """Extract structure from a natural language request."""
    return request_valid_structure(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    )


def generate_plan(user_input: str, history: list = None) -> tuple[str, list]:
    """Propose or update the structural plan based on user feedback."""
    if history is None or len(history) == 0:
        history = [
            {"role": "system", "content": load_plan_prompt()},
            {"role": "user", "content": user_input}
        ]
    else:
        history.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=history,
            temperature=0.2,
            max_tokens=4096
        )
    except Exception as e:
        raise RuntimeError(f"Groq API call failed:\n{e}")

    raw = clean_response(response.choices[0].message.content)
    history.append({"role": "assistant", "content": raw})
    return raw, history


def convert_plan_to_json(approved_plan: str) -> dict:
    """Convert the final approved plan to JSON matching the schema."""
    return request_valid_structure(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Based on the following approved plan, generate the final structured JSON:\n\n{approved_plan}",
            },
        ]
    )


def main():
    """Run extraction directly from this module with interactive planning."""
    user_input = input("Origami request: ")

    print("\nProposing structure plan...")
    plan, history = generate_plan(user_input)

    while True:
        print("\n" + "=" * 40)
        print(plan)
        print("=" * 40 + "\n")

        feedback = input("Do you want to adjust the plan? Enter your feedback, or type 'yes' to approve: ").strip()

        if feedback.lower() in ["yes", "y", "approve"]:
            break
        elif not feedback:
            print("Please enter feedback or type 'yes' to approve.")
            continue

        print("\nUpdating structure plan...")
        plan, history = generate_plan(feedback, history)

    print("\nGenerating final structure JSON...")
    structure = convert_plan_to_json(plan)

    print("\nExtracted structure:\n")
    print(json.dumps(structure, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
