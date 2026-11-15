"""Integration test: a one-row batch must yield one note and three cards.

This guards the genanki `_req` workaround: without it, `{{furigana:Field}}`
is misparsed and the package ends up with notes but zero cards.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import genanki

from jpcard.analyze import Analyzer  # noqa: E402
from jpcard.anki import _required_fields, build_model, build_package  # noqa: E402
from jpcard.config import load_config  # noqa: E402
from jpcard.models import CardRow  # noqa: E402
from jpcard.pipeline import run_batch  # noqa: E402

ANKI_FURIGANA = re.compile(r" ?([^ >]+?)\[(.+?)\]")


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analyzer = Analyzer()

    def test_model_requires_one_field_per_template(self) -> None:
        model = build_model(load_config())
        names = [field["name"] for field in model.fields]
        self.assertEqual(len(model._req), 3)
        # The prompt field must be the sentence, never optional audio that a
        # template happens to place first inside {{#SentenceAudio}}.
        expected = ["SentenceFurigana", "SentenceTargetKanji", "SentenceTargetKana"]
        for index, (_, kind, fields) in enumerate(model._req):
            self.assertEqual(kind, "any")
            self.assertEqual(len(fields), 1)
            self.assertEqual(names[fields[0]], expected[index])

    def test_conditional_audio_is_not_a_required_field(self) -> None:
        model = genanki.Model(
            1,
            "conditional",
            fields=[{"name": "Sentence"}, {"name": "SentenceAudio"}],
            templates=[
                {
                    "name": "card",
                    "qfmt": (
                        "{{#SentenceAudio}}{{SentenceAudio}}{{/SentenceAudio}}"
                        "<div>{{furigana:Sentence}}</div>"
                    ),
                    "afmt": "",
                }
            ],
        )
        self.assertEqual(_required_fields(model), [[0, "any", [0]]])

    def test_one_note_three_cards(self) -> None:
        cfg = load_config()
        scratch = Path(__file__).resolve().parents[1] / "out" / "_test_pkg"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            tmp_path = scratch
            cfg.out_apkg = tmp_path / "test.apkg"
            cfg.audio_cache = tmp_path / "audio"

            row = CardRow(
                sentence="昨日は寿司を食べた。",
                target="食べる",
                sentence_meaning="I ate sushi yesterday.",
                target_meaning="to eat",
            )
            cards, errors = run_batch(
                self.analyzer, cfg, [row], tts=None, generate_audio=False, log=lambda *_: None
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(cards), 1)

            package = build_package(cfg, cards)
            self.assertTrue(package.exists())

            with zipfile.ZipFile(package) as archive:
                database = tmp_path / "collection.anki2"
                database.write_bytes(archive.read("collection.anki2"))
                media = json.loads(archive.read("media"))

            connection = sqlite3.connect(database)
            try:
                notes = connection.execute("SELECT count(*) FROM notes").fetchone()[0]
                cards_count = connection.execute("SELECT count(*) FROM cards").fetchone()[0]
                fields = connection.execute("SELECT flds FROM notes").fetchone()[0].split("\x1f")
                models_json = connection.execute("SELECT models FROM col").fetchone()[0]
            finally:
                connection.close()

            model = list(json.loads(models_json).values())[0]
            css = model["css"]
            card3 = [t for t in model["tmpls"] if t["name"].startswith("3 ")][0]

            self.assertEqual(notes, 1)
            self.assertEqual(cards_count, 3)
            self.assertEqual(fields[0], "昨日は寿司を食べた。")
            self.assertEqual(
                ANKI_FURIGANA.findall(fields[1]),
                [("昨日", "きのう"), ("寿司", "すし"), ("食", "た")],
            )
            self.assertEqual(
                ANKI_FURIGANA.findall(fields[2]),
                [("昨日", "きのう"), ("寿司", "すし")],
            )
            self.assertIn("食べた", fields[2])
            self.assertEqual(
                ANKI_FURIGANA.findall(fields[3]),
                [("昨日", "きのう"), ("寿司", "すし")],
            )
            self.assertIn("たべた", fields[3])
            self.assertIn("stroke-toggle", fields[4])
            self.assertIn("kanji_098df.svg", fields[4])
            self.assertIn("kanji_c_098df.svg", fields[4])
            self.assertIn("kanji_098df.svg", media.values())
            self.assertIn("kanji_c_098df.svg", media.values())
            self.assertIn("img.colored", css)
            self.assertIn("show-color", css)
            self.assertNotIn(".strokes .colored", css)
            self.assertIn("show-color", card3["afmt"])
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
