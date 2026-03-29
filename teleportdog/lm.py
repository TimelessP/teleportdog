from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CharNGramLM:
    """A tiny dependency-free character n-gram language model."""

    order: int = 4
    seed: int = 42
    _counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    _charset: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if not self._counts:
            self._counts = {}

    def _pad(self, text: str) -> str:
        return ("~" * (self.order - 1)) + text

    def learn(self, text: str) -> None:
        if not text:
            return
        padded = self._pad(text)
        for ch in text:
            self._charset.add(ch)
        for i in range(self.order - 1, len(padded)):
            ctx = padded[i - (self.order - 1) : i]
            nxt = padded[i]
            bucket = self._counts.setdefault(ctx, {})
            bucket[nxt] = bucket.get(nxt, 0) + 1

    def fit(self, texts: list[str]) -> None:
        for text in texts:
            self.learn(text)

    def _sample_char(self, context: str, temperature: float = 0.9) -> str:
        if not self._charset:
            return " "
        ctx = context[-(self.order - 1) :]
        counts = self._counts.get(ctx)
        if not counts:
            return self._rng.choice(sorted(self._charset))

        chars = list(counts.keys())
        weights = [float(counts[c]) for c in chars]
        if temperature <= 0:
            # Greedy path.
            return chars[max(range(len(chars)), key=lambda i: weights[i])]

        # Temperature scaling for a tiny categorical distribution.
        scaled = [w ** (1.0 / max(temperature, 1e-6)) for w in weights]
        total = sum(scaled)
        if total <= 0:
            return self._rng.choice(chars)
        r = self._rng.random() * total
        running = 0.0
        for c, w in zip(chars, scaled):
            running += w
            if running >= r:
                return c
        return chars[-1]

    def generate(self, prompt: str, max_new_chars: int = 240, temperature: float = 0.85) -> str:
        context = self._pad(prompt)
        out = []
        for _ in range(max_new_chars):
            ch = self._sample_char(context, temperature=temperature)
            out.append(ch)
            context += ch
            if ch in "\n.!?" and len(out) > 40:
                break
        return "".join(out)

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "seed": self.seed,
            "counts": self._counts,
            "charset": sorted(self._charset),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharNGramLM":
        lm = cls(order=int(data.get("order", 4)), seed=int(data.get("seed", 42)))
        lm._counts = {
            str(ctx): {str(k): int(v) for k, v in inner.items()}
            for ctx, inner in data.get("counts", {}).items()
        }
        lm._charset = set(data.get("charset", []))
        return lm
