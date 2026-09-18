"""Core text, MinHash, and LSH primitives for tender deduplication."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


TOKEN_RE = re.compile(r"[a-z0-9]+")
REFERENCE_RE = re.compile(r"^(?:npas|spc|pwd|ref|mc|tn|no|nid|nit)[a-z0-9/-]*$", re.I)
DATE_RE = re.compile(r"^(?:\d{1,4}[-/.]){1,2}\d{1,4}$")
MONEY_RE = re.compile(r"^(?:rs|inr|rupees|lakh|lakhs|crore|crores|cr)$", re.I)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def content_tokens(title: str, body: str, stopwords: set[str]) -> list[str]:
    tokens = tokenize(f"{title} {body}")
    return [
        token
        for token in tokens
        if token not in stopwords
        and not REFERENCE_RE.match(token)
        and not DATE_RE.match(token)
        and not MONEY_RE.match(token)
        and not token.isdigit()
    ]


def shingles(tokens: list[str], width: int = 5) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def corpus_stopwords(rows: Iterable[tuple[str, str]], document_fraction: float = 0.20) -> set[str]:
    rows = list(rows)
    document_frequency: Counter[str] = Counter()
    for title, body in rows:
        document_frequency.update(set(tokenize(f"{title} {body}")))
    cutoff = max(2, int(len(rows) * document_fraction))
    return {token for token, count in document_frequency.items() if count >= cutoff}


@dataclass(frozen=True)
class MinHasher:
    permutations: int = 256
    seed: int = 20240917

    def _hash(self, value: str, index: int) -> int:
        digest = hashlib.blake2b(
            f"{self.seed}:{index}:{value}".encode("utf-8"), digest_size=8
        ).digest()
        return int.from_bytes(digest, "big")

    def signature(self, values: set[str]) -> tuple[int, ...]:
        if not values:
            return (0,) * self.permutations
        minima = [2**64 - 1] * self.permutations
        for value in values:
            digest = hashlib.blake2b(f"{self.seed}:{value}".encode("utf-8"), digest_size=64).digest()
            seeds = [int.from_bytes(digest[offset * 8 : (offset + 1) * 8], "big") for offset in range(8)]
            for index in range(self.permutations):
                source = seeds[index % len(seeds)] + self.seed + index * 0x9E3779B97F4A7C15
                candidate = (source ^ (source >> 30)) * 0xBF58476D1CE4E5B9 & (2**64 - 1)
                candidate = (candidate ^ (candidate >> 27)) * 0x94D049BB133111EB & (2**64 - 1)
                candidate ^= candidate >> 31
                if candidate < minima[index]:
                    minima[index] = candidate
        return tuple(minima)


def lsh_buckets(signature: tuple[int, ...], bands: int = 64, rows: int = 4) -> list[tuple[int, str]]:
    if bands * rows != len(signature):
        raise ValueError("bands * rows must equal signature length")
    return [
        (band, hashlib.blake2b(repr(signature[start : start + rows]).encode(), digest_size=12).hexdigest())
        for band, start in enumerate(range(0, len(signature), rows))
    ]


def estimated_jaccard(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return sum(a == b for a, b in zip(left, right)) / len(left)