"""
Single entry point for turning either a live natural-language request OR an
existing raw_parts-only JSON file into a rendered tree.

    "a reindeer with antlers..." -> structure/pipeline.py::run_pipeline()
                                     [UNCHANGED, imported as-is]  -> ...
    dataset/some_object.json    -> read raw_parts directly, skip upstream   -> ...
                                     |
                                     v
    ...  -> strip_for_tan() -> trained TAN -> Chu-Liu/Edmonds decode
         -> merge_tan_output() [puts length_weight-derived lengths back]
         -> tree_adapter.build_tree_payload() -> validate_connected()
         -> rendered to renders/from_prompt/<object>.{png,html}

Requires tan_checkpoint.pt to already exist -- run run_pipeline.py at least
once first to produce it.

Usage:
    python run_from_prompt.py                                       (interactive)
    python run_from_prompt.py "a reindeer with antlers and four legs"  (live NL request)
    python run_from_prompt.py dataset/some_object.json               (predict from an existing file, no API call)
"""

import sys
import json
from pathlib import Path

import torch

CURRENT_DIR = Path(__file__).resolve().parent
STRUCTURE_DIR = CURRENT_DIR.parent / "structure"
sys.path.insert(0, str(STRUCTURE_DIR))   # so `from pipeline import run_pipeline` resolves
sys.path.insert(0, str(CURRENT_DIR))     # in case this is invoked from elsewhere

from pipeline import run_pipeline        # structure/pipeline.py -- NOT modified
from tan_model import TANModel
from name_encoder import LearnedNameEncoder
from run_pipeline import render_object
from tan_decode import predict
from length_resolver import merge_tan_output
from tree_adapter import build_tree_payload, validate_connected
from format_upstream import sanitize_filename

CHECKPOINT_PATH = CURRENT_DIR / "tan_checkpoint.pt"
RENDER_DIR = CURRENT_DIR / "renders" / "from_prompt"


def load_model() -> TANModel:
    ckpt = torch.load(CHECKPOINT_PATH, weights_only=False)
    name_encoder = LearnedNameEncoder(ckpt["name_vocab"])
    model = TANModel(name_encoder, ckpt["group_vocab"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model


def run_from_raw_parts(raw_parts: list[dict], object_name: str, model) -> dict:
    """Shared by both entry points: predict, merge, render. No upstream call here."""
    tan_output = predict(model, raw_parts)
    print("\n=== TAN's predicted structure ===")
    print(json.dumps(tan_output, indent=2))

    merged = merge_tan_output(tan_output, raw_parts)
    payload = build_tree_payload(merged, root_direction_deg=0.0)
    validate_connected(payload)

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    png_path = RENDER_DIR / f"{sanitize_filename(object_name)}.png"
    html_path = RENDER_DIR / f"{sanitize_filename(object_name)}.html"
    ok, msg = render_object(model, {"name": object_name, "raw_parts": raw_parts}, png_path, html_path)
    if ok:
        print(f"\nRendered -> {png_path.relative_to(CURRENT_DIR)}, {html_path.relative_to(CURRENT_DIR)}")
    else:
        print(f"\n[FAIL] rendering: {msg}")

    return payload


def run_from_text(user_input: str, model) -> dict:
    upstream_result = run_pipeline(user_input)  # calls the real extractor + length_assign
    print("\n=== Upstream output ===")
    print(json.dumps(upstream_result, indent=2, ensure_ascii=False))

    raw_parts = upstream_result["structure"]["parts"]
    object_name = upstream_result.get("intent", {}).get("object", "unnamed")
    return run_from_raw_parts(raw_parts, object_name, model)


def run_from_file(path: Path, model) -> dict:
    with open(path, encoding="utf-8") as f:
        raw_parts = json.load(f)["raw_parts"]
    return run_from_raw_parts(raw_parts, path.stem, model)


def main():
    if not CHECKPOINT_PATH.exists():
        print(f"No checkpoint found at {CHECKPOINT_PATH} -- run run_pipeline.py first.")
        sys.exit(1)

    model = load_model()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        candidate = Path(arg)
        if candidate.suffix == ".json" and candidate.exists():
            print(f"Detected an existing JSON file -- predicting directly from its raw_parts (no upstream/API call).")
            run_from_file(candidate, model)
        else:
            run_from_text(arg, model)
    else:
        user_input = input("Origami request: ")
        run_from_text(user_input, model)


if __name__ == "__main__":
    main()