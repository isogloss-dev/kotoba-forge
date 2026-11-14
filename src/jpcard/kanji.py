"""KanjiVG stroke-order diagrams.

KanjiVG ships one SVG per kanji, named by Unicode codepoint, with the stroke
paths in order and numbered readings already included. The SVGs are licensed
CC BY-SA 3.0; the card template carries the attribution.

For every kanji we emit two files: the plain diagram and a colour-coded copy
where each stroke gets its own hue (golden-angle spacing, alternating
lightness) and the matching number is tinted to match. The card template
swaps between them on click.
"""
from __future__ import annotations

import colorsys
import re
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .analyze import is_kanji

KANJIVG_VERSION = "r20260714"
KANJIVG_URL = (
    "https://github.com/KanjiVG/kanjivg/releases/download/"
    f"{KANJIVG_VERSION}/kanjivg-20260714-main.zip"
)

_PATH_TAG_RE = re.compile(r"<path\b[^>]*>")
_PATH_ID_RE = re.compile(r'id="kvg:[0-9a-fA-F]+-s(\d+)"')
_TEXT_RE = re.compile(r"<text\b([^>]*)>(\d+)</text>")
_NUMBERS_GROUP_RE = re.compile(
    r'(<g id="kvg:StrokeNumbers_[^"]*"[^>]*>)(.*?)(</g>)', re.DOTALL
)


def setup_kanjivg(
    data_dir: Path,
    force: bool = False,
    url: str = KANJIVG_URL,
    log=print,
) -> int:
    """Download and extract KanjiVG into data_dir/kanjivg/kanji."""
    data_dir = Path(data_dir)
    kanji_dir = data_dir / "kanjivg" / "kanji"
    zip_path = data_dir / "kanjivg-main.zip"
    data_dir.mkdir(parents=True, exist_ok=True)

    if force or not zip_path.exists() or zip_path.stat().st_size < 1_000_000:
        log(f"downloading KanjiVG ({KANJIVG_VERSION}) ...")
        request = urllib.request.Request(url, headers={"User-Agent": "jpcard/0.1"})
        with urllib.request.urlopen(request, timeout=120) as response, open(
            zip_path, "wb"
        ) as handle:
            shutil.copyfileobj(response, handle)
        log(f"saved {zip_path} ({zip_path.stat().st_size / 1_000_000:.1f} MB)")

    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        zip_path.unlink(missing_ok=True)
        return setup_kanjivg(data_dir, force=True, url=url, log=log)

    kanji_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with archive:
        for name in archive.namelist():
            if name.startswith("kanji/") and name.endswith(".svg"):
                (kanji_dir / name.rsplit("/", 1)[-1]).write_bytes(
                    archive.read(name)
                )
                count += 1
    log(f"KanjiVG: {count} SVGs in {kanji_dir}")
    return count


def unique_kanji(text: str) -> list[str]:
    """Unique kanji in first-appearance order; kana and punctuation skipped."""
    seen: set[str] = set()
    result: list[str] = []
    for char in text:
        if is_kanji(char) and char not in seen:
            seen.add(char)
            result.append(char)
    return result


def sanitize_svg(text: str) -> str:
    """Drop the XML prolog, licence comment and doctype before shipping.

    Some embedded browsers are unhappy with KanjiVG's internal DTD subset;
    the remaining <svg> element is plain XML.
    """
    start = text.find("<svg")
    end = text.rfind("</svg>")
    if start < 0 or end < 0:
        return text
    return text[start : end + len("</svg>")]


def stroke_color(index: int) -> str:
    """Distinct colour per stroke; no fixed palette length."""
    hue = ((index * 137.508) % 360.0) / 360.0
    lightness = 0.38 if index % 2 == 0 else 0.46
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, 0.72)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def number_color(index: int) -> str:
    """Darker version of the stroke colour, for the small number text."""
    hue = ((index * 137.508) % 360.0) / 360.0
    lightness = 0.24 if index % 2 == 0 else 0.30
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, 0.78)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def colorize_svg(text: str) -> str:
    """Colour each KanjiVG stroke and its number, leaving geometry untouched."""
    if "<svg" not in text:
        return text

    def path_replacement(match: re.Match[str]) -> str:
        tag = match.group(0)
        id_match = _PATH_ID_RE.search(tag)
        if id_match is None or 'stroke="' in tag:
            return tag
        color = stroke_color(int(id_match.group(1)) - 1)
        self_closing = tag.rstrip().endswith("/>")
        closing = "/>" if self_closing else ">"
        body = tag.rstrip()[: -len(closing)].rstrip()
        return f'{body} stroke="{color}"{closing}'

    def text_replacement(match: re.Match[str]) -> str:
        attrs, number = match.group(1), match.group(2)
        if 'fill="' in attrs:
            return match.group(0)
        color = number_color(int(number) - 1)
        return f'<text{attrs} fill="{color}">{number}</text>'

    def numbers_replacement(match: re.Match[str]) -> str:
        opening, body, closing = match.group(1), match.group(2), match.group(3)
        return opening + _TEXT_RE.sub(text_replacement, body) + closing

    text = _NUMBERS_GROUP_RE.sub(numbers_replacement, text)
    return _PATH_TAG_RE.sub(path_replacement, text)


def _write_if_changed(path: Path, content: str) -> None:
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


@dataclass
class StrokeOrderResult:
    html: str = ""
    media: list[Path] = field(default_factory=list)
    chars: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_stroke_order(
    target: str,
    kanji_dir: Path,
    out_dir: Path,
) -> StrokeOrderResult:
    """Create the StrokeOrder field HTML and the two SVGs per kanji."""
    kanji_dir = Path(kanji_dir)
    out_dir = Path(out_dir)
    result = StrokeOrderResult()

    chars = unique_kanji(target)
    if not chars:
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    figures: list[str] = []

    for char in chars:
        source = kanji_dir / f"{ord(char):05x}.svg"
        if not source.exists():
            result.warnings.append(f"no KanjiVG diagram for {char}")
            continue

        plain = sanitize_svg(source.read_text(encoding="utf-8"))
        colored = colorize_svg(plain)

        plain_path = out_dir / f"kanji_{ord(char):05x}.svg"
        colored_path = out_dir / f"kanji_c_{ord(char):05x}.svg"
        _write_if_changed(plain_path, plain)
        _write_if_changed(colored_path, colored)

        figures.append(
            '<figure class="stroke-toggle" role="button" tabindex="0" '
            'title="Click to colour the strokes">'
            f'<img class="plain" src="{plain_path.name}" alt="{char}">'
            f'<img class="colored" src="{colored_path.name}" '
            f'alt="{char} (coloured strokes)">'
            f"<figcaption>{char}</figcaption></figure>"
        )
        result.media.extend([plain_path, colored_path])
        result.chars.append(char)

    if figures:
        result.html = '<div class="strokes">' + "".join(figures) + "</div>"
    return result
