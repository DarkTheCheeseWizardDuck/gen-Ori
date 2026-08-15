"""
Batch version of the upstream -> dataset converter.

Instead of converting one upstream JSON at a time, this scans
results/structure/*_outputs.json (the files evaluate.py already produces),
lets you pick one from a menu (same style as evaluate.py's own benchmark
picker), and writes one dataset/<object>.json per test case -- skipping
error entries, and disambiguating by test-case id if the same object name
shows up more than once in a single batch (this does happen -- e.g. two
separate "european dragon" test cases in one run).

ground_truth is still left empty on purpose -- that's yours to author.
"""

import json
import re
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent

RESULT_DIR = ROOT_DIR / "results" / "structure"
DATASET_DIR = CURRENT_DIR / "dataset"


def format_part(part: dict) -> str:
    return json.dumps(part, separators=(", ", ": "))


def format_parts_block(parts: list[dict], indent: int = 4) -> str:
    pad = " " * indent
    lines = [format_part(p) for p in parts]
    body = (",\n" + pad).join(lines)
    return f"[\n{pad}{body}\n" + " " * (indent - 2) + "]"


def convert(parts: list[dict]) -> str:
    parts_block = format_parts_block(parts, indent=4)
    return (
        "{\n"
        f'  "raw_parts": {parts_block},\n'
        '  "ground_truth": []\n'
        "}\n"
    )


def sanitize_filename(name: str) -> str:
    name = name.strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", name)


def pick_result_file() -> Path:
    result_files = sorted(RESULT_DIR.glob("*_outputs.json"))
    if not result_files:
        raise RuntimeError(f"No result files found in:\n{RESULT_DIR}")

    print("Available result files:\n")
    for i, file in enumerate(result_files, start=1):
        print(f"[{i}] {file.stem}")

    while True:
        choice = input("\nSelect result file: ")
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(result_files):
                return result_files[index]
        else:
            for file in result_files:
                stem = file.stem
                short = stem.removesuffix("_outputs")
                if choice.lower() in (stem.lower(), short.lower()):
                    return file
        print("Invalid selection. Please try again.")


def main():
    result_path = pick_result_file()
    with open(result_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"\nConverting: {result_path.stem}")
    print(f"Total test cases: {len(test_cases)}\n")

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    written, skipped_errors, collisions = 0, 0, 0
    seen_names: dict[str, int] = {}  # sanitized name -> count so far, this run

    for tc in test_cases:
        output = tc["output"]
        if "error" in output:
            print(f"[skip]  {tc['id']}: upstream returned an error -- {output['error'][:80]}")
            skipped_errors += 1
            continue

        object_name = output.get("intent", {}).get("object", tc["id"])
        base_name = sanitize_filename(object_name)
        parts = output["structure"]["parts"]

        out_path = DATASET_DIR / f"{base_name}.json"
        seen_names[base_name] = seen_names.get(base_name, 0) + 1

        if out_path.exists() or seen_names[base_name] > 1:
            out_path = DATASET_DIR / f"{base_name}_{tc['id']}.json"
            collisions += 1
            print(f"[collision] '{object_name}' already used -- writing {out_path.name} instead")

        out_path.write_text(convert(parts), encoding="utf-8")
        print(f"[write] {tc['id']} -> {out_path.relative_to(ROOT_DIR)}")
        written += 1

    print("\n========================================")
    print(f"Written:  {written}")
    print(f"Skipped (errors): {skipped_errors}")
    print(f"Collisions handled: {collisions}")
    print("ground_truth is empty in every new file -- fill it in by hand.")
    print("========================================")


if __name__ == "__main__":
    main()
