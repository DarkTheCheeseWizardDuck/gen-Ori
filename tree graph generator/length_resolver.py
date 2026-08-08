"""
Length Resolver
================
Sits on both sides of TAN. Neither function is ML -- both are pure, deterministic
bookkeeping, same category as segment-count validation.

    raw upstream JSON
          |
          |-- strip_for_tan() -----------------> TAN's actual model input
          |                                          |
          |                                     (parent_id, endpoint) per part
          |                                          |
          `-- merge_tan_output() <-------------------'
                     |
                     v
          Tree Adapter's expected input shape
          {part_id, parent_id, endpoint, length, side, order_index}
"""

from __future__ import annotations

FLOOR = 0.03          # prevents a very minor part's length from collapsing near zero
TOTAL_SCALE = 1.0     # calibrate against the real tiling database's typical tree scale


def strip_for_tan(raw_parts: list[dict]) -> list[dict]:
    """
    What TAN actually reads. Drops length_weight and anything from `intent`
    entirely -- TAN never sees them, not even as fields it's trained to ignore.
    """
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "segment_index": p.get("segment_index"),
            "symmetry": p.get("symmetry"),
        }
        for p in raw_parts
    ]


def resolve_lengths(raw_parts: list[dict], floor: float = FLOOR, total_scale: float = TOTAL_SCALE) -> dict[str, float]:
    """length_weight -> length, normalized against the object's own total weight."""
    total_weight = sum(p["length_weight"] for p in raw_parts)
    if total_weight <= 0:
        raise ValueError("Sum of length_weight must be positive.")
    return {
        p["id"]: max(p["length_weight"] / total_weight, floor) * total_scale
        for p in raw_parts
    }


def merge_tan_output(tan_output: list[dict], raw_parts: list[dict]) -> list[dict]:
    """
    tan_output: [{"part_id", "parent_id", "endpoint"}, ...] -- TAN's prediction
    raw_parts:  the original upstream parts list (has length_weight + symmetry.side)

    Returns exactly the shape Tree Adapter's build_tree_payload expects.
    """
    lengths = resolve_lengths(raw_parts)
    side_by_id = {p["id"]: (p.get("symmetry") or {}).get("side") for p in raw_parts}
    order_by_id = {p["id"]: (p.get("symmetry") or {}).get("order_index") for p in raw_parts}

    return [
        {
            "part_id": t["part_id"],
            "parent_id": t["parent_id"],
            "endpoint": t["endpoint"],
            "length": lengths[t["part_id"]],
            "side": side_by_id.get(t["part_id"]),
            "order_index": order_by_id.get(t["part_id"]),
        }
        for t in tan_output
    ]
