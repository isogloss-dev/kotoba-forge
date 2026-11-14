"""Render a standalone preview.html with real ruby markup.

This is the quality gate: it shows the three variants exactly as they will be
stored, plus the token/reading table, before anything is imported into Anki.
"""
from __future__ import annotations

import html
import os
import re
from datetime import datetime
from pathlib import Path

from .models import ErrorRow, ProcessedCard

KANJI_RUN_RE = re.compile(
    r"([\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々〆ヶ]+)\[([^\]]+)\]"
)

CSS = """
:root { color-scheme: light; }
body { margin: 0; padding: 32px; background: #f4f1ea; color: #1c1a17;
       font-family: "Segoe UI", "Yu Gothic UI", system-ui, sans-serif; }
h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: .02em; }
.meta { color: #6b655c; font-size: 13px; margin-bottom: 28px; }
.card { background: #fffdf7; border: 1px solid #e2dccd; border-radius: 10px;
        padding: 22px 26px; margin-bottom: 22px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.card > header { display: flex; align-items: baseline; gap: 10px;
                 border-bottom: 1px solid #eee6d6; padding-bottom: 10px; margin-bottom: 16px; }
.target { font-family: "Yu Mincho", "Noto Serif JP", serif; font-size: 24px; font-weight: 600; }
.reading { color: #8a7f6d; font-size: 14px; }
.variant { margin: 14px 0; }
.label { font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
         color: #9b8f7b; margin-bottom: 4px; }
.jp { font-family: "Yu Mincho", "Hiragino Mincho ProN", "Noto Serif JP", serif;
      font-size: 27px; line-height: 2.25; }
ruby { ruby-position: over; }
rt { font-size: 0.5em; color: #7a6f5d; font-weight: 400; }
.meanings { margin-top: 18px; padding-top: 14px; border-top: 1px dashed #e7dfcf;
            font-size: 14px; color: #4b453b; display: grid; gap: 4px; }
.meanings b { color: #8a7f6d; font-weight: 600; }
.audio { margin-top: 10px; }
audio { height: 30px; }
details { margin-top: 14px; font-size: 13px; color: #57503f; }
summary { cursor: pointer; color: #8a7f6d; }
table { border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { border: 1px solid #e7dfcf; padding: 3px 10px; text-align: left; }
th { background: #f6f1e5; font-weight: 600; }
.warn { margin-top: 10px; color: #9a5b00; font-size: 13px; }
.errors { border-color: #e8c9c9; background: #fff6f6; }
.errors td { border-color: #f0dada; }
.ok { color: #2f6b3a; }
.bad { color: #a33; }
.strokes { display: flex; gap: 10px; justify-content: center; margin-top: 16px; flex-wrap: wrap; }
.strokes figure { margin: 0; background: #fff; border-radius: 8px; padding: 6px; box-shadow: 0 0 0 1px #eee; }
.strokes figure.stroke-toggle { cursor: pointer; }
.strokes img.colored { display: none; }
.strokes figure.stroke-toggle.show-color img.plain { display: none; }
.strokes figure.stroke-toggle.show-color img.colored { display: inline; }
.strokes img { width: 96px; height: 96px; user-select: none; }
.strokes figcaption { font-size: 13px; color: #8a7f6d; }
.stroke-credit { text-align: center; font-size: 11px; color: #9b8f7b; margin-top: 4px; }
.src { font-size: 11px; color: #8a7f6d; margin-left: 8px; }
"""


def to_ruby(text: str) -> str:
    escaped = html.escape(text, quote=False)
    return KANJI_RUN_RE.sub(r"<ruby>\1<rt>\2</rt></ruby>", escaped)


def _audio_tag(path: Path | None, out_dir: Path, source: str) -> str:
    labels = {
        "csv": "from CSV path",
        "folder": "from audio folder",
        "tts": "generated",
        "none": "none",
    }
    label = labels.get(source, source)
    if path is None or not path.exists():
        return f'<span class="meta">audio: {html.escape(label)}</span>'
    try:
        relative = os.path.relpath(path, out_dir).replace("\\", "/")
    except ValueError:
        relative = path.name
    return (
        f'<audio controls preload="none" src="{html.escape(relative)}"></audio>'
        f'<span class="src">{html.escape(label)}</span>'
    )


def build(
    cards: list[ProcessedCard],
    errors: list[ErrorRow],
    path: Path,
    out_dir: Path,
    dry_run: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="ja"><head><meta charset="utf-8">',
        "<title>jpcard preview</title>",
        f"<style>{CSS}</style></head><body>",
        "<h1>jpcard preview</h1>",
        (
            f'<div class="meta">{len(cards)} card(s), {len(errors)} error row(s) '
            f"&middot; {datetime.now():%Y-%m-%d %H:%M}"
            + (" &middot; dry run" if dry_run else "")
            + "</div>"
        ),
    ]

    if errors:
        parts.append('<div class="card errors"><header><span class="target">Errors</span></header>')
        parts.append("<table><tr><th>row</th><th>sentence</th><th>target</th><th>reason</th></tr>")
        for error in errors:
            parts.append(
                "<tr>"
                f"<td>{error.row_number}</td>"
                f"<td>{html.escape(error.sentence)}</td>"
                f"<td>{html.escape(error.target)}</td>"
                f"<td>{html.escape(error.error)}</td>"
                "</tr>"
            )
        parts.append("</table></div>")

    for card in cards:
        row = card.row
        parts.append('<section class="card">')
        parts.append(
            "<header>"
            f'<span class="target">{html.escape(row.target)}</span>'
            f'<span class="reading">{html.escape(card.target_reading)}</span>'
            "</header>"
        )
        variants = [
            ("1 &middot; all furigana", card.furigana),
            ("2 &middot; target as kanji", card.target_kanji),
            ("3 &middot; target as hiragana", card.target_kana),
        ]
        for label, text in variants:
            parts.append(
                '<div class="variant">'
                f'<div class="label">{label}</div>'
                f'<div class="jp">{to_ruby(text)}</div>'
                "</div>"
            )

        parts.append('<div class="meanings">')
        if row.sentence_meaning:
            parts.append(f"<div><b>sentence</b> {html.escape(row.sentence_meaning)}</div>")
        if row.target_meaning:
            parts.append(f"<div><b>target</b> {html.escape(row.target_meaning)}</div>")
        parts.append(f'<div class="audio">{_audio_tag(card.sentence_audio, out_dir, card.sentence_audio_source)}</div>')
        if card.word_audio:
            parts.append(f'<div class="audio">{_audio_tag(card.word_audio, out_dir, card.word_audio_source)}</div>')
        parts.append("</div>")

        if card.stroke_chars:
            figures = "".join(
                '<figure class="stroke-toggle" role="button" tabindex="0" '
                'title="Click to colour the strokes">'
                f'<img class="plain" src="kanji/kanji_{ord(char):05x}.svg" alt="{char}">'
                f'<img class="colored" src="kanji/kanji_c_{ord(char):05x}.svg" '
                f'alt="{char} (coloured strokes)">'
                f"<figcaption>{char}</figcaption></figure>"
                for char in card.stroke_chars
            )
            parts.append(f'<div class="strokes">{figures}</div>')
            parts.append(
                '<div class="stroke-credit">Stroke order: KanjiVG (CC BY-SA 3.0)</div>'
            )

        if card.warnings:
            for warning in card.warnings:
                parts.append(f'<div class="warn">! {html.escape(warning)}</div>')

        parts.append("<details><summary>tokens &amp; readings</summary><table>")
        parts.append("<tr><th>#</th><th>surface</th><th>reading</th><th>lemma</th><th>pos</th></tr>")
        for token in card.tokens:
            marker = ' class="ok"' if token.has_kanji else ""
            parts.append(
                f"<tr{marker}><td>{token.index}</td><td>{html.escape(token.surface)}</td>"
                f"<td>{html.escape(token.reading)}</td><td>{html.escape(token.lemma)}</td>"
                f"<td>{html.escape(token.pos)}</td></tr>"
            )
        parts.append("</table></details>")
        parts.append("</section>")

    parts.append("</body></html>")
    parts.insert(
        -1,
        """
<script>
(function () {
  var figures = document.querySelectorAll(".stroke-toggle");
  for (var i = 0; i < figures.length; i++) {
    (function (figure) {
      figure.addEventListener("click", function () {
        figure.classList.toggle("show-color");
      });
    })(figures[i]);
  }
})();
</script>
""",
    )
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
