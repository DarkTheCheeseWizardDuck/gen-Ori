"""
TAN v0.1 -- training loop.

Loss stays simple per-part cross-entropy (parent) + BCE (endpoint), same as
the toy version. Note: this relies on your dataset's ground_truth already
following the canonical-convention checklist (mirrored parts share identical
labels) -- if that holds, standard per-part loss already teaches consistency,
no special-casing needed here. enforce_symmetry_consistency in tan_decode.py
is the safety net for when the model doesn't perfectly generalize that on
its own yet.
"""

import sys
sys.path.insert(0, "/home/claude/search225/SEARCH-22.5")

import torch
import torch.nn.functional as F

from load_dataset import load_dataset
from length_resolver import strip_for_tan
from tan_model import TANModel, build_group_vocab, build_name_vocab
from name_encoder import LearnedNameEncoder
from tan_decode import predict

ENDPOINT2IDX = {"base": 0.0, "tip": 1.0}


def id_index_map(tan_input):
    return {p["id"]: i for i, p in enumerate(tan_input)}


def train(model, dataset, epochs=1200, lr=3e-3, verbose_every=200):
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        opt.zero_grad()
        for obj in dataset:
            tan_input = strip_for_tan(obj["raw_parts"])
            idmap = id_index_map(tan_input)
            n = len(tan_input)
            h = model.encode(tan_input)
            scores = model.parent_scores(h)

            parent_targets = torch.zeros(n, dtype=torch.long)
            ec, ep, et = [], [], []
            for gt in obj["ground_truth"]:
                ci = idmap[gt["part_id"]]
                if gt["parent_id"] is None:
                    parent_targets[ci] = n
                else:
                    pi = idmap[gt["parent_id"]]
                    parent_targets[ci] = pi
                    ec.append(ci); ep.append(pi); et.append(ENDPOINT2IDX[gt["endpoint"]])

            loss_parent = F.cross_entropy(scores, parent_targets)
            logits = model.endpoint_logit(h[torch.tensor(ec)], h[torch.tensor(ep)])
            loss_endpoint = F.binary_cross_entropy_with_logits(logits, torch.tensor(et))

            loss = loss_parent + loss_endpoint
            loss.backward()
            total_loss += loss.item()

        opt.step()
        if epoch % verbose_every == 0 or epoch == 1:
            print(f"epoch {epoch:4d}  total_loss {total_loss:.4f}")


def evaluate(model, dataset) -> dict:
    results = {}
    for obj in dataset:
        pred = predict(model, obj["raw_parts"])
        gt_by_id = {gt["part_id"]: gt for gt in obj["ground_truth"]}
        correct = sum(
            1 for p in pred
            if p["parent_id"] == gt_by_id[p["part_id"]]["parent_id"]
            and p["endpoint"] == gt_by_id[p["part_id"]]["endpoint"]
        )
        results[obj["name"]] = (correct, len(pred))
    return results


if __name__ == "__main__":
    dataset = load_dataset("dataset")
    print(f"Loaded {len(dataset)} objects: {[d['name'] for d in dataset]}\n")

    name_vocab = build_name_vocab(dataset)
    group_vocab = build_group_vocab(dataset)
    name_encoder = LearnedNameEncoder(name_vocab)
    model = TANModel(name_encoder, group_vocab)

    train(model, dataset)

    print("\n=== Evaluation (exact match, Chu-Liu/Edmonds + symmetry-enforced decode) ===")
    for name, (correct, total) in evaluate(model, dataset).items():
        print(f"{name:10s}  {correct}/{total} parts exactly correct")
