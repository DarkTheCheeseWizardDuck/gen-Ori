"""
Tests the "unpaired parts fail more" and "parts under head fail more"
hypotheses with real numbers instead of guessing from a handful of examples.

Run this after run_pipeline.py (needs tan_checkpoint.pt).
"""

from pathlib import Path
import torch

from load_dataset import load_dataset
from tan_model import TANModel
from name_encoder import LearnedNameEncoder
from tan_decode import predict

CURRENT_DIR = Path(__file__).resolve().parent
CHECKPOINT_PATH = CURRENT_DIR / "tan_checkpoint.pt"
DATASET_DIR = CURRENT_DIR / "dataset"


def main():
    ckpt = torch.load(CHECKPOINT_PATH, weights_only=False)
    model = TANModel(LearnedNameEncoder(ckpt["name_vocab"]), ckpt["group_vocab"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    dataset = load_dataset(str(DATASET_DIR))

    buckets = {
        "paired (has symmetry)": [0, 0],
        "unpaired (no symmetry)": [0, 0],
        "parent is named 'head'": [0, 0],
        "parent is NOT named 'head'": [0, 0],
    }
    mistakes = []

    for obj in dataset:
        raw_by_id = {p["id"]: p for p in obj["raw_parts"]}
        gt_by_id = {g["part_id"]: g for g in obj["ground_truth"]}
        pred = predict(model, obj["raw_parts"])

        for p in pred:
            gt = gt_by_id[p["part_id"]]
            if gt["parent_id"] is None:
                continue  # root has nothing to get wrong
            correct = (p["parent_id"] == gt["parent_id"] and p["endpoint"] == gt["endpoint"])

            raw = raw_by_id[p["part_id"]]
            is_paired = raw.get("symmetry") is not None
            bucket_key = "paired (has symmetry)" if is_paired else "unpaired (no symmetry)"
            buckets[bucket_key][0] += correct
            buckets[bucket_key][1] += 1

            parent_name = raw_by_id.get(gt["parent_id"], {}).get("name")
            head_key = "parent is named 'head'" if parent_name == "head" else "parent is NOT named 'head'"
            buckets[head_key][0] += correct
            buckets[head_key][1] += 1

            if not correct:
                mistakes.append(
                    f"{obj['name']:20s} {p['part_id']:15s} "
                    f"predicted=({p['parent_id']}, {p['endpoint']})  "
                    f"true=({gt['parent_id']}, {gt['endpoint']})"
                )

    print("=== Accuracy by category ===")
    for k, (correct, total) in buckets.items():
        pct = 100 * correct / total if total else 0
        print(f"{k:28s}  {correct:4d}/{total:<4d}  ({pct:.1f}%)")

    print(f"\n=== All {len(mistakes)} individual mistakes ===")
    for m in mistakes:
        print(m)


if __name__ == "__main__":
    main()
