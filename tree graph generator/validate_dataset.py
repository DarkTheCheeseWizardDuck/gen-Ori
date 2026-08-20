"""
Checks every dataset/*.json file for the mistakes that are easy to make by
hand: a ground_truth part_id/parent_id that doesn't exist in raw_parts,
zero or multiple roots, a missing endpoint, a part with no ground_truth
entry at all, or a duplicate id within one file.

Run this BEFORE run_pipeline.py -- it reports every problem across every
file in one pass, instead of training crashing on the first one it hits.
"""

from pathlib import Path
import json

CURRENT_DIR = Path(__file__).resolve().parent
DATASET_DIR = CURRENT_DIR / "dataset"


def validate_file(path: Path) -> list[str]:
    errors = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_parts = data.get("raw_parts", [])
    ground_truth = data.get("ground_truth", [])

    raw_ids = [p["id"] for p in raw_parts]
    raw_id_set = set(raw_ids)
    if len(raw_ids) != len(raw_id_set):
        dupes = {i for i in raw_ids if raw_ids.count(i) > 1}
        errors.append(f"duplicate id(s) in raw_parts: {dupes}")

    gt_ids = [g["part_id"] for g in ground_truth]
    gt_id_set = set(gt_ids)

    missing_gt = raw_id_set - gt_id_set
    if missing_gt:
        errors.append(f"part(s) with no ground_truth entry at all: {missing_gt}")

    extra_gt = gt_id_set - raw_id_set
    if extra_gt:
        errors.append(f"ground_truth part_id(s) not found in raw_parts: {extra_gt}")

    for p in raw_parts:
        lw = p.get("length_weight")
        if lw is None:
            errors.append(f"'{p['id']}': length_weight is null -- upstream didn't fill it in")
        elif not isinstance(lw, (int, float)) or lw <= 0:
            errors.append(f"'{p['id']}': length_weight must be a positive number, got {lw!r}")

    roots = [g for g in ground_truth if g.get("parent_id") is None]
    if len(roots) == 0:
        errors.append("no root found (every entry has a non-null parent_id)")
    elif len(roots) > 1:
        errors.append(f"multiple roots found: {[r['part_id'] for r in roots]}")

    for g in ground_truth:
        pid = g.get("part_id")
        parent = g.get("parent_id")
        endpoint = g.get("endpoint")

        if parent is not None and parent not in raw_id_set:
            errors.append(f"'{pid}': parent_id '{parent}' does not exist in raw_parts")

        if parent is None and endpoint is not None:
            errors.append(f"'{pid}': is root (parent_id=None) but endpoint is '{endpoint}', should be None")
        if parent is not None and endpoint not in ("base", "tip"):
            errors.append(f"'{pid}': endpoint is {endpoint!r}, must be 'base' or 'tip'")

    return errors


def main():
    files = sorted(DATASET_DIR.glob("*.json"))
    if not files:
        print(f"No files found in {DATASET_DIR}")
        return

    total_errors = 0
    for path in files:
        try:
            errors = validate_file(path)
        except Exception as e:
            errors = [f"could not parse file: {e}"]

        if errors:
            print(f"\n[{path.stem}] {len(errors)} problem(s):")
            for e in errors:
                print(f"  - {e}")
            total_errors += len(errors)

    print("\n========================================")
    if total_errors == 0:
        print(f"All {len(files)} files passed.")
    else:
        print(f"{total_errors} problem(s) across {len(files)} files -- fix these before running run_pipeline.py")
    print("========================================")


if __name__ == "__main__":
    main()