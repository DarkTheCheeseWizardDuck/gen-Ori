"""
Run this to go from dataset/ all the way to pictures.

For every object in dataset/:
    predict() -> merge_tan_output() -> build_tree_payload() -> validate_connected()
    -> saved as renders/png/<object>.png (quick skim, real engine-style layout)
    -> saved as renders/html/<object>.html (hover-to-inspect, rigid, base=left/tip=right)

Also saves the trained model to tan_checkpoint.pt so you don't have to
retrain from scratch just to look at output again later.
"""

from pathlib import Path
import json

import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from load_dataset import load_dataset
from tan_model import TANModel, build_group_vocab, build_name_vocab
from name_encoder import LearnedNameEncoder
from tan_train import train, evaluate
from tan_decode import predict
from length_resolver import merge_tan_output
from tree_adapter import build_tree_payload_with_parts, validate_connected, TreeAdapterError
from debug_view import render_html, build_index_html

CURRENT_DIR = Path(__file__).resolve().parent
DATASET_DIR = CURRENT_DIR / "dataset"
RENDER_DIR = CURRENT_DIR / "renders"
PNG_DIR = RENDER_DIR / "png"
HTML_DIR = RENDER_DIR / "html"
CHECKPOINT_PATH = CURRENT_DIR / "tan_checkpoint.pt"


def render_object(model, obj: dict, png_path: Path, html_path: Path) -> tuple[bool, str]:
    """Renders both the PNG (engine-style layout) and the HTML debug view. Returns (ok, message)."""
    try:
        tan_output = predict(model, obj["raw_parts"])
        merged = merge_tan_output(tan_output, obj["raw_parts"])
        payload, edge_part_ids = build_tree_payload_with_parts(merged, root_direction_deg=0.0)
        validate_connected(payload)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

    nodes = {n["id"]: (n["x"], n["y"]) for n in payload["tree"]["nodes"]}
    fig, ax = plt.subplots(figsize=(6, 5))
    for e in payload["tree"]["edges"]:
        x1, y1 = nodes[e["u"]]
        x2, y2 = nodes[e["v"]]
        ax.plot([x1, x2], [y1, y2], color="#1C2541", linewidth=2)
    xs = [p[0] for p in nodes.values()]
    ys = [p[1] for p in nodes.values()]
    ax.scatter(xs, ys, color="#E8871E", zorder=5, s=35)
    ax.set_title(obj["name"], fontsize=12)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.savefig(png_path, dpi=130, bbox_inches="tight")
    plt.close(fig)

    render_html(obj["name"], obj["raw_parts"], payload, edge_part_ids, html_path)

    return True, "ok"


def main():
    dataset = load_dataset(str(DATASET_DIR))
    print(f"Loaded {len(dataset)} objects from {DATASET_DIR}\n")

    name_vocab = build_name_vocab(dataset)
    group_vocab = build_group_vocab(dataset)
    model = TANModel(LearnedNameEncoder(name_vocab), group_vocab)

    train(model, dataset)

    torch.save({
        "model_state": model.state_dict(),
        "name_vocab": name_vocab,
        "group_vocab": group_vocab,
    }, CHECKPOINT_PATH)
    print(f"\nSaved trained model to {CHECKPOINT_PATH}")

    print("\n=== Exact-match evaluation ===")
    eval_results = evaluate(model, dataset)
    exact_matches = 0
    for name, (correct, total) in eval_results.items():
        flag = "" if correct == total else "  <-- not exact"
        print(f"{name:20s}  {correct}/{total}{flag}")
        if correct == total:
            exact_matches += 1
    print(f"\n{exact_matches}/{len(dataset)} objects fully correct")

    print("\n=== Rendering every object (PNG + interactive HTML) ===")
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    ok_count, fail_count = 0, 0
    rendered_names = []
    for obj in dataset:
        png_path = PNG_DIR / f"{obj['name']}.png"
        html_path = HTML_DIR / f"{obj['name']}.html"
        ok, msg = render_object(model, obj, png_path, html_path)
        if ok:
            ok_count += 1
            rendered_names.append(obj["name"])
            print(f"[ok]   {obj['name']:20s} -> png/{obj['name']}.png, html/{obj['name']}.html")
        else:
            fail_count += 1
            print(f"[FAIL] {obj['name']:20s} {msg}")

    build_index_html(rendered_names, HTML_DIR / "index.html")

    print("\n========================================")
    print(f"Rendered: {ok_count}   Failed: {fail_count}")
    print(f"Quick skim:       {PNG_DIR}")
    print(f"Detailed inspect: {HTML_DIR / 'index.html'}  (open in a browser, hover any edge)")
    print("========================================")


if __name__ == "__main__":
    main()