"""Golden tests for furigana alignment, target matching and the three variants.

Run with:  py -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jpcard.analyze import Analyzer  # noqa: E402
from jpcard.furigana import (  # noqa: E402
    align,
    render_variants,
    strip_brackets,
    to_anki_html,
)
from jpcard.target import TargetNotFound, dictionary_reading, find_spans  # noqa: E402

# Anki's actual filter, copied from rslib/src/template_filters.rs.
ANKI_FURIGANA = re.compile(r" ?([^ >]+?)\[(.+?)\]")


class FuriganaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analyzer = Analyzer()

    def variants(self, sentence: str, target: str):
        tokens = self.analyzer.tokenize(sentence)
        spans = find_spans(tokens, target)
        indices = {i for span in spans for i in range(span.start, span.end)}
        return render_variants(tokens, indices), tokens

    def test_align_okurigana(self) -> None:
        self.assertEqual(
            align("食べる", "たべる"),
            [("食", "た"), ("べる", None)],
        )

    def test_align_all_kanji(self) -> None:
        self.assertEqual(align("大人", "おとな"), [("大人", "おとな")])

    def test_align_leading_kana(self) -> None:
        self.assertEqual(
            align("お菓子", "おかし"),
            [("お", None), ("菓子", "かし")],
        )

    def test_align_mixed_runs(self) -> None:
        self.assertEqual(
            align("食べ物", "たべもの"),
            [("食", "た"), ("べ", None), ("物", "もの")],
        )

    def test_inflected_target(self) -> None:
        (full, kanji, kana), _ = self.variants("昨日は寿司を食べた。", "食べる")
        self.assertEqual(full, "昨日[きのう]は寿司[すし]を食[た]べた。")
        self.assertEqual(kanji, "昨日[きのう]は寿司[すし]を食べた。")
        self.assertEqual(kana, "昨日[きのう]は寿司[すし]をたべた。")

    def test_leading_kana_target(self) -> None:
        (full, kanji, kana), _ = self.variants("お菓子が好きだ。", "お菓子")
        self.assertEqual(full, "お菓子[かし]が好[す]きだ。")
        self.assertEqual(kanji, "お菓子が好[す]きだ。")
        self.assertEqual(kana, "おかしが好[す]きだ。")

    def test_number_counter(self) -> None:
        (full, _, _), _ = self.variants("三人で映画を見た。", "映画")
        self.assertEqual(full, "三[さん]人[にん]で映画[えいが]を見[み]た。")

    def test_multi_token_target(self) -> None:
        (full, kanji, kana), _ = self.variants("彼はその仕事を気に入った。", "気に入る")
        self.assertEqual(kanji, "彼[かれ]はその仕事[しごと]を気に入った。")
        self.assertIn("きにいった", kana)
        self.assertIn("気[き]", full)
        self.assertIn("入[い]", full)

    def test_katakana_left_alone(self) -> None:
        (full, _, kana), _ = self.variants("コーヒーを飲みながら本を読む。", "読む")
        self.assertEqual(full, "コーヒーを飲[の]みながら本[ほん]を読[よ]む。")
        self.assertIn("コーヒー", kana)

    def test_reconstruction(self) -> None:
        sentence = "雨が降っている。"
        (full, kanji, _), _ = self.variants(sentence, "降る")
        self.assertEqual(strip_brackets(full), sentence)
        self.assertEqual(strip_brackets(kanji), sentence)

    def test_target_not_found(self) -> None:
        tokens = self.analyzer.tokenize("雨が降っている。")
        with self.assertRaises(TargetNotFound):
            find_spans(tokens, "食べる")

    def test_dictionary_reading(self) -> None:
        self.assertEqual(dictionary_reading(self.analyzer, "食べる"), "たべる")
        self.assertEqual(dictionary_reading(self.analyzer, "気に入る"), "きにいる")

    def test_anki_boundaries_plain_sentence(self) -> None:
        html = to_anki_html("昨日[きのう]は寿司[すし]を食[た]べた。")
        self.assertEqual(
            ANKI_FURIGANA.findall(html),
            [("昨日", "きのう"), ("寿司", "すし"), ("食", "た")],
        )

    def test_anki_boundaries_leading_kana(self) -> None:
        html = to_anki_html("お菓子[かし]が好[す]きだ。")
        self.assertEqual(
            ANKI_FURIGANA.findall(html),
            [("菓子", "かし"), ("好", "す")],
        )

    def test_anki_boundaries_mixed_runs(self) -> None:
        html = to_anki_html("食[た]べ物[もの]を買[か]った。")
        self.assertEqual(
            ANKI_FURIGANA.findall(html),
            [("食", "た"), ("物", "もの"), ("買", "か")],
        )


if __name__ == "__main__":
    unittest.main()
