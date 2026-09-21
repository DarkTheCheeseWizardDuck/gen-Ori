"""
Upstream pipeline: natural language -> structure (extractor.py) -> length_weight (length_assign.py)

Run this instead of extractor.py directly.
"""

import json

from extractor import extract_structure
from length_assign import assign_length_weights


def run_pipeline(user_input: str, api_key: str | None = None, model: str | None = None) -> dict:
    structure = extract_structure(user_input, api_key=api_key, model=model)
    structure = assign_length_weights(structure, api_key=api_key, model=model)  # overwrite with the length-filled version
    return structure


def main():
    user_input = input("Origami request: ")

    result = run_pipeline(user_input)

    print("\nFinal Structure:\n")
    print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
