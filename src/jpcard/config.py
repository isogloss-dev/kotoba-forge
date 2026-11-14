"""Configuration loading (TOML, stdlib tomllib)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    root: Path
    deck_name: str
    model_name: str
    model_id: int
    deck_id: int
    input_path: Path
    out_apkg: Path
    audio_cache: Path
    templates_dir: Path
    words_dir: Path
    sentences_dir: Path
    kanjivg_dir: Path
    tts_backend: str
    voicevox_url: str
    engine_dir: Path
    speaker: int
    speed: float
    pitch: float
    intonation: float
    sample_rate: int
    word_fallback: bool


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path)


def load_config(path: str | Path | None = None) -> Config:
    config_path = Path(path) if path else (ROOT / "config.toml")
    base = config_path.parent
    data: dict = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    deck = data.get("deck", {})
    paths = data.get("paths", {})
    tts = data.get("tts", {})
    audio = data.get("audio", {})
    kanji = data.get("kanji", {})

    return Config(
        root=base,
        deck_name=deck.get("name", "Japanese::Sentences"),
        model_name=deck.get("model_name", "JP Sentence (kotoba-forge)"),
        model_id=int(deck.get("model_id", 1734567890123)),
        deck_id=int(deck.get("deck_id", 1734567890456)),
        input_path=_resolve(base, paths.get("input", "cards.csv")),
        out_apkg=_resolve(base, paths.get("out_apkg", "out/kotoba-forge.apkg")),
        audio_cache=_resolve(base, paths.get("audio_cache", "out/audio")),
        templates_dir=_resolve(base, paths.get("templates", "templates")),
        words_dir=_resolve(base, audio.get("words_dir", "audio/words")),
        sentences_dir=_resolve(base, audio.get("sentences_dir", "audio/sentences")),
        kanjivg_dir=_resolve(base, kanji.get("dir", "data/kanjivg/kanji")),
        tts_backend=str(tts.get("backend", "voicevox")),
        voicevox_url=str(tts.get("voicevox_url", "http://127.0.0.1:50021")),
        engine_dir=_resolve(base, tts.get("engine_dir", "voices/engine")),
        speaker=int(tts.get("speaker", 3)),
        speed=float(tts.get("speed", 0.95)),
        pitch=float(tts.get("pitch", 0.0)),
        intonation=float(tts.get("intonation", 1.0)),
        sample_rate=int(tts.get("sample_rate", 24000)),
        word_fallback=bool(tts.get("word_fallback", True)),
    )
