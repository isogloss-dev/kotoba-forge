"""Find audio dropped into project folders.

Lookup order in the pipeline is: explicit CSV path -> folder match -> TTS.

Words follow Forvo's naming (`pronunciation_ja_食べる.mp3`) but plain
`食べる.mp3` also works. Sentence files should be named after the sentence
(trailing punctuation optional); naming one after the target word is accepted
as a fallback.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import jaconv

AUDIO_EXTS = {
    ".mp3",
    ".ogg",
    ".oga",
    ".wav",
    ".m4a",
    ".opus",
    ".flac",
    ".aac",
    ".webm",
}

_FORVO_PREFIX = "pronunciation_ja_"
_SUFFIX_RE = re.compile(r"(?:[_\-\s]\(?\d+\)?|\(\d+\))$")
_TRAILING_PUNCT_RE = re.compile(r"[。．.!?！？、,，]+$")


def normalize_key(text: str) -> str:
    text = urllib.parse.unquote(text)
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", "", text).strip()


def strip_forvo(stem: str) -> str:
    if stem.lower().startswith(_FORVO_PREFIX):
        stem = stem[len(_FORVO_PREFIX) :]
    while True:
        stripped = _SUFFIX_RE.sub("", stem)
        if stripped == stem:
            break
        stem = stripped
    return stem


def normalize_sentence(text: str) -> str:
    return _TRAILING_PUNCT_RE.sub("", normalize_key(text))


def _suffix_rank(path: Path) -> int:
    return 1 if _SUFFIX_RE.search(path.stem) else 0


def _sort_key(path: Path) -> tuple:
    return (_suffix_rank(path), len(path.name), path.name)


@dataclass
class AudioMatch:
    path: Path
    key: str
    alternatives: list[Path] = field(default_factory=list)


class AudioLibrary:
    """Index of audio files in the words/ and sentences/ folders."""

    def __init__(self, words_dir: Path | None, sentences_dir: Path | None) -> None:
        self.words = self._index(Path(words_dir) if words_dir else None, sentence=False)
        self.words_folded = self._fold(self.words)
        self.sentences = self._index(
            Path(sentences_dir) if sentences_dir else None, sentence=True
        )
        self.sentences_folded = self._fold(self.sentences)

    def _index(self, directory: Path | None, sentence: bool) -> dict[str, list[Path]]:
        table: dict[str, list[Path]] = {}
        if directory is None or not directory.exists():
            return table

        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue
            stems = {path.stem, strip_forvo(path.stem)}
            for stem in stems:
                keys = {normalize_key(stem)}
                if sentence:
                    keys.add(normalize_sentence(stem))
                for key in keys:
                    if key:
                        table.setdefault(key, []).append(path)
        return table

    def _fold(self, table: dict[str, list[Path]]) -> dict[str, list[Path]]:
        folded: dict[str, list[Path]] = {}
        for key, paths in table.items():
            folded.setdefault(jaconv.kata2hira(key), []).extend(paths)
        return folded

    def _pick(self, paths: list[Path], key: str) -> AudioMatch:
        ordered = sorted(set(paths), key=_sort_key)
        return AudioMatch(ordered[0], key, ordered[1:])

    def _find(
        self,
        table: dict[str, list[Path]],
        folded: dict[str, list[Path]],
        keys: list[str],
    ) -> AudioMatch | None:
        for key in keys:
            if key in table:
                return self._pick(table[key], key)
        for key in keys:
            folded_key = jaconv.kata2hira(key)
            if folded_key in folded:
                return self._pick(folded[folded_key], folded_key)
        return None

    def find_word(self, candidates: list[str]) -> AudioMatch | None:
        keys = [normalize_key(strip_forvo(value)) for value in candidates if value]
        keys = [key for key in keys if key]
        return self._find(self.words, self.words_folded, keys)

    def find_sentence(self, sentence: str, target: str = "") -> AudioMatch | None:
        keys = [normalize_key(sentence), normalize_sentence(sentence)]
        if target:
            keys.append(normalize_key(strip_forvo(target)))
        keys = [key for key in keys if key]
        return self._find(self.sentences, self.sentences_folded, keys)
