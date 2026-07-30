"""
Upstream pipeline: natural language -> structure (extractor.py) -> length_weight (length_assign.py)

Run this instead of extractor.py directly.
"""

import json

from extractor import extract_intent
from length_assign import assign_length_weights


def run_pipeline(user_input: str) -> dict:
    intent = extract_intent(user_input)
    intent = assign_length_weights(intent)  # overwrite with the length-filled version
    return intent


def main():
    user_input = input("Origami request: ")

    result = run_pipeline(user_input)

    print("\nFinal Intent:\n")
    print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
