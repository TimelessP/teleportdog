from __future__ import annotations

import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CharNGramLM:
    """A tiny dependency-free n-gram language model.

    Default mode is subword-token n-grams for better coherence than raw chars.
    Legacy char-model state is still loadable for backward compatibility.
    """

    order: int = 4
    seed: int = 42
    unit: str = "subword"
    _counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    _charset: set[str] = field(default_factory=set)

    _SEP = "\x1f"
    _BOS = "<s>"

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if not self._counts:
            self._counts = {}

    def _tokenize(self, text: str) -> list[str]:
        # Keep whitespace as tokens so reconstruction preserves natural spacing.
        raw = re.findall(r"\s+|[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[.,!?;:()\-]|\S", text)
        out: list[str] = []
        for tok in raw:
            if tok.isspace() or not tok or len(tok) <= 8 or not tok.isalpha():
                out.append(tok)
                continue

            # Tiny subword split for long words to improve generalization.
            head = tok[:4]
            out.append(head)
            rest = tok[4:]
            for i in range(0, len(rest), 3):
                out.append("##" + rest[i : i + 3])
        return out

    def _detokenize(self, tokens: list[str]) -> str:
        pieces: list[str] = []
        for tok in tokens:
            if tok.startswith("##") and pieces:
                pieces[-1] += tok[2:]
            else:
                pieces.append(tok)
        return "".join(pieces)

    def _pack_ctx(self, tokens: list[str]) -> str:
        return self._SEP.join(tokens)

    def _unpack_ctx(self, ctx: str) -> list[str]:
        if not ctx:
            return []
        return ctx.split(self._SEP)

    def _pad(self, text: str) -> str:
        return ("~" * (self.order - 1)) + text

    def _pad_tokens(self, tokens: list[str]) -> list[str]:
        return ([self._BOS] * (self.order - 1)) + tokens

    def learn(self, text: str) -> None:
        if not text:
            return
        if self.unit == "char":
            self._learn_char(text)
            return

        tokens = self._tokenize(text)
        if not tokens:
            return
        padded = self._pad_tokens(tokens)
        for tok in tokens:
            self._charset.add(tok)
        for i in range(self.order - 1, len(padded)):
            ctx = padded[i - (self.order - 1) : i]
            nxt = padded[i]
            bucket = self._counts.setdefault(self._pack_ctx(ctx), {})
            bucket[nxt] = bucket.get(nxt, 0) + 1

    def _learn_char(self, text: str) -> None:
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

    def _sample_token(self, context_tokens: list[str], temperature: float = 0.9) -> str:
        if not self._charset:
            return " "
        ctx = context_tokens[-(self.order - 1) :]
        counts = self._counts.get(self._pack_ctx(ctx))
        if not counts:
            return self._rng.choice(sorted(self._charset))

        toks = list(counts.keys())
        weights = [float(counts[t]) for t in toks]
        if temperature <= 0:
            return toks[max(range(len(toks)), key=lambda i: weights[i])]

        scaled = [w ** (1.0 / max(temperature, 1e-6)) for w in weights]
        total = sum(scaled)
        if total <= 0:
            return self._rng.choice(toks)
        r = self._rng.random() * total
        running = 0.0
        for tok, w in zip(toks, scaled):
            running += w
            if running >= r:
                return tok
        return toks[-1]

    def generate(self, prompt: str, max_new_chars: int = 240, temperature: float = 0.85) -> str:
        if self.unit == "char":
            return self._generate_char(prompt, max_new_chars=max_new_chars, temperature=temperature)

        prompt_tokens = self._tokenize(prompt)
        context_tokens = self._pad_tokens(prompt_tokens)
        out_tokens: list[str] = []
        max_new_tokens = max(24, min(120, max_new_chars // 2))
        for _ in range(max_new_tokens):
            tok = self._sample_token(context_tokens, temperature=temperature)
            out_tokens.append(tok)
            context_tokens.append(tok)
            if tok in {".", "!", "?"} and len(out_tokens) >= 14:
                break
        return self._detokenize(out_tokens)

    def _generate_char(self, prompt: str, max_new_chars: int = 240, temperature: float = 0.85) -> str:
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
            "unit": self.unit,
            "counts": self._counts,
            "charset": sorted(self._charset),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharNGramLM":
        unit = str(data.get("unit", "char" if "counts" in data and "charset" in data and "unit" not in data else "subword"))
        lm = cls(order=int(data.get("order", 4)), seed=int(data.get("seed", 42)), unit=unit)
        lm._counts = {
            str(ctx): {str(k): int(v) for k, v in inner.items()}
            for ctx, inner in data.get("counts", {}).items()
        }
        lm._charset = set(data.get("charset", []))
        return lm
