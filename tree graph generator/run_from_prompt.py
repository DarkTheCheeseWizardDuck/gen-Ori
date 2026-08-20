"""
The actual end-to-end loop: a natural language request goes in one end,
a rendered tree comes out the other.

    user input -> structure/pipeline.py::run_pipeline() [UNCHANGED, imported as-is]
               -> strip_for_tan() -> trained TAN -> Chu-Liu/Edmonds decode
               -> merge_tan_output() [puts length_weight-derived lengths back]
               -> tree_adapter.build_tree_payload() -> validate_connected()
               -> rendered to renders/from_prompt/<object>.png

Requires tan_checkpoint.pt to already exist -- run run_pipeline.py at least
once first to produce it.

Usage:
    python run_from_prompt.py                      (interactive, asks for input)
    python run_from_prompt.py "a reindeer with antlers and four legs"   (one-shot)
"""

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
STRUCTURE_DIR = CURRENT_DIR.parent / "structure"
sys.path.insert(0, str(STRUCTURE_DIR))   # so `from pipeline import run_pipeline` resolves
sys.path.insert(0, str(CURRENT_DIR))     # in case this is invoked from elsewhere

from pipeline import run_pipeline        # structure/pipeline.py -- NOT modified
from predict_from_checkpoint import load_model, CHECKPOINT_PATH
from run_pipeline import render_object
from tan_decode import predict
from length_resolver import merge_tan_output
from tree_adapter import build_tree_payload, validate_connected
from format_upstream import sanitize_filename

RENDER_DIR = CURRENT_DIR / "renders" / "from_prompt"


def run_from_text(user_input: str, model) -> dict:
    upstream_result = run_pipeline(user_input)  # calls the real extractor + length_assign
    print("\n=== Upstream output ===")
    print(json.dumps(upstream_result, indent=2, ensure_ascii=False))

    raw_parts = upstream_result["structure"]["parts"]
    object_name = upstream_result.get("intent", {}).get("object", "unnamed")

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


def main():
    if not CHECKPOINT_PATH.exists():
        print(f"No checkpoint found at {CHECKPOINT_PATH} -- run run_pipeline.py first.")
        sys.exit(1)

    model = load_model()

    user_input = sys.argv[1] if len(sys.argv) > 1 else input("Origami request: ")
    run_from_text(user_input, model)


if __name__ == "__main__":
    main()