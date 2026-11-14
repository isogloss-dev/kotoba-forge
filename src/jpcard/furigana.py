"""Render a tokenised sentence into the three furigana variants.

Convention (agreed with the user): bracket each maximal *kanji run* with its
reading, and leave kana bare. For example:

    食べる  ->  食[た]べる
    食べ物  ->  食[た]べ物[もの]
    お菓子  ->  お菓子[かし]      (お is a separate token and stays bare)

This is unambiguous for Anki's furigana filter and does not depend on it
stripping okurigana.
"""
from __future__ import annotations

import re

from .analyze import Token, is_kanji, is_kana


def split_runs(surface: str) -> list[tuple[str, str]]:
    """Split a token surface into alternating ('kanji'|'kana', text) runs."""
    runs: list[list[str]] = []
    for ch in surface:
        kind = "kanji" if is_kanji(ch) else ("kana" if is_kana(ch) else "kana")
        if runs and runs[-1][0] == kind:
            runs[-1][1] += ch
        else:
            runs.append([kind, ch])
    return [(k, t) for k, t in runs]


def align(surface: str, reading: str) -> list[tuple[str, str | None]] | None:
    """Align a reading onto the kanji runs of a surface.

    Returns a list of (text, reading-or-None) pieces, or None if the reading
    cannot be aligned (kana in the surface must appear literally in the
    reading).
    """
    runs = split_runs(surface)
    if not any(kind == "kanji" for kind, _ in runs):
        return None
    if not reading:
        return None

    pattern = "".join(
        "(.+?)" if kind == "kanji" else re.escape(text) for kind, text in runs
    )
    match = re.fullmatch(pattern, reading)
    if match is None:
        return None

    pieces: list[tuple[str, str | None]] = []
    group = 1
    for kind, text in runs:
        if kind == "kanji":
            pieces.append((text, match.group(group)))
            group += 1
        else:
            pieces.append((text, None))
    return pieces


def render_token(token: Token) -> str:
    """Render one token with kanji-run furigana.

    Falls back to `surface[reading]` if alignment fails; callers can detect
    that with `alignment_failed()` and warn.
    """
    if not token.has_kanji:
        return token.surface
    pieces = align(token.surface, token.reading)
    if pieces is None:
        return f"{token.surface}[{token.reading}]"
    return "".join(
        f"{text}[{reading}]" if reading is not None else text
        for text, reading in pieces
    )


def alignment_failed(token: Token) -> bool:
    return token.has_kanji and align(token.surface, token.reading) is None


def strip_brackets(text: str) -> str:
    """Remove furigana markup; useful for validation and tests."""
    return re.sub(r"\[[^\]]*\]", "", text)


def render_variants(
    tokens: list[Token], target_indices: set[int]
) -> tuple[str, str, str]:
    """Return (all_furigana, target_as_kanji, target_as_hiragana)."""
    full: list[str] = []
    kanji: list[str] = []
    kana: list[str] = []

    for token in tokens:
        rendered = render_token(token)
        full.append(rendered)
        if token.index in target_indices:
            kanji.append(token.surface)
            kana.append(token.reading)
        else:
            kanji.append(rendered)
            kana.append(rendered)

    return "".join(full), "".join(kanji), "".join(kana)


def to_anki_html(text: str) -> str:
    """Add invisible span boundaries so Anki's furigana filter behaves.

    Anki's `furigana` filter uses ` ?([^ >]+?)\\[(.+?)\\]`: the ruby base is
    everything since the last space or `>`, with no okurigana handling. In
    plain Japanese text that swallows the preceding particle (the manual's
    own example marks `世[よ]の中[なか]` as incorrect).

    Wrapping each run in a `<span>` gives every `[` a `>` boundary, so the
    reading attaches to exactly the kanji run while the sentence keeps its
    normal spacing and renders identically.

    The input is expected to be HTML-escaped already; only the generated
    `<span>` tags are markup.
    """
    if not text:
        return ""

    out: list[str] = []
    position = 0
    for match in re.finditer(r"([^\[\]]+)\[([^\[\]]+)\]", text):
        before = text[position : match.start()]
        if before:
            out.append(f"<span>{before}</span>")

        base, reading = match.group(1), match.group(2)
        runs = split_runs(base)
        kanji_index = next(
            (i for i in range(len(runs) - 1, -1, -1) if runs[i][0] == "kanji"),
            None,
        )
        if kanji_index is None:
            out.append(f"<span>{base}[{reading}]</span>")
        else:
            prefix = "".join(run_text for _, run_text in runs[:kanji_index])
            core = runs[kanji_index][1]
            suffix = "".join(run_text for _, run_text in runs[kanji_index + 1 :])
            if prefix:
                out.append(f"<span>{prefix}</span>")
            out.append(f"<span>{core}[{reading}]</span>")
            if suffix:
                out.append(f"<span>{suffix}</span>")

        position = match.end()

    tail = text[position:]
    if tail:
        out.append(f"<span>{tail}</span>")
    return "".join(out)
