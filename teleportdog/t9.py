from __future__ import annotations

import re
from collections import defaultdict

LETTER_TO_DIGIT = {
    **{c: "2" for c in "abc"},
    **{c: "3" for c in "def"},
    **{c: "4" for c in "ghi"},
    **{c: "5" for c in "jkl"},
    **{c: "6" for c in "mno"},
    **{c: "7" for c in "pqrs"},
    **{c: "8" for c in "tuv"},
    **{c: "9" for c in "wxyz"},
}

WORD_RE = re.compile(r"[a-zA-Z']+")


class T9:
    def __init__(self) -> None:
        self._index: dict[str, dict[str, int]] = defaultdict(dict)

    @staticmethod
    def encode_word(word: str) -> str:
        chars = [c.lower() for c in word if c.isalpha()]
        if not chars:
            return ""
        return "".join(LETTER_TO_DIGIT.get(c, "") for c in chars)

    def learn_text(self, text: str) -> None:
        for raw in WORD_RE.findall(text):
            word = raw.lower()
            key = self.encode_word(word)
            if not key:
                continue
            bucket = self._index[key]
            bucket[word] = bucket.get(word, 0) + 1

    def suggest(self, digits: str, limit: int = 8) -> list[str]:
        if not digits.isdigit():
            return []
        bucket = self._index.get(digits, {})
        if not bucket:
            return []
        ranked = sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))
        return [w for w, _ in ranked[:limit]]

    def decode_phrase(self, phrase: str) -> tuple[str, list[tuple[str, list[str]]]]:
        """
        Decode whitespace-separated T9 tokens into words.
        Non-digit tokens pass through unchanged.
        Returns decoded text and ambiguity metadata.
        """
        out = []
        ambiguities: list[tuple[str, list[str]]] = []
        for token in phrase.strip().split():
            if token.isdigit():
                candidates = self.suggest(token)
                if candidates:
                    out.append(candidates[0])
                    if len(candidates) > 1:
                        ambiguities.append((token, candidates[:5]))
                else:
                    out.append(f"[{token}]")
            else:
                out.append(token)
        return " ".join(out), ambiguities

    def to_dict(self) -> dict:
        return {
            "index": self._index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "T9":
        t9 = cls()
        idx = data.get("index", {})
        t9._index = defaultdict(dict)
        for key, value in idx.items():
            t9._index[str(key)] = {str(w): int(c) for w, c in value.items()}
        return t9
