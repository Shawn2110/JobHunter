from __future__ import annotations

import math
from typing import Protocol


class Embedder(Protocol):
    """Anything that maps text to a fixed-dimension vector."""

    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic 384-dim embedder using character 3-gram hashing.

    NOT semantic — it matches text by character overlap, not meaning.
    Used as a self-contained development backend so the indexing
    pipeline runs end-to-end without requiring sentence-transformers
    (~400MB model + dep weight). Swap in a real embedder by giving the
    IndexService any object satisfying the Embedder protocol; nothing
    else needs to change.
    """

    dim: int = 384

    def embed(self, text: str) -> list[float]:
        normalized = " ".join((text or "").lower().split())
        vec = [0.0] * self.dim
        for i in range(max(len(normalized) - 2, 0)):
            tri = normalized[i : i + 3]
            # hash() randomization across runs would break reproducibility
            # — use a stable hash.
            slot = _stable_hash(tri) % self.dim
            vec[slot] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def _stable_hash(s: str) -> int:
    """FNV-1a 32-bit — small, fast, deterministic across processes."""
    h = 0x811C9DC5
    for byte in s.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
