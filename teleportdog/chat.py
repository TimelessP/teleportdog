from __future__ import annotations

import json
import glob
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .lm import CharNGramLM
from .t9 import T9


DEFAULT_STATE_PATH = Path.home() / ".teleportdog" / "state.json"
FALLBACK_RESPONSES = [
    "I am teleportdog: tiny, local, and still learning. Tell me more.",
    "That is interesting. Can you add one concrete detail?",
    "I can chat offline and keep adapting from this conversation.",
    "Let us keep it practical. What should we do next?",
]

SESSION_CONTEXT_VERSION = 1
SESSION_CONTEXT_SNIPPETS = [
    "system: You are teleportdog, an offline-only local CLI chat assistant.",
    "system: Keep answers concise, practical, and clear.",
    "system: Never claim internet access or remote tools.",
    "system: You can decode T9 sequences and suggest words for numeric input.",
    "system: You can learn incrementally from user text within and across sessions.",
    "assistant: I should give direct answers first, then one practical next step when useful.",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "we",
    "what",
    "you",
    "your",
}

TEXT_FILE_SUFFIXES = {
    ".csv",
    ".jsonl",
    ".log",
    ".markdown",
    ".md",
    ".text",
    ".txt",
}


def _load_bootstrap_corpus() -> list[str]:
    data_path = Path(__file__).parent / "data" / "bootstrap_corpus.txt"
    text = data_path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    return chunks


def _clean_generated(text: str) -> str:
    # Keep output compact and printable for a CLI chat loop.
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\x20-\x7E]", "", text)
    return text


def _looks_like_markupish_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("#", "- ", "* ", "> ", "```")):
        return True
    if re.match(r"^\d+\.\s", stripped):
        return True
    if "`" in stripped:
        return True
    if re.search(r"https?://|\[[^\]]+\]\([^\)]+\)|<[^>]+>|\bwww\.", stripped):
        return True
    return False


def _looks_like_structured_metadata(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if '"""' in stripped:
        return True
    if re.match(r"^[\{\[]", stripped):
        return True
    # key: value style lines from JSON/YAML-like corpora.
    if re.match(r"^[\"']?[a-zA-Z0-9_ .-]{1,40}[\"']?\s*:\s*", stripped):
        return True

    punct = sum(1 for ch in stripped if not (ch.isalnum() or ch.isspace()))
    if punct / max(1, len(stripped)) > 0.22:
        return True
    return False


def _is_usable_sentence(text: str) -> bool:
    if _looks_like_markupish_text(text):
        return False
    if _looks_like_structured_metadata(text):
        return False
    if len(_keywords(text)) == 0:
        return False
    return True


def _normalize_sentence_key(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    out = []
    for chunk in chunks:
        s = chunk.strip()
        if len(s) < 8:
            continue
        if s.lower().startswith(("system:", "user:")):
            continue
        if s.lower().startswith("assistant:"):
            s = s.split(":", 1)[1].strip()
        if not _is_usable_sentence(s):
            continue
        out.append(_clean_generated(s))
    return out


def _resolve_corpus_paths(inputs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()

    for item in inputs:
        raw = item.strip()
        if not raw:
            continue
        expanded = os.path.expanduser(raw)
        matches = glob.glob(expanded, recursive=True)
        if not matches and Path(expanded).exists():
            matches = [expanded]

        for match in matches:
            p = Path(match)
            if p.is_dir():
                for child in p.rglob("*"):
                    if child.is_file() and child.suffix.lower() in TEXT_FILE_SUFFIXES:
                        key = str(child.resolve())
                        if key not in seen:
                            seen.add(key)
                            resolved.append(child)
            elif p.is_file():
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    resolved.append(p)

    return resolved


def _file_signature(path: Path) -> str:
    st = path.stat()
    return f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"


def _read_text_chunks(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    return chunks or [text.strip()] if text.strip() else []


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _top_sentences(user_text: str, bank: list[str], limit: int = 2) -> list[str]:
    query = _keywords(user_text)
    if not query:
        return []

    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, sentence in enumerate(bank):
        if not _is_usable_sentence(sentence):
            continue
        key = _normalize_sentence_key(sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        sk = _keywords(sentence)
        if not sk:
            continue
        overlap = len(query & sk)
        if overlap <= 0:
            continue
        # Prefer strong overlap and more recent learned sentences.
        recency_bonus = idx
        scored.append((overlap, recency_bonus, sentence))

    scored.sort(key=lambda x: (-x[0], -x[1]))
    out: list[str] = []
    for _, _, s in scored:
        if not out:
            out.append(s)
        else:
            # Avoid near-duplicate second line in "Also:" responses.
            if _normalize_sentence_key(s) == _normalize_sentence_key(out[0]):
                continue
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _gen_quality_score(text: str) -> float:
    """Heuristic quality score for tiny char-model outputs in range [0, 1]."""
    if not text:
        return 0.0

    score = 0.0
    n = len(text)
    alpha = sum(1 for ch in text if ch.isalpha())
    spaces = sum(1 for ch in text if ch.isspace())
    printable = sum(1 for ch in text if 32 <= ord(ch) <= 126)
    weird = sum(1 for ch in text if not (ch.isalnum() or ch.isspace() or ch in ".,!?':;\"-()"))

    alpha_ratio = alpha / max(n, 1)
    space_ratio = spaces / max(n, 1)
    printable_ratio = printable / max(n, 1)
    weird_ratio = weird / max(n, 1)

    # Healthy natural-language-ish signal.
    if 0.55 <= alpha_ratio <= 0.92:
        score += 0.28
    if 0.08 <= space_ratio <= 0.30:
        score += 0.18
    if printable_ratio > 0.98:
        score += 0.14

    # Basic length and sentence shape checks.
    if 24 <= n <= 220:
        score += 0.18
    if text.endswith((".", "!", "?")):
        score += 0.08

    # Penalties for noisy artifacts.
    if re.search(r"(.)\1\1\1", text):
        score -= 0.16
    if re.search(r"[0-9]{3,}", text):
        score -= 0.10
    if re.search(r"[^\w\s.,!?':;\"\-()]", text):
        score -= 0.12
    score -= min(0.24, weird_ratio * 0.8)

    return max(0.0, min(1.0, score))


def _gen_relevance_score(user_text: str, candidate: str) -> float:
    """Keyword-overlap relevance score in range [0, 1]."""
    q = _keywords(user_text)
    if not q:
        return 0.5
    c = _keywords(candidate)
    if not c:
        return 0.0
    overlap = len(q & c)
    return min(1.0, overlap / max(1, len(q)))


def _looks_like_markup_or_link_noise(text: str) -> bool:
    """Reject obvious markdown/html/link fragments often seen in noisy corpora."""
    return _looks_like_markupish_text(text)


@dataclass
class TeleportDog:
    model: CharNGramLM = field(default_factory=lambda: CharNGramLM(order=5, seed=42))
    t9: T9 = field(default_factory=T9)
    history: list[tuple[str, str]] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)
    context_version: int = 0
    imported_corpus_signatures: set[str] = field(default_factory=set)

    @classmethod
    def bootstrap(cls) -> "TeleportDog":
        bot = cls()
        corpus = _load_bootstrap_corpus()
        bot.model.fit(corpus)
        for chunk in corpus:
            bot.t9.learn_text(chunk)
            bot.knowledge.extend(_split_sentences(chunk))
        bot.init_session_context(force=True)
        return bot

    def init_session_context(self, force: bool = False) -> None:
        """Seed invariant session context so each run starts with core behavior hints."""
        if not force and self.context_version >= SESSION_CONTEXT_VERSION:
            return
        for snippet in SESSION_CONTEXT_SNIPPETS:
            self.learn(snippet)
        self.context_version = SESSION_CONTEXT_VERSION

    def import_external_corpus(self, inputs: list[str] | None = None) -> int:
        if not inputs:
            return 0

        learned_files = 0
        for path in _resolve_corpus_paths(inputs):
            sig = _file_signature(path)
            if sig in self.imported_corpus_signatures:
                continue
            for chunk in _read_text_chunks(path):
                self.learn(chunk)
            self.imported_corpus_signatures.add(sig)
            learned_files += 1
        return learned_files

    def learn(self, text: str) -> None:
        self.model.learn(text)
        self.t9.learn_text(text)
        self.knowledge.extend(_split_sentences(text))

    def _build_prompt(self, user_text: str) -> str:
        turns = self.history[-6:]
        parts = [
            "system: You are teleportdog, a tiny local offline chat assistant.",
            "system: Keep replies concise, friendly, and practical.",
        ]
        for u, a in turns:
            parts.append(f"user: {u}")
            parts.append(f"assistant: {a}")
        parts.append(f"user: {user_text}")
        parts.append("assistant:")
        return "\n".join(parts)

    def generate_reply(
        self,
        user_text: str,
        temperature: float = 0.55,
        max_new_chars: int = 220,
        num_candidates: int = 6,
        min_quality: float = 0.58,
    ) -> str:
        """Generate a reply directly from the tiny local char model."""
        prompt = self._build_prompt(user_text)
        candidates: list[tuple[float, float, str]] = []
        for _ in range(max(1, num_candidates)):
            generated = self.model.generate(
                prompt=prompt,
                max_new_chars=max_new_chars,
                temperature=temperature,
            )
            text = _clean_generated(generated)
            if "assistant:" in text:
                text = text.split("assistant:", 1)[-1].strip()
            text = re.split(r"\buser:\b|\bsystem:\b", text)[0].strip()
            quality = _gen_quality_score(text)
            relevance = _gen_relevance_score(user_text, text)

            # Blend lexical quality and prompt relevance; heavy penalty for markdown/link noise.
            blended = (0.65 * quality) + (0.35 * relevance)
            if _looks_like_markup_or_link_noise(text):
                blended -= 0.35

            candidates.append((max(0.0, min(1.0, blended)), relevance, text))

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_relevance, text = candidates[0]

        asks_definition = bool(re.search(r"^(who|what)\s+is\b", user_text.lower().strip()))

        # If generation looks too noisy, route to stable non-generative path.
        if best_score < min_quality or (asks_definition and best_relevance < 0.34):
            return self.reply(user_text)

        if len(text) < 8:
            text = FALLBACK_RESPONSES[len(self.history) % len(FALLBACK_RESPONSES)]
        text = text.strip(" -:\t")
        if not text.endswith((".", "!", "?")):
            text += "."

        self.history.append((user_text, text))
        self.learn(f"user: {user_text}\nassistant: {text}\n")
        return text

    def reply(self, user_text: str, temperature: float = 0.8) -> str:
        _ = temperature  # Kept for API compatibility in a tiny local model.
        lower = user_text.lower().strip()

        # Lightweight intent: puzzle-style "starts with X and ends with Y".
        m = re.search(r"starts with\s+([a-zA-Z]+)\s+and\s+ends with\s+([a-zA-Z]+)", lower)
        if m:
            prefix = m.group(1)
            suffix = m.group(2)
            text = f"Likely answer: {prefix}{suffix}."
        elif any(k in lower for k in ("summarise", "summarize")):
            topics = sorted({w for s in self.knowledge[-300:] for w in _keywords(s)})
            if topics:
                text = "I mainly know about: " + ", ".join(topics[:10]) + "."
            else:
                text = "I know basic chat behavior, offline operation, and T9 decoding."
        elif lower in {"hi", "hello", "hey", "yo"} or lower.startswith("hello "):
            text = "Hi. I am teleportdog, local and ready to chat."
        elif any(k in lower for k in ("help", "how", "what can you do")):
            text = "I can chat offline, learn from your text, and decode T9 digits into words."
        elif any(k in lower for k in ("name", "who are you")):
            text = "I am teleportdog: a tiny offline chat mutt with T9 instincts."
        else:
            matches = _top_sentences(user_text, self.knowledge, limit=2)
            if matches:
                if len(matches) == 1:
                    text = matches[0]
                else:
                    text = f"{matches[0]} Also: {matches[1]}"
            else:
                # Last resort fallback from a tiny rotating bank.
                text = FALLBACK_RESPONSES[len(self.history) % len(FALLBACK_RESPONSES)]

        text = text.strip(" -:\t")
        if not text.endswith((".", "!", "?")):
            text += "."

        self.history.append((user_text, text))
        self.learn(f"user: {user_text}\nassistant: {text}\n")
        return text

    def save(self, path: Path = DEFAULT_STATE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model.to_dict(),
            "t9": self.t9.to_dict(),
            "history": self.history[-200:],
            "knowledge": self.knowledge[-2000:],
            "context_version": self.context_version,
            "imported_corpus_signatures": sorted(self.imported_corpus_signatures),
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load_or_bootstrap(
        cls,
        path: Path = DEFAULT_STATE_PATH,
        corpus_inputs: list[str] | None = None,
    ) -> "TeleportDog":
        if not path.exists():
            bot = cls.bootstrap()
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            bot = cls(
                model=CharNGramLM.from_dict(payload.get("model", {})),
                t9=T9.from_dict(payload.get("t9", {})),
                history=[tuple(item) for item in payload.get("history", [])],
                knowledge=[str(item) for item in payload.get("knowledge", [])],
                context_version=int(payload.get("context_version", 0)),
                imported_corpus_signatures=set(payload.get("imported_corpus_signatures", [])),
            )
            if not bot.knowledge:
                for chunk in _load_bootstrap_corpus():
                    bot.knowledge.extend(_split_sentences(chunk))
            bot.init_session_context()

        bot.import_external_corpus(corpus_inputs)
        return bot
