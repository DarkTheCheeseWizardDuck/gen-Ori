"""
Decoding: turns raw model scores into a guaranteed-valid tree.

Two upgrades over the toy version's naive per-part argmax:
  1. Chu-Liu/Edmonds (via networkx's maximum_spanning_arborescence) -- guarantees
     exactly one root and zero cycles, by construction, rather than hoping
     independent per-part choices happen to form a valid tree.
  2. Symmetry-consistent decoding -- mirrored parts (same symmetry.group) are
     forced to share one (parent, endpoint) decision, using a stable
     representative, rather than risking each sibling being decided
     independently and disagreeing.
"""

from __future__ import annotations
import torch
import networkx as nx

from length_resolver import strip_for_tan

ROOT = "__ROOT__"


def chu_liu_edmonds_parents(scores: torch.Tensor, part_ids: list[str]) -> dict[str, str | None]:
    """
    scores: (n, n+1) tensor, scores[child_i, candidate] where candidate in
    [0..n-1] are real parts and column n is ROOT.
    Returns {part_id: parent_id_or_None}, guaranteed a single valid tree.
    """
    n = len(part_ids)
    scores_np = scores.detach().numpy()

    g = nx.DiGraph()
    g.add_node(ROOT)
    for pid in part_ids:
        g.add_node(pid)

    for child_i in range(n):
        g.add_edge(ROOT, part_ids[child_i], weight=float(scores_np[child_i, n]))
        for parent_i in range(n):
            if parent_i == child_i:
                continue
            g.add_edge(part_ids[parent_i], part_ids[child_i], weight=float(scores_np[child_i, parent_i]))

    arb = nx.maximum_spanning_arborescence(g, attr="weight")

    parent_of: dict[str, str | None] = {}
    for pid in part_ids:
        preds = list(arb.predecessors(pid))
        parent_of[pid] = None if (not preds or preds[0] == ROOT) else preds[0]
    return parent_of


def _symmetry_groups(raw_parts: list[dict]) -> dict[tuple, list[str]]:
    """{(group_name, order_index): [part_id, ...]} -- keyed on BOTH group and
    order_index, since parts sharing a group name but different order_index
    (e.g. leg_1 vs leg_2) are different attachment points, not mirror pairs
    of each other. Only true mirror pairs (same group AND order_index,
    opposite side) should be forced to agree."""
    groups: dict[tuple, list[str]] = {}
    for p in raw_parts:
        sym = p.get("symmetry")
        if sym:
            key = (sym["group"], sym.get("order_index"))
            groups.setdefault(key, []).append(p["id"])
    for members in groups.values():
        members.sort()  # stable, deterministic representative choice
    return groups


def enforce_symmetry_consistency(tan_output: list[dict], raw_parts: list[dict]) -> list[dict]:
    """Forces every member of a symmetry group to share the representative's (parent, endpoint)."""
    groups = _symmetry_groups(raw_parts)
    by_id = {t["part_id"]: t for t in tan_output}

    for members in groups.values():
        if len(members) < 2:
            continue
        rep = by_id[members[0]]
        for pid in members[1:]:
            by_id[pid]["parent_id"] = rep["parent_id"]
            by_id[pid]["endpoint"] = rep["endpoint"]

    return list(by_id.values())


@torch.no_grad()
def predict(model, raw_parts: list[dict]) -> list[dict]:
    model.eval()
    tan_input = strip_for_tan(raw_parts)
    part_ids = [p["id"] for p in tan_input]
    n = len(part_ids)

    h = model.encode(tan_input)
    scores = model.parent_scores(h)
    parent_of = chu_liu_edmonds_parents(scores, part_ids)

    id_to_h = {pid: h[i] for i, pid in enumerate(part_ids)}
    output = []
    for pid in part_ids:
        parent_id = parent_of[pid]
        if parent_id is None:
            output.append({"part_id": pid, "parent_id": None, "endpoint": None})
        else:
            logit = model.endpoint_logit(id_to_h[pid].unsqueeze(0), id_to_h[parent_id].unsqueeze(0))
            endpoint = "tip" if torch.sigmoid(logit).item() > 0.5 else "base"
            output.append({"part_id": pid, "parent_id": parent_id, "endpoint": endpoint})

    return enforce_symmetry_consistency(output, raw_parts)
