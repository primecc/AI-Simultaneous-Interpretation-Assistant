import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticTextSegment:
    text: str
    reason: str


class SemanticTextSegmenter:
    """Merge short ASR fragments into sentence-like units before translation."""

    def __init__(
        self,
        *,
        min_words: int = 7,
        pause_min_words: int = 4,
        max_words: int = 34,
        max_chars: int = 220,
        max_hold_chunks: int = 3,
    ) -> None:
        self._min_words = min_words
        self._pause_min_words = pause_min_words
        self._max_words = max_words
        self._max_chars = max_chars
        self._max_hold_chunks = max_hold_chunks
        self._buffer = ""
        self._chunks = 0

    @property
    def preview(self) -> str:
        return self._buffer

    def push(self, text: str) -> list[SemanticTextSegment]:
        cleaned = _normalize_spacing(text)
        if not cleaned:
            return []
        if _looks_like_duplicate(self._buffer, cleaned):
            return []
        self._buffer = _merge_text(self._buffer, cleaned)
        self._chunks += 1
        return self._drain_ready()

    def flush_on_pause(self) -> SemanticTextSegment | None:
        if not self._buffer:
            return None

        words = _word_count(self._buffer)
        has_terminal = _has_terminal_boundary(self._buffer)
        if has_terminal and words >= 1:
            return self._pop_buffer("pause")
        if words >= self._max_words:
            return self._pop_buffer("pause")
        if words >= self._pause_min_words and not _has_weak_ending(self._buffer):
            return self._pop_buffer("pause")
        return None

    def flush_remaining(self) -> SemanticTextSegment | None:
        if not self._buffer:
            return None
        return self._pop_buffer("flush")

    def _drain_ready(self) -> list[SemanticTextSegment]:
        ready: list[SemanticTextSegment] = []
        while self._buffer:
            boundary = self._find_internal_sentence_boundary()
            if boundary is None:
                break
            sentence = self._buffer[:boundary].strip()
            self._buffer = self._buffer[boundary:].strip()
            self._chunks = 1 if self._buffer else 0
            ready.append(SemanticTextSegment(sentence, "punctuation"))

        if self._buffer and self._is_buffer_ready():
            ready.append(self._pop_buffer("semantic"))

        return ready

    def _find_internal_sentence_boundary(self) -> int | None:
        for match in re.finditer(r"[.!?]+(?:[\"')\]]+)?\s+", self._buffer):
            boundary = match.end()
            sentence = self._buffer[:boundary].strip()
            if _word_count(sentence) < self._min_words:
                continue
            if _has_weak_ending(sentence):
                continue
            return boundary
        return None

    def _is_buffer_ready(self) -> bool:
        words = _word_count(self._buffer)
        if words <= 0:
            return False
        if words >= self._max_words + 8 or len(self._buffer) >= self._max_chars + 60:
            return True
        if _has_weak_ending(self._buffer):
            return False
        if words >= self._max_words or len(self._buffer) >= self._max_chars:
            return True
        if _has_terminal_boundary(self._buffer) and words >= self._min_words:
            return True
        return self._chunks >= self._max_hold_chunks and words >= self._min_words + 2

    def _pop_buffer(self, reason: str) -> SemanticTextSegment:
        segment = SemanticTextSegment(_normalize_spacing(self._buffer), reason)
        self._buffer = ""
        self._chunks = 0
        return segment


def _normalize_spacing(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    return len(_word_tokens(text))


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def _has_terminal_boundary(text: str) -> bool:
    return bool(re.search(r"[.!?]+(?:[\"')\]]+)?$", text.strip()))


def _has_weak_ending(text: str) -> bool:
    lowered = text.lower().strip()
    lowered = re.sub(r"[.!?,;:\"')\]]+$", "", lowered).strip()
    if not lowered:
        return False

    weak_phrases = (
        "not only",
        "as well as",
        "in order to",
        "because of",
        "due to",
        "according to",
        "instead of",
        "one of",
        "a lot of",
        "kind of",
        "sort of",
        "the fact that",
        "which means",
        "so that",
        "even though",
    )
    if any(lowered.endswith(phrase) for phrase in weak_phrases):
        return True

    tokens = _word_tokens(lowered)
    if not tokens:
        return False
    weak_last_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "so",
        "because",
        "although",
        "though",
        "if",
        "when",
        "while",
        "as",
        "that",
        "which",
        "who",
        "where",
        "why",
        "how",
        "to",
        "of",
        "for",
        "with",
        "without",
        "from",
        "into",
        "in",
        "on",
        "at",
        "by",
        "about",
        "than",
        "then",
        "only",
        "also",
        "even",
        "very",
        "just",
        "more",
        "less",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
    }
    return tokens[-1] in weak_last_words


def _looks_like_duplicate(existing: str, incoming: str) -> bool:
    existing_norm = _overlap_key(existing)
    incoming_norm = _overlap_key(incoming)
    if not existing_norm or not incoming_norm:
        return False
    return incoming_norm in existing_norm[-max(80, len(incoming_norm)) :]


def _merge_text(existing: str, incoming: str) -> str:
    existing = _normalize_spacing(existing)
    incoming = _normalize_spacing(incoming)
    if not existing:
        return incoming
    if not incoming:
        return existing

    existing_words = existing.split()
    incoming_words = incoming.split()
    max_overlap = min(8, len(existing_words), len(incoming_words))
    for size in range(max_overlap, 0, -1):
        if _words_key(existing_words[-size:]) == _words_key(incoming_words[:size]):
            return _normalize_spacing(" ".join(existing_words + incoming_words[size:]))

    return f"{existing} {incoming}"


def _words_key(words: list[str]) -> str:
    return _overlap_key(" ".join(words))


def _overlap_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())
