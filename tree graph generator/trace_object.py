"""
Traces one object all the way through: predict() -> merge_tan_output() ->
build_tree_payload_with_parts(). Prints every stage so a mismatch between
"what TAN predicted" and "what actually got rendered" is visible directly,
instead of only seeing the final picture.

Usage:
    python trace_object.py anglerfish
"""

import sys
from pathlib import Path
import torch

from load_dataset import load_dataset
from tan_model import TANModel
from name_encoder import LearnedNameEncoder
from tan_decode import predict
from length_resolver import merge_tan_output
from tree_adapter import build_tree_payload_with_parts, validate_connected

CURRENT_DIR = Path(__file__).resolve().parent
CHECKPOINT_PATH = CURRENT_DIR / "tan_checkpoint.pt"
DATASET_DIR = CURRENT_DIR / "dataset"


def main():
    if len(sys.argv) != 2:
        print("Usage: python trace_object.py <object_name>")
        sys.exit(1)
    target = sys.argv[1]

    ckpt = torch.load(CHECKPOINT_PATH, weights_only=False)
    model = TANModel(LearnedNameEncoder(ckpt["name_vocab"]), ckpt["group_vocab"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    dataset = load_dataset(str(DATASET_DIR))
    obj = next((o for o in dataset if o["name"] == target), None)
    if obj is None:
        print(f"'{target}' not found. Available: {[o['name'] for o in dataset]}")
        sys.exit(1)

    name_by_id = {p["id"]: p["name"] for p in obj["raw_parts"]}

    print(f"=== STAGE 1: raw ground_truth for {target} ===")
    for g in obj["ground_truth"]:
        print(f"  {g['part_id']:15s} ({name_by_id.get(g['part_id'],'?'):10s})  parent={g['parent_id']!s:15s} endpoint={g['endpoint']}")

    print(f"\n=== STAGE 2: TAN's raw predict() output ===")
    tan_output = predict(model, obj["raw_parts"])
    for t in tan_output:
        print(f"  {t['part_id']:15s} ({name_by_id.get(t['part_id'],'?'):10s})  parent={t['parent_id']!s:15s} endpoint={t['endpoint']}")

    print(f"\n=== STAGE 3: after merge_tan_output (lengths/side attached) ===")
    merged = merge_tan_output(tan_output, obj["raw_parts"])
    for m in merged:
        print(f"  {m['part_id']:15s}  parent={m['parent_id']!s:15s} endpoint={m['endpoint']!s:6s} length={m['length']:.4f}")

    print(f"\n=== STAGE 4: final rendered edges (what tree_adapter actually built) ===")
    payload, edge_part_ids = build_tree_payload_with_parts(merged, root_direction_deg=0.0)
    nodes = {n["id"]: (n["x"], n["y"]) for n in payload["tree"]["nodes"]}
    for edge, pid in zip(payload["tree"]["edges"], edge_part_ids):
        x1, y1 = nodes[edge["u"]]
        x2, y2 = nodes[edge["v"]]
        print(f"  {pid:15s} ({name_by_id.get(pid,'?'):10s})  vertex {edge['u']}({x1:.2f},{y1:.2f}) -> vertex {edge['v']}({x2:.2f},{y2:.2f})  length={edge['length']:.4f}")

    try:
        validate_connected(payload)
        print("\nGraph is connected: OK")
    except Exception as e:
        print(f"\nGraph connectivity FAILED: {e}")


if __name__ == "__main__":
    main()
