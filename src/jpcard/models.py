"""Plain data containers shared by the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .analyze import Token


@dataclass
class CardRow:
    sentence: str
    target: str
    sentence_meaning: str = ""
    target_meaning: str = ""
    target_reading: str = ""
    word_audio: str = ""
    sentence_audio: str = ""
    tags: str = ""
    source: str = ""

    @property
    def key(self) -> str:
        import hashlib

        raw = f"{self.sentence}\x1f{self.target}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:20]


@dataclass
class Span:
    start: int
    end: int          # exclusive token index
    score: int        # lower is a better match

    def __len__(self) -> int:
        return self.end - self.start


@dataclass
class ProcessedCard:
    row: CardRow
    tokens: list[Token]
    spans: list[Span]
    furigana: str
    target_kanji: str
    target_kana: str
    target_reading: str
    key: str
    sentence_audio: Path | None = None
    word_audio: Path | None = None
    sentence_audio_source: str = "none"
    word_audio_source: str = "none"
    stroke_order: str = ""
    stroke_media: list[Path] = field(default_factory=list)
    stroke_chars: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def target_indices(self) -> set[int]:
        return {i for span in self.spans for i in range(span.start, span.end)}


@dataclass
class ErrorRow:
    row_number: int
    sentence: str
    target: str
    error: str
    tokens: str = ""
