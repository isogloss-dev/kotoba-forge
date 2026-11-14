"""Batch pipeline: CSV rows -> processed cards + error rows.

Audio priority: explicit CSV path -> file found in audio/words or
audio/sentences -> VOICEVOX synthesis.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path

from .analyze import AnalysisError, Analyzer
from .audio_lookup import AudioLibrary
from .config import Config
from .furigana import alignment_failed, render_variants, strip_brackets
from .kanji import build_stroke_order
from .models import CardRow, ErrorRow, ProcessedCard
from .target import TargetNotFound, dictionary_reading, find_spans
from .tts import TTSError, VoicevoxTTS

CSV_COLUMNS = [
    "sentence",
    "target",
    "sentence_meaning",
    "target_meaning",
    "target_reading",
    "word_audio",
    "sentence_audio",
    "tags",
    "source",
]


def read_rows(path: Path) -> list[CardRow]:
    if not path.exists():
        raise FileNotFoundError(f"input CSV not found: {path}")

    rows: list[CardRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        for raw in reader:
            clean = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in raw.items()
            }
            sentence = clean.get("sentence", "")
            target = clean.get("target", "")
            if not sentence and not target:
                continue
            rows.append(
                CardRow(
                    sentence=sentence,
                    target=target,
                    sentence_meaning=clean.get("sentence_meaning")
                    or clean.get("translation", ""),
                    target_meaning=clean.get("target_meaning", ""),
                    target_reading=clean.get("target_reading", ""),
                    word_audio=clean.get("word_audio", ""),
                    sentence_audio=clean.get("sentence_audio", ""),
                    tags=clean.get("tags", ""),
                    source=clean.get("source", ""),
                )
            )
    return rows


def _cache_name(text: str, cfg: Config) -> str:
    payload = "\x1f".join(
        [
            text,
            str(cfg.speaker),
            str(cfg.speed),
            str(cfg.pitch),
            str(cfg.intonation),
            str(cfg.sample_rate),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _synthesize(tts: VoicevoxTTS, cfg: Config, text: str, prefix: str) -> Path:
    path = cfg.audio_cache / f"{prefix}_{_cache_name(text, cfg)}.wav"
    if path.exists() and path.stat().st_size > 0:
        return path
    return tts.synthesize(text, path)


def _import_media(cfg: Config, source: Path, prefix: str) -> Path:
    digest = hashlib.sha1(source.read_bytes()).hexdigest()[:16]
    suffix = source.suffix.lower() or ".wav"
    destination = cfg.audio_cache / f"{prefix}_{digest}{suffix}"
    if not destination.exists():
        cfg.audio_cache.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return destination


def _resolve_input(cfg: Config, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (cfg.root / path)


def process_row(
    analyzer: Analyzer,
    cfg: Config,
    row: CardRow,
    tts: VoicevoxTTS | None = None,
    generate_audio: bool = False,
    audio_lib: AudioLibrary | None = None,
    audio_enabled: bool = True,
) -> ProcessedCard:
    tokens = analyzer.tokenize(row.sentence)
    spans = find_spans(tokens, row.target)
    indices = {i for span in spans for i in range(span.start, span.end)}
    full, target_kanji, target_kana = render_variants(tokens, indices)

    reading = row.target_reading.strip()
    if not reading:
        try:
            reading = dictionary_reading(analyzer, row.target)
        except Exception:  # noqa: BLE001 - reading is optional
            reading = ""

    warnings: list[str] = []
    for token in tokens:
        if alignment_failed(token):
            warnings.append(
                f"furigana fallback for {token.surface!r} (reading {token.reading!r})"
            )
    if strip_brackets(full) != row.sentence:
        warnings.append("variant 1 does not reconstruct the sentence")
    if strip_brackets(target_kanji) != row.sentence:
        warnings.append("variant 2 does not reconstruct the sentence")

    stroke = build_stroke_order(
        row.target, cfg.kanjivg_dir, cfg.out_apkg.parent / "kanji"
    )
    warnings.extend(stroke.warnings)

    card = ProcessedCard(
        row=row,
        tokens=tokens,
        spans=spans,
        furigana=full,
        target_kanji=target_kanji,
        target_kana=target_kana,
        target_reading=reading,
        key=row.key,
        stroke_order=stroke.html,
        stroke_media=stroke.media,
        stroke_chars=stroke.chars,
        warnings=warnings,
    )

    lemma = "".join(
        token.lemma for span in spans for token in tokens[span.start : span.end]
    )

    if not audio_enabled:
        return card

    # -- word audio: CSV path -> folder -> TTS --------------------------
    if row.word_audio:
        candidate = _resolve_input(cfg, row.word_audio)
        if candidate.exists():
            card.word_audio = _import_media(cfg, candidate, "wv")
            card.word_audio_source = "csv"
        else:
            warnings.append(f"word_audio path not found: {candidate}")

    if card.word_audio is None and audio_lib is not None:
        match = audio_lib.find_word([row.target, lemma, reading])
        if match is not None:
            card.word_audio = _import_media(cfg, match.path, "wv")
            card.word_audio_source = "folder"
            if match.alternatives:
                warnings.append(
                    f"word audio: {len(match.alternatives)} other recording(s) available"
                )

    if (
        card.word_audio is None
        and generate_audio
        and tts is not None
        and cfg.word_fallback
    ):
        try:
            card.word_audio = _synthesize(tts, cfg, row.target, "wv")
            card.word_audio_source = "tts"
        except TTSError as exc:
            warnings.append(f"word audio failed: {exc}")

    # -- sentence audio: CSV path -> folder -> TTS ----------------------
    if row.sentence_audio:
        candidate = _resolve_input(cfg, row.sentence_audio)
        if candidate.exists():
            card.sentence_audio = _import_media(cfg, candidate, "sv")
            card.sentence_audio_source = "csv"
        else:
            warnings.append(f"sentence_audio path not found: {candidate}")

    if card.sentence_audio is None and audio_lib is not None:
        match = audio_lib.find_sentence(row.sentence, row.target)
        if match is not None:
            card.sentence_audio = _import_media(cfg, match.path, "sv")
            card.sentence_audio_source = "folder"
            if match.alternatives:
                warnings.append(
                    f"sentence audio: {len(match.alternatives)} other recording(s) available"
                )

    if card.sentence_audio is None and generate_audio and tts is not None:
        try:
            card.sentence_audio = _synthesize(tts, cfg, row.sentence, "sv")
            card.sentence_audio_source = "tts"
        except TTSError as exc:
            warnings.append(f"sentence audio failed: {exc}")

    return card


def _token_listing(tokens) -> str:
    parts = []
    for token in tokens:
        if token.reading and token.reading != token.surface:
            parts.append(f"{token.surface}({token.reading})")
        else:
            parts.append(token.surface)
    return " ".join(parts)


def run_batch(
    analyzer: Analyzer,
    cfg: Config,
    rows: list[CardRow],
    tts: VoicevoxTTS | None = None,
    generate_audio: bool = False,
    audio_lib: AudioLibrary | None = None,
    audio_enabled: bool = True,
    log=print,
) -> tuple[list[ProcessedCard], list[ErrorRow]]:
    cards: list[ProcessedCard] = []
    errors: list[ErrorRow] = []

    for offset, row in enumerate(rows):
        number = offset + 2  # header is row 1
        if not row.sentence or not row.target:
            errors.append(
                ErrorRow(number, row.sentence, row.target, "missing sentence or target")
            )
            log(f"[skip] row {number}: missing sentence or target")
            continue
        try:
            card = process_row(
                analyzer,
                cfg,
                row,
                tts,
                generate_audio,
                audio_lib=audio_lib,
                audio_enabled=audio_enabled,
            )
        except TargetNotFound as exc:
            errors.append(
                ErrorRow(number, row.sentence, row.target, str(exc), _token_listing(exc.tokens))
            )
            log(f"[skip] row {number}: target not found: {row.target}")
        except AnalysisError as exc:
            errors.append(ErrorRow(number, row.sentence, row.target, str(exc)))
            log(f"[skip] row {number}: analysis failed")
        except Exception as exc:  # noqa: BLE001 - one bad row must not kill a run
            errors.append(
                ErrorRow(number, row.sentence, row.target, f"{type(exc).__name__}: {exc}")
            )
            log(f"[skip] row {number}: {type(exc).__name__}: {exc}")
        else:
            cards.append(card)
            log(f"[ok]   row {number}: {row.target}  ->  {card.furigana}")

    return cards, errors


def write_errors(path: Path, errors: list[ErrorRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "sentence", "target", "error", "tokens"])
        for error in errors:
            writer.writerow(
                [error.row_number, error.sentence, error.target, error.error, error.tokens]
            )
    return path
