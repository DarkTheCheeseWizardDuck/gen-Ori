"""
Upstream pipeline: natural language -> structure (extractor.py) -> length_weight (length_assign.py)

Run this instead of extractor.py directly.
"""

import json

try:
    from .extractor import extract_structure, generate_plan, convert_plan_to_json
    from .length_assign import assign_length_weights
except ImportError:  # Supports `python structure/pipeline.py`.
    from extractor import extract_structure, generate_plan, convert_plan_to_json
    from length_assign import assign_length_weights


def run_pipeline(user_input: str) -> dict:
    structure = extract_structure(user_input)
    structure = assign_length_weights(structure)  # overwrite with the length-filled version
    return structure


def main():
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

    print("\nAssigning length weights...")
    structure = assign_length_weights(structure)

    print("\nFinal Structure:\n")
    print(json.dumps(structure, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
