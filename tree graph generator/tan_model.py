"""
TAN v0.1 -- shared encoder + two heads.

Upgrades over the earlier toy version:
  - name encoding is pluggable (name_encoder.py), not hardcoded
  - decoding (tan_decode.py) uses Chu-Liu/Edmonds for guaranteed valid trees,
    not independent per-part argmax
  - symmetry-consistent decoding: mirrored parts are forced to agree
"""

from __future__ import annotations
import torch
import torch.nn as nn

from name_encoder import NameEncoder

SIDE2IDX = {None: 0, "left": 1, "right": 2, "center": 3}


class TANModel(nn.Module):
    def __init__(self, name_encoder: NameEncoder, group_vocab: dict[str, int], d_model: int = 32):
        super().__init__()
        self.name_encoder = name_encoder
        self.group_vocab = group_vocab

        d_side, d_group, d_seg, d_ord = 4, 8, 4, 4
        self.side_emb = nn.Embedding(4, d_side)
        self.group_emb = nn.Embedding(len(group_vocab) + 1, d_group)  # 0 = no group
        self.seg_emb = nn.Embedding(8, d_seg)   # bucket 0..7, 0 = null
        self.ord_emb = nn.Embedding(6, d_ord)   # bucket 0..5, 0 = null

        in_dim = name_encoder.out_dim + d_side + d_group + d_seg + d_ord
        self.proj = nn.Linear(in_dim, d_model)

        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=4, dim_feedforward=64, batch_first=True)
        self.context = nn.TransformerEncoder(encoder_layer, num_layers=2)

        self.root_vec = nn.Parameter(torch.randn(d_model) * 0.1)
        self.parent_W = nn.Linear(d_model, d_model, bias=False)
        self.endpoint_head = nn.Sequential(
            nn.Linear(2 * d_model, d_model), nn.ReLU(), nn.Linear(d_model, 1)
        )
        self.d_model = d_model

    def featurize(self, tan_input: list[dict]) -> torch.Tensor:
        rows = []
        for p in tan_input:
            sym = p.get("symmetry")
            name_vec = self.name_encoder(p["name"])
            side_i = SIDE2IDX[sym["side"]] if sym else 0
            group_i = self.group_vocab.get(sym["group"], 0) if sym else 0
            seg_i = min(p.get("segment_index") or 0, 7)
            ord_i = min((sym["order_index"] if sym else 0) or 0, 5)
            other = torch.cat([
                self.side_emb(torch.tensor(side_i)),
                self.group_emb(torch.tensor(group_i)),
                self.seg_emb(torch.tensor(seg_i)),
                self.ord_emb(torch.tensor(ord_i)),
            ])
            rows.append(torch.cat([name_vec, other]))
        return self.proj(torch.stack(rows))

    def encode(self, tan_input: list[dict]) -> torch.Tensor:
        x = self.featurize(tan_input).unsqueeze(0)
        return self.context(x).squeeze(0)

    def parent_scores(self, h: torch.Tensor) -> torch.Tensor:
        n = h.shape[0]
        candidates = torch.cat([h, self.root_vec.unsqueeze(0)], dim=0)
        child = self.parent_W(h)
        scores = child @ candidates.T
        mask = torch.zeros(n, n + 1)
        mask[torch.arange(n), torch.arange(n)] = float("-inf")
        return scores + mask  # column n == ROOT

    def endpoint_logit(self, h_child: torch.Tensor, h_parent: torch.Tensor) -> torch.Tensor:
        return self.endpoint_head(torch.cat([h_child, h_parent], dim=-1)).squeeze(-1)


def build_group_vocab(dataset: list[dict]) -> dict[str, int]:
    groups = set()
    for obj in dataset:
        for p in obj["raw_parts"]:
            sym = p.get("symmetry")
            if sym:
                groups.add(sym["group"])
    return {g: i + 1 for i, g in enumerate(sorted(groups))}


def build_name_vocab(dataset: list[dict]) -> list[str]:
    names = set()
    for obj in dataset:
        for p in obj["raw_parts"]:
            names.add(p["name"])
    return sorted(names)
