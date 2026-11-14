"""Locate the target word inside a tokenised sentence.

The user supplies a dictionary form (食べる, 気に入る) while the sentence may
contain an inflected surface (食べた) or a multi-token compound. Matching is
therefore attempted on surface, lemma, normalised form, and a kana-folded
comparison, for spans of one to five tokens.
"""
from __future__ import annotations

import unicodedata

import jaconv

from .analyze import Analyzer, Token
from .models import Span


class TargetNotFound(Exception):
    def __init__(self, target: str, tokens: list[Token]) -> None:
        self.target = target
        self.tokens = tokens
        super().__init__(f"target {target!r} not found in sentence")


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip())


def kana_fold(text: str) -> str:
    return jaconv.kata2hira(normalize(text))


def find_spans(
    tokens: list[Token], target: str, max_tokens: int = 5
) -> list[Span]:
    """Return non-overlapping spans where the target occurs.

    Raises TargetNotFound if nothing matches.
    """
    needle = normalize(target)
    if not needle:
        raise TargetNotFound(target, tokens)
    folded_needle = kana_fold(needle)

    candidates: list[Span] = []
    count = len(tokens)
    for start in range(count):
        for end in range(start + 1, min(start + max_tokens, count) + 1):
            span = tokens[start:end]
            surface = normalize("".join(t.surface for t in span))
            lemma = normalize("".join(t.lemma for t in span))
            norm = normalize("".join(t.normalized for t in span))

            score: int | None = None
            if surface == needle:
                score = 0
            elif lemma == needle:
                score = 1
            elif norm == needle:
                score = 2
            elif kana_fold(surface) == folded_needle:
                score = 3
            elif kana_fold(lemma) == folded_needle:
                score = 4

            if score is not None:
                candidates.append(Span(start, end, score))

    if not candidates:
        raise TargetNotFound(target, tokens)

    # Best quality first, then longest, then earliest. Greedily keep
    # non-overlapping spans so repeated targets are all annotated.
    candidates.sort(key=lambda s: (s.score, -len(s), s.start))
    chosen: list[Span] = []
    for candidate in candidates:
        if all(
            candidate.end <= existing.start or candidate.start >= existing.end
            for existing in chosen
        ):
            chosen.append(candidate)

    chosen.sort(key=lambda s: s.start)
    return chosen


def dictionary_reading(analyzer: Analyzer, target: str) -> str:
    """Reading of the target as supplied (usually the dictionary form)."""
    return "".join(token.reading for token in analyzer.tokenize(target))
