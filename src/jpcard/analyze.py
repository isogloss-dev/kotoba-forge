"""Morphological analysis.

SudachiPy is used with the `core` dictionary in split mode C. Readings come
back as katakana and are converted to hiragana immediately, so every Token
carries a hiragana reading.
"""
from __future__ import annotations

from dataclasses import dataclass

import jaconv
from sudachipy import dictionary

try:  # SudachiPy >= 0.7
    from sudachipy import SplitMode
except ImportError:  # pragma: no cover - very old versions
    SplitMode = None  # type: ignore[assignment]


class AnalysisError(Exception):
    """Raised when tokenisation does not reconstruct the input exactly."""


def is_kanji(ch: str) -> bool:
    """True for characters that take a reading (kanji, iteration marks, ヶ)."""
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF:      # CJK Unified Ideographs
        return True
    if 0x3400 <= o <= 0x4DBF:      # CJK Extension A
        return True
    if 0xF900 <= o <= 0xFAFF:      # CJK Compatibility Ideographs
        return True
    if 0x3005 <= o <= 0x3007:      # 々 〆 〇
        return True
    return ch in "ヶヵ"


def is_kana(ch: str) -> bool:
    o = ord(ch)
    return (
        0x3040 <= o <= 0x309F      # hiragana
        or 0x30A0 <= o <= 0x30FF   # katakana (includes ー)
        or 0xFF66 <= o <= 0xFF9D   # halfwidth katakana
    )


@dataclass(frozen=True)
class Token:
    surface: str
    lemma: str
    reading: str      # hiragana, full token reading (may equal surface)
    normalized: str
    pos: str
    index: int

    @property
    def has_kanji(self) -> bool:
        return any(is_kanji(c) for c in self.surface)


class Analyzer:
    """Thin, reusable wrapper around a Sudachi tokenizer."""

    def __init__(self, dict_type: str = "core") -> None:
        d = dictionary.Dictionary(dict=dict_type)
        # 0.7 renamed create() -> tokenizer(); support both.
        factory = getattr(d, "tokenizer", None) or d.create
        self._tokenizer = factory()
        self._mode = SplitMode.C if SplitMode is not None else None

    def tokenize(self, text: str) -> list[Token]:
        if not text:
            return []
        raw = (
            self._tokenizer.tokenize(text, self._mode)
            if self._mode is not None
            else self._tokenizer.tokenize(text)
        )
        tokens: list[Token] = []
        for i, m in enumerate(raw):
            reading = m.reading_form() or m.surface()
            if reading in ("", "*"):
                reading = m.surface()
            tokens.append(
                Token(
                    surface=m.surface(),
                    lemma=m.dictionary_form(),
                    reading=jaconv.kata2hira(reading),
                    normalized=m.normalized_form(),
                    pos=m.part_of_speech()[0],
                    index=i,
                )
            )

        joined = "".join(t.surface for t in tokens)
        if joined != text:
            raise AnalysisError(
                "tokenisation did not reconstruct the input; "
                f"input={text!r} reconstructed={joined!r}"
            )
        return tokens
