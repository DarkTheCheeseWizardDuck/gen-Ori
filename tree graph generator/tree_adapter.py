"""
Tree Adapter
============

Bridges TAN's structural output to the exact wire format SEARCH-22.5's
interface/server.py expects at POST /api/query.

INPUT CONTRACT (what this module expects to receive)
------------------------------------------------------
A flat list of parts, each already carrying:
    - part_id   : str, unique
    - parent_id : str or None (exactly one part has parent_id=None -> the root)
    - endpoint  : "base" | "tip" | None (None only for the root)
    - length    : float > 0 (already computed upstream from length_weight
                  via your external length formula -- NOT predicted by TAN)
    - side      : optional, "left" | "right" | "center" | None
                  (purely a layout hint for nicer fan-out; has no effect
                  on connectivity or on the HKT shape-matching math)
    - order_index: optional int, used to keep sibling ordering stable

This is TAN's { part_id, parent_id, endpoint } output, merged with the
external length step -- this module does not compute or predict either.

OUTPUT CONTRACT (verified against interface/server.py::_build_query_graph)
------------------------------------------------------------------------
    {
      "tree": {
        "nodes": [{"id": int, "x": float, "y": float}, ...],
        "edges": [{"u": int, "v": int, "length": float}, ...]
      }
    }

Notes pulled directly from reading server.py, not assumed:
    - node "id" must be castable to int -> we mint fresh integer vertex ids.
    - "x" and "y" are read unconditionally when building edges (even if
      "length" is also supplied), so real coordinates are REQUIRED, not
      optional metadata. This module runs a deterministic layout pass to
      produce them.
    - the actual shape-matching math (extract_eigenvalues in tree.py) only
      touches the "weight" edge attribute (1/length), never x/y -- so layout
      quality does not affect retrieval quality, it only has to be valid.
    - the server independently checks nx.is_connected() and 400s if not;
      we replicate that check locally so a bad input fails fast.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Part:
    part_id: str
    parent_id: Optional[str]
    endpoint: Optional[str]     # "base" | "tip" | None (root only)
    length: float
    side: Optional[str] = None          # "left" | "right" | "center" | None
    order_index: Optional[int] = None


class TreeAdapterError(ValueError):
    """Raised when the input part list is malformed or produces an invalid graph."""


# ---------------------------------------------------------------------------
# Step 1: validate + index the input
# ---------------------------------------------------------------------------

def _load_parts(raw_parts: list[dict]) -> list[Part]:
    parts = []
    for p in raw_parts:
        if "part_id" not in p or "length" not in p:
            raise TreeAdapterError(f"Part missing required field(s): {p}")
        if p.get("length", 0) <= 0:
            raise TreeAdapterError(f"Part '{p['part_id']}' has non-positive length: {p.get('length')}")
        parts.append(Part(
            part_id=p["part_id"],
            parent_id=p.get("parent_id"),
            endpoint=p.get("endpoint"),
            length=float(p["length"]),
            side=p.get("side"),
            order_index=p.get("order_index"),
        ))
    return parts


def _find_root(parts: list[Part]) -> Part:
    roots = [p for p in parts if p.parent_id is None]
    if len(roots) != 1:
        raise TreeAdapterError(f"Expected exactly one root part (parent_id=None), found {len(roots)}")
    return roots[0]


def _group_children(parts: list[Part]) -> dict[tuple[str, str], list[Part]]:
    """Map (parent_id, endpoint) -> children attaching there, in stable sorted order."""
    groups: dict[tuple[str, str], list[Part]] = {}
    for p in parts:
        if p.parent_id is None:
            continue
        if p.endpoint not in ("base", "tip"):
            raise TreeAdapterError(f"Part '{p.part_id}' has invalid endpoint: {p.endpoint!r}")
        groups.setdefault((p.parent_id, p.endpoint), []).append(p)

    _SIDE_RANK = {"left": -1, "center": 0, "right": 1, None: 0}
    for key, children in groups.items():
        children.sort(key=lambda c: (_SIDE_RANK.get(c.side, 0), c.order_index if c.order_index is not None else 0, c.part_id))
    return groups


# ---------------------------------------------------------------------------
# Step 2: fan-out angles for siblings sharing one attachment vertex
# ---------------------------------------------------------------------------

def _fan_angles(center_deg: float, n: int, spread_deg: float) -> list[float]:
    """n directions spread evenly around center_deg. A single child continues straight."""
    if n == 1:
        return [center_deg]
    start = center_deg - spread_deg / 2.0
    step = spread_deg / (n - 1)
    return [start + i * step for i in range(n)]


def _direction(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return (math.cos(rad), math.sin(rad))


# ---------------------------------------------------------------------------
# Step 3: fuse per-part edges into one connected graph + deterministic layout
# ---------------------------------------------------------------------------

def _build(raw_parts: list[dict], root_direction_deg: float, fan_spread_deg: float):
    """Shared core: returns (nodes, edge_payload, edge_part_ids), all index-aligned."""
    parts = _load_parts(raw_parts)
    root = _find_root(parts)
    children_by_attach = _group_children(parts)

    vertex_pos: dict[int, tuple[float, float]] = {}
    edges: list[tuple[int, int, float]] = []
    edge_part_ids: list[str] = []
    _next_id = [0]

    def new_vertex(pos: tuple[float, float]) -> int:
        vid = _next_id[0]
        _next_id[0] += 1
        vertex_pos[vid] = pos
        return vid

    def place(part: Part, base_vertex_id: int, base_pos: tuple[float, float], direction_deg: float) -> None:
        dx, dy = _direction(direction_deg)
        tip_pos = (base_pos[0] + part.length * dx, base_pos[1] + part.length * dy)
        tip_vertex_id = new_vertex(tip_pos)
        edges.append((base_vertex_id, tip_vertex_id, part.length))
        edge_part_ids.append(part.part_id)

        for endpoint, vid, vpos, arc_center in (
            ("base", base_vertex_id, base_pos, direction_deg + 180.0),
            ("tip", tip_vertex_id, tip_pos, direction_deg),
        ):
            kids = children_by_attach.get((part.part_id, endpoint), [])
            if not kids:
                continue
            angles = _fan_angles(arc_center, len(kids), fan_spread_deg)
            for child, ang in zip(kids, angles):
                place(child, vid, vpos, ang)

    root_base_id = new_vertex((0.0, 0.0))
    place(root, root_base_id, (0.0, 0.0), root_direction_deg)

    nodes = [{"id": vid, "x": x, "y": y} for vid, (x, y) in vertex_pos.items()]
    edge_payload = [{"u": u, "v": v, "length": length} for u, v, length in edges]
    return nodes, edge_payload, edge_part_ids


def build_tree_payload(
    raw_parts: list[dict],
    root_direction_deg: float = 90.0,
    fan_spread_deg: float = 150.0,
) -> dict:
    """
    Fuses TAN's (part_id, parent_id, endpoint, length) structure into one
    connected weighted tree and lays it out in 2D, returning the payload
    ready to POST as-is to /api/query. Unchanged from before -- same
    signature, same output shape.
    """
    nodes, edge_payload, _ = _build(raw_parts, root_direction_deg, fan_spread_deg)
    return {"tree": {"nodes": nodes, "edges": edge_payload}}


def build_tree_payload_with_parts(
    raw_parts: list[dict],
    root_direction_deg: float = 90.0,
    fan_spread_deg: float = 150.0,
) -> tuple[dict, list[str]]:
    """
    Same as build_tree_payload, but also returns edge_part_ids: a list
    aligned with payload["tree"]["edges"], giving the part_id each edge
    came from. For debug_view.py -- so it can reuse this exact layout
    (the same one the PNG and the engine payload use) instead of computing
    its own.
    """
    nodes, edge_payload, edge_part_ids = _build(raw_parts, root_direction_deg, fan_spread_deg)
    return {"tree": {"nodes": nodes, "edges": edge_payload}}, edge_part_ids


# ---------------------------------------------------------------------------
# Step 4: local sanity check, mirroring the server's own validation
# ---------------------------------------------------------------------------

def validate_connected(payload: dict) -> None:
    g = nx.Graph()
    for n in payload["tree"]["nodes"]:
        g.add_node(n["id"])
    for e in payload["tree"]["edges"]:
        g.add_edge(e["u"], e["v"])
    if g.number_of_nodes() == 0 or not nx.is_connected(g):
        raise TreeAdapterError("Resulting graph is disconnected -- check parent_id references in the input parts.")


# ---------------------------------------------------------------------------
# Step 5 (optional): send to a locally running server
# ---------------------------------------------------------------------------

def query_local_server(payload: dict, n: int = 5, host: str = "127.0.0.1", port: int = 8000, token: str | None = None) -> dict:
    """Convenience wrapper for calling a locally running interface/server.py. Requires `requests`."""
    import json
    import urllib.request

    body = dict(payload)
    body["n"] = n
    req = urllib.request.Request(
        f"http://{host}:{port}/api/query",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **({"X-Interface-Token": token} if token else {})},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Self-test: hand-built quadruped, no TAN required
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    example_parts = [
        {"part_id": "body_01", "parent_id": None, "endpoint": None, "length": 2.2},
        {"part_id": "head_01", "parent_id": "body_01", "endpoint": "tip", "length": 0.9},
        {"part_id": "ear_01", "parent_id": "head_01", "endpoint": "tip", "length": 0.35, "side": "left"},
        {"part_id": "ear_02", "parent_id": "head_01", "endpoint": "tip", "length": 0.35, "side": "right"},
        {"part_id": "tail_01", "parent_id": "body_01", "endpoint": "tip", "length": 1.1},
        {"part_id": "front_leg_01", "parent_id": "body_01", "endpoint": "base", "length": 1.3, "side": "left", "order_index": 1},
        {"part_id": "front_leg_02", "parent_id": "body_01", "endpoint": "base", "length": 1.3, "side": "right", "order_index": 1},
        {"part_id": "hind_leg_01", "parent_id": "body_01", "endpoint": "base", "length": 1.3, "side": "left", "order_index": 2},
        {"part_id": "hind_leg_02", "parent_id": "body_01", "endpoint": "base", "length": 1.3, "side": "right", "order_index": 2},
    ]

    payload = build_tree_payload(example_parts)
    validate_connected(payload)

    print(f"nodes: {len(payload['tree']['nodes'])}, edges: {len(payload['tree']['edges'])}")
    import json
    print(json.dumps(payload, indent=2))

    try:
        result = query_local_server(payload)
        print("Server responded with", len(result.get("results", [])), "results")
    except Exception as e:
        print(f"(skipping live server query -- {e})")