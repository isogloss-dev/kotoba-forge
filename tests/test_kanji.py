"""Stroke-order tests against the real KanjiVG data when present."""
from __future__ import annotations

import re
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jpcard.kanji import (  # noqa: E402
    build_stroke_order,
    colorize_svg,
    sanitize_svg,
    stroke_color,
    unique_kanji,
)

KANJI_DIR = ROOT / "data" / "kanjivg" / "kanji"
SCRATCH = ROOT / "out" / "_test_kanji"


class KanjiTests(unittest.TestCase):
    def test_unique_kanji_order(self) -> None:
        self.assertEqual(unique_kanji("気に入る"), ["気", "入"])
        self.assertEqual(unique_kanji("食べる"), ["食"])
        self.assertEqual(unique_kanji("コーヒー"), [])
        self.assertEqual(unique_kanji("日々"), ["日", "々"])

    def test_sanitize_strips_prolog_and_comment(self) -> None:
        raw = (
            '<?xml version="1.0"?>\n<!-- licence -->\n'
            '<!DOCTYPE svg [ <!ATTLIST g x CDATA #IMPLIED> ]>\n'
            '<svg><path d="M0 0"/></svg>'
        )
        cleaned = sanitize_svg(raw)
        self.assertTrue(cleaned.startswith("<svg"))
        self.assertTrue(cleaned.endswith("</svg>"))
        self.assertNotIn("<?xml", cleaned)
        self.assertNotIn("<!--", cleaned)

    def test_colorize_strokes_and_numbers(self) -> None:
        raw = (
            '<svg><g id="kvg:StrokePaths_00001">'
            '<path id="kvg:00001-s1" d="M0 0"/>'
            '<path id="kvg:00001-s2" d="M0 0"/>'
            '<path id="kvg:00001-s3" d="M0 0"/>'
            "</g><g id=\"kvg:StrokeNumbers_00001\">"
            '<text transform="matrix(1 0 0 1 1 1)">1</text>'
            '<text transform="matrix(1 0 0 1 2 2)">2</text>'
            '<text transform="matrix(1 0 0 1 3 3)">3</text>'
            "</g></svg>"
        )
        colored = colorize_svg(raw)
        strokes = re.findall(r'stroke="(#[0-9a-f]{6})"', colored)
        fills = re.findall(r'fill="(#[0-9a-f]{6})"', colored)
        self.assertEqual(len(strokes), 3)
        self.assertEqual(len(set(strokes)), 3)
        self.assertEqual(len(fills), 3)

    def test_stroke_colours_are_distinct(self) -> None:
        colors = [stroke_color(index) for index in range(23)]
        self.assertEqual(len(set(colors)), 23)
        self.assertNotEqual(colors[0], colors[1])

    @unittest.skipUnless(
        (KANJI_DIR / "098df.svg").exists(), "KanjiVG data not installed"
    )
    def test_build_stroke_order(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        try:
            result = build_stroke_order("気に入る", KANJI_DIR, SCRATCH)
            self.assertEqual(result.chars, ["気", "入"])
            self.assertIn("kanji_06c17.svg", result.html)
            self.assertIn("kanji_c_06c17.svg", result.html)
            self.assertIn("kanji_c_05165.svg", result.html)
            self.assertIn("stroke-toggle", result.html)
            self.assertEqual(len(result.media), 4)
            names = {path.name for path in result.media}
            self.assertEqual(
                names,
                {
                    "kanji_06c17.svg",
                    "kanji_c_06c17.svg",
                    "kanji_05165.svg",
                    "kanji_c_05165.svg",
                },
            )
            for path in result.media:
                self.assertTrue(path.exists())
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("<svg"))
                self.assertNotIn("<?xml", text)
        finally:
            shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
