"""
Name Encoder
============
Turns a part's `name` string into a feature vector. Pluggable so the
learned-vocab version (works fully offline, what this sandbox can run) can
be swapped for a real pretrained semantic embedding once you're running
locally with internet access.

IMPORTANT LIMITATION, stated plainly: this sandbox's network access does not
include model-weight hosts (e.g. huggingface.co), so I cannot actually fetch
or run a pretrained embedding model here. LearnedNameEncoder below is what
TAN v0.1 actually runs on in this environment. PretrainedNameEncoder is real,
working code -- but untested in this sandbox -- for you to switch to on your
own machine once you have a name vocabulary large/varied enough that
generalizing to unseen part names actually matters.
"""

from __future__ import annotations
import torch
import torch.nn as nn


class NameEncoder(nn.Module):
    """Interface: forward(name: str) -> Tensor[out_dim]. All part names in a batch go one at a time (small n, no need to batch)."""
    out_dim: int


class LearnedNameEncoder(NameEncoder):
    """
    Small learned embedding table over the vocabulary seen at construction time.
    Default for TAN v0.1 in this sandbox. Known limitation: any part name not
    seen during training maps to a single shared UNK vector -- no semantic
    generalization to new names (e.g. "flipper" gets no benefit from "fin"
    being in the vocabulary).
    """

    def __init__(self, vocab: list[str], dim: int = 24):
        super().__init__()
        self.name2idx = {n: i + 1 for i, n in enumerate(sorted(set(vocab)))}  # 0 reserved for UNK
        self.emb = nn.Embedding(len(self.name2idx) + 1, dim)
        self.out_dim = dim

    def forward(self, name: str) -> torch.Tensor:
        idx = self.name2idx.get(name, 0)
        return self.emb(torch.tensor(idx))


class PretrainedNameEncoder(NameEncoder):
    """
    Real semantic embedding via sentence-transformers, frozen (not fine-tuned).
    Requires: pip install sentence-transformers
    Requires: internet access to huggingface.co on first run to download weights.
    NOT importable/runnable in this sandbox -- written for you to use locally.

    Usage once you're ready to switch:
        encoder = PretrainedNameEncoder(model_name="all-MiniLM-L6-v2")
        # then pass encoder.out_dim into ToyTAN/TANModel's constructor,
        # and pass `name_encoder=encoder` instead of a LearnedNameEncoder.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", project_to: int | None = 24):
        super().__init__()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            ) from e
        self._model = SentenceTransformer(model_name)
        raw_dim = self._model.get_sentence_embedding_dimension()
        self.project = nn.Linear(raw_dim, project_to) if project_to else None
        self.out_dim = project_to or raw_dim
        self._cache: dict[str, torch.Tensor] = {}

    def forward(self, name: str) -> torch.Tensor:
        if name not in self._cache:
            with torch.no_grad():
                vec = self._model.encode(name, convert_to_tensor=True)
            self._cache[name] = vec
        vec = self._cache[name]
        return self.project(vec) if self.project else vec
