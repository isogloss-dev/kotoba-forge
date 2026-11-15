"""Build a genanki .apkg from processed cards.

The model id and deck id are fixed in config.toml, so re-importing a
regenerated package updates the existing note type instead of creating
"JP Sentence (jpcard)+1" duplicates.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import genanki

from .config import Config
from .furigana import to_anki_html
from .models import CardRow, ProcessedCard

FIELD_NAMES = [
    "Sentence",
    "SentenceFurigana",
    "SentenceTargetKanji",
    "SentenceTargetKana",
    "StrokeOrder",
    "Target",
    "TargetReading",
    "TargetMeaning",
    "SentenceMeaning",
    "SentenceAudio",
    "WordAudio",
    "Source",
    "Key",
]

DEFAULT_CSS = """
.card {
  font-family: "Yu Mincho", "Hiragino Mincho ProN", "Noto Serif JP", serif;
  font-size: 28px;
  text-align: center;
  color: #1a1a1a;
  background: #fafafa;
  line-height: 2.0;
}
.jp { line-height: 2.1; }
rt { font-size: 0.55em; color: #555; }
.audio { margin-top: 12px; }
.translation { font-size: 20px; color: #333; margin-top: 12px; }
.target { font-size: 22px; margin-top: 10px; }
.meaning { font-size: 18px; color: #555; }
hr#answer { border: 0; border-top: 1px solid #ddd; margin: 16px 0; }
.strokes { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.strokes figure { margin: 0; }
.strokes img { width: 109px; height: 109px; }
.strokes figcaption { font-size: 15px; color: #666; }
.stroke-credit { font-size: 12px; color: #888; margin-top: 6px; }
.stroke-credit a { color: #888; }
.nightMode .strokes img { filter: invert(1); }
"""

DEFAULTS = {
    "card1": (
        '<div class="jp">{{furigana:SentenceFurigana}}</div>\n'
        "{{#SentenceAudio}}<div class=\"audio\">{{SentenceAudio}}</div>{{/SentenceAudio}}",
        "{{FrontSide}}\n<hr id=\"answer\">\n"
        "{{#SentenceMeaning}}<div class=\"translation\">{{SentenceMeaning}}</div>{{/SentenceMeaning}}\n"
        "<div class=\"target\">{{Target}}（{{TargetReading}}）</div>\n"
        "{{#TargetMeaning}}<div class=\"meaning\">{{TargetMeaning}}</div>{{/TargetMeaning}}",
    ),
    "card2": (
        '<div class="jp">{{furigana:SentenceTargetKanji}}</div>',
        "{{FrontSide}}\n<hr id=\"answer\">\n"
        '<div class="jp">{{furigana:SentenceFurigana}}</div>\n'
        "<div class=\"target\">{{Target}}（{{TargetReading}}）</div>\n"
        "{{#TargetMeaning}}<div class=\"meaning\">{{TargetMeaning}}</div>{{/TargetMeaning}}\n"
        "{{#SentenceAudio}}<div class=\"audio\">{{SentenceAudio}}</div>{{/SentenceAudio}}",
    ),
    "card3": (
        '<div class="jp">{{furigana:SentenceTargetKana}}</div>\n'
        "{{#SentenceAudio}}<div class=\"audio\">{{SentenceAudio}}</div>{{/SentenceAudio}}",
        "{{FrontSide}}\n<hr id=\"answer\">\n"
        '<div class="jp">{{furigana:SentenceTargetKanji}}</div>\n'
        "<div class=\"target\">{{Target}}（{{TargetReading}}）</div>\n"
        "{{#TargetMeaning}}<div class=\"meaning\">{{TargetMeaning}}</div>{{/TargetMeaning}}\n"
        "{{StrokeOrder}}\n"
        "{{#StrokeOrder}}<div class=\"stroke-credit\">Stroke order: "
        "<a href=\"https://kanjivg.tagaini.net/\">KanjiVG</a> (CC BY-SA 3.0)</div>{{/StrokeOrder}}",
    ),
}

TEMPLATE_TITLES = [
    ("1 Furigana", "card1"),
    ("2 Target (kanji)", "card2"),
    ("3 Target (hiragana)", "card3"),
]


def _read(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def load_templates(cfg: Config) -> tuple[list[dict], str]:
    directory = cfg.templates_dir
    css = _read(directory / "style.css", DEFAULT_CSS)
    templates = []
    for title, stem in TEMPLATE_TITLES:
        default_front, default_back = DEFAULTS[stem]
        templates.append(
            {
                "name": title,
                "qfmt": _read(directory / f"{stem}_front.html", default_front),
                "afmt": _read(directory / f"{stem}_back.html", default_back),
            }
        )
    return templates, css


# genanki's own req calculation cannot parse Anki's {{furigana:Field}} filter:
# it treats "furigana:Field" as an unknown variable, so every field looks
# required and notes end up with zero cards. We compute req ourselves from the
# plain (non-conditional) field references on the front.
_TAG_RE = re.compile(r"\{\{\s*([#^/]?)([^{}]*?)\s*\}\}")
_FIELD_NAME_RE = re.compile(r"^(?:[A-Za-z]+:)?([A-Za-z0-9_]+)$")


def _front_field_refs(qfmt: str) -> list[str]:
    """Field references on the front, preferring ones outside {{#...}} blocks.

    Optional extras such as audio live in conditionals, and templates may put
    them above the sentence. A conditional reference must never become the
    template's required field, or the card disappears whenever the note has no
    audio.
    """
    unconditional: list[str] = []
    anywhere: list[str] = []
    depth = 0
    for match in _TAG_RE.finditer(qfmt):
        marker, body = match.group(1), match.group(2).strip()
        if marker in ("#", "^"):
            depth += 1
            continue
        if marker == "/":
            depth = max(0, depth - 1)
            continue
        name_match = _FIELD_NAME_RE.match(body)
        if name_match is None:
            continue
        name = name_match.group(1)
        anywhere.append(name)
        if depth == 0:
            unconditional.append(name)
    return unconditional or anywhere


def _required_fields(model: genanki.Model) -> list[list]:
    names = [field["name"] for field in model.fields]
    req: list[list] = []
    for index, template in enumerate(model.templates):
        found: list[int] = []
        for name in _front_field_refs(template["qfmt"]):
            if name in names:
                field_index = names.index(name)
                if field_index not in found:
                    found.append(field_index)
        if not found:
            found = [0]
        # The first plain reference is the prompt field; later ones are
        # usually optional extras inside {{#...}} sections.
        req.append([index, "any", found[:1]])
    return req


def build_model(cfg: Config) -> genanki.Model:
    templates, css = load_templates(cfg)
    model = genanki.Model(
        cfg.model_id,
        cfg.model_name,
        fields=[{"name": name} for name in FIELD_NAMES],
        templates=templates,
        css=css,
    )
    model._req = _required_fields(model)  # type: ignore[attr-defined]
    return model


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _sound(path: Path | None) -> str:
    return f"[sound:{path.name}]" if path is not None else ""


def _field_values(card: ProcessedCard) -> list[str]:
    row = card.row
    return [
        _escape(row.sentence),
        to_anki_html(_escape(card.furigana)),
        to_anki_html(_escape(card.target_kanji)),
        to_anki_html(_escape(card.target_kana)),
        card.stroke_order,
        _escape(row.target),
        _escape(card.target_reading),
        _escape(row.target_meaning),
        _escape(row.sentence_meaning),
        _sound(card.sentence_audio),
        _sound(card.word_audio),
        _escape(row.source),
        card.key,
    ]


def _tag_list(row: CardRow) -> list[str]:
    raw = row.tags.replace(";", ",").replace(",", " ")
    tags = ["jpcard"] + [part for part in raw.split() if part]
    seen: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def build_package(
    cfg: Config, cards: list[ProcessedCard], out_path: Path | None = None
) -> Path:
    destination = Path(out_path) if out_path else cfg.out_apkg
    destination.parent.mkdir(parents=True, exist_ok=True)

    model = build_model(cfg)
    deck = genanki.Deck(cfg.deck_id, cfg.deck_name)
    media: set[Path] = set()

    for card in cards:
        note = genanki.Note(
            model=model,
            fields=_field_values(card),
            tags=_tag_list(card.row),
            guid=genanki.guid_for(card.key),
        )
        deck.add_note(note)
        if card.sentence_audio:
            media.add(card.sentence_audio)
        if card.word_audio:
            media.add(card.word_audio)
        media.update(card.stroke_media)

    package = genanki.Package(deck)
    package.media_files = [str(path) for path in sorted(media)]
    package.write_to_file(str(destination))
    return destination
