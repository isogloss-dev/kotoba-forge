"""Audio folder lookup tests (word and sentence naming variants)."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jpcard.audio_lookup import AudioLibrary, normalize_sentence, strip_forvo  # noqa: E402

SCRATCH = Path(__file__).resolve().parents[1] / "out" / "_test_audio"


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not really audio")


class AudioLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        words = SCRATCH / "words"
        sentences = SCRATCH / "sentences"
        touch(words / "pronunciation_ja_食べる.mp3")
        touch(words / "pronunciation_ja_食べる_2.mp3")
        touch(words / "pronunciation_ja_タベル.mp3")
        touch(words / "pronunciation_ja_雑魚.mp3")
        touch(sentences / "昨日は寿司を食べた.mp3")
        touch(sentences / "食べる.mp3")
        cls.lib = AudioLibrary(words, sentences)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def test_prefers_unsuffixed_recording(self) -> None:
        match = self.lib.find_word(["食べる"])
        self.assertIsNotNone(match)
        self.assertEqual(match.path.name, "pronunciation_ja_食べる.mp3")
        self.assertEqual(
            [path.name for path in match.alternatives],
            ["pronunciation_ja_食べる_2.mp3"],
        )

    def test_kana_fold(self) -> None:
        match = self.lib.find_word(["たべる"])
        self.assertIsNotNone(match)
        self.assertEqual(match.path.name, "pronunciation_ja_タベル.mp3")

    def test_exact_word(self) -> None:
        match = self.lib.find_word(["雑魚"])
        self.assertIsNotNone(match)
        self.assertEqual(match.path.name, "pronunciation_ja_雑魚.mp3")

    def test_sentence_named_after_sentence(self) -> None:
        match = self.lib.find_sentence("昨日は寿司を食べた。", "食べる")
        self.assertIsNotNone(match)
        self.assertEqual(match.path.name, "昨日は寿司を食べた.mp3")

    def test_sentence_target_fallback(self) -> None:
        match = self.lib.find_sentence("存在しない文。", "食べる")
        self.assertIsNotNone(match)
        self.assertEqual(match.path.name, "食べる.mp3")

    def test_missing(self) -> None:
        self.assertIsNone(self.lib.find_word(["全くない"]))
        self.assertIsNone(self.lib.find_sentence("全くない。", "全くない"))

    def test_helpers(self) -> None:
        self.assertEqual(strip_forvo("pronunciation_ja_食べる_2"), "食べる")
        self.assertEqual(normalize_sentence("昨日は寿司を食べた。"), "昨日は寿司を食べた")


if __name__ == "__main__":
    unittest.main()
