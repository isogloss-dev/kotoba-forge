"""Command line interface.

  py run.py batch cards.csv
  py run.py batch cards.csv --dry-run
  py run.py one "昨日は寿司を食べた。" 食べる --sentence-meaning "I ate sushi yesterday."
  py run.py voices
  py run.py kanji-setup
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import anki, preview
from .analyze import Analyzer
from .audio_lookup import AudioLibrary
from .config import Config, load_config
from .kanji import setup_kanjivg
from .models import CardRow
from .pipeline import read_rows, run_batch, write_errors
from .tts import TTSError, VoicevoxTTS, check_windows_userdata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jpcard",
        description="Batch Anki sentence cards for Japanese: three furigana variants + local audio.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    batch = sub.add_parser("batch", help="build a deck from a CSV file")
    batch.add_argument("csv", nargs="?", help="input CSV (default: paths.input in config.toml)")
    batch.add_argument("--config", default=None, help="alternate config.toml")
    batch.add_argument("--out", default=None, help="output .apkg path")
    batch.add_argument("--deck", default=None, help="override the deck name")
    batch.add_argument("--tts", choices=["voicevox", "none"], default=None)
    batch.add_argument("--dry-run", action="store_true", help="preview only, no audio or .apkg")
    batch.add_argument("--limit", type=int, default=None, help="process only the first N rows")
    batch.add_argument("--no-audio", action="store_true")

    one = sub.add_parser("one", help="build a single-card .apkg")
    one.add_argument("sentence")
    one.add_argument("target")
    one.add_argument("--sentence-meaning", default="")
    one.add_argument("--target-meaning", default="")
    one.add_argument("--target-reading", default="")
    one.add_argument("--word-audio", default="")
    one.add_argument("--tags", default="")
    one.add_argument("--config", default=None)
    one.add_argument("--tts", choices=["voicevox", "none"], default=None)
    one.add_argument("--no-audio", action="store_true")
    one.add_argument("--dry-run", action="store_true")

    voices = sub.add_parser("voices", help="list VOICEVOX speakers and style ids")
    voices.add_argument("--config", default=None)

    kanji = sub.add_parser(
        "kanji-setup", help="download KanjiVG stroke-order SVGs"
    )
    kanji.add_argument("--force", action="store_true", help="re-download the archive")
    kanji.add_argument("--config", default=None)

    return parser


def _make_tts(cfg: Config, args: argparse.Namespace) -> VoicevoxTTS | None:
    backend = args.tts or cfg.tts_backend
    if getattr(args, "no_audio", False) or backend == "none":
        return None

    warning = check_windows_userdata(cfg.engine_dir)
    if warning:
        print(warning)

    tts = VoicevoxTTS(
        base_url=cfg.voicevox_url,
        engine_dir=cfg.engine_dir,
        speaker=cfg.speaker,
        speed=cfg.speed,
        pitch=cfg.pitch,
        intonation=cfg.intonation,
        sample_rate=cfg.sample_rate,
    )
    try:
        tts.ensure_running()
    except TTSError as exc:
        print(f"! audio disabled: {exc}")
        tts.close()
        return None
    return tts


def _apply_overrides(cfg: Config, args: argparse.Namespace) -> None:
    if getattr(args, "out", None):
        cfg.out_apkg = Path(args.out).resolve()
    if getattr(args, "deck", None):
        cfg.deck_name = args.deck


def _report(cfg: Config, cards, errors, dry_run: bool) -> None:
    out_dir = cfg.out_apkg.parent
    print()
    print(f"cards:  {len(cards)}")
    print(f"errors: {len(errors)}  ({out_dir / 'errors.csv'})")
    if dry_run:
        print("dry run: no .apkg written")
    elif cards:
        print(f"apkg:   {cfg.out_apkg}")
    print(f"preview: {out_dir / 'preview.html'}")


def cmd_batch(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    _apply_overrides(cfg, args)

    input_path = Path(args.csv).resolve() if args.csv else cfg.input_path
    try:
        rows = read_rows(input_path)
    except FileNotFoundError as exc:
        print(f"! {exc}")
        return 2
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("! no rows to process")
        return 2

    analyzer = Analyzer()
    audio_enabled = not args.no_audio
    audio_lib = (
        AudioLibrary(cfg.words_dir, cfg.sentences_dir) if audio_enabled else None
    )
    tts = None if args.dry_run else _make_tts(cfg, args)
    try:
        cards, errors = run_batch(
            analyzer,
            cfg,
            rows,
            tts,
            generate_audio=tts is not None,
            audio_lib=audio_lib,
            audio_enabled=audio_enabled,
        )
    finally:
        if tts is not None:
            tts.close()

    out_dir = cfg.out_apkg.parent
    write_errors(out_dir / "errors.csv", errors)
    preview.build(cards, errors, out_dir / "preview.html", out_dir, dry_run=args.dry_run)

    if not args.dry_run and cards:
        anki.build_package(cfg, cards, cfg.out_apkg)

    _report(cfg, cards, errors, args.dry_run)
    return 0 if cards else 1


def cmd_one(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    row = CardRow(
        sentence=args.sentence,
        target=args.target,
        sentence_meaning=args.sentence_meaning,
        target_meaning=args.target_meaning,
        target_reading=args.target_reading,
        word_audio=args.word_audio,
        tags=args.tags,
        source="cli",
    )

    analyzer = Analyzer()
    audio_enabled = not args.no_audio
    audio_lib = (
        AudioLibrary(cfg.words_dir, cfg.sentences_dir) if audio_enabled else None
    )
    tts = None if args.dry_run else _make_tts(cfg, args)
    try:
        cards, errors = run_batch(
            analyzer,
            cfg,
            [row],
            tts,
            generate_audio=tts is not None,
            audio_lib=audio_lib,
            audio_enabled=audio_enabled,
        )
    finally:
        if tts is not None:
            tts.close()

    out_dir = cfg.out_apkg.parent
    write_errors(out_dir / "one-errors.csv", errors)
    preview.build(
        cards, errors, out_dir / "one-preview.html", out_dir, dry_run=args.dry_run
    )
    if not args.dry_run and cards:
        out_path = out_dir / "one.apkg"
        anki.build_package(cfg, cards, out_path)
        print(f"\napkg: {out_path}")
    print(f"preview: {out_dir / 'one-preview.html'}")
    return 0 if cards else 1


def cmd_voices(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    tts = VoicevoxTTS(
        base_url=cfg.voicevox_url,
        engine_dir=cfg.engine_dir,
        speaker=cfg.speaker,
        speed=cfg.speed,
        pitch=cfg.pitch,
        intonation=cfg.intonation,
        sample_rate=cfg.sample_rate,
    )
    try:
        speakers = tts.speakers()
    except TTSError as exc:
        print(f"! {exc}")
        return 1
    finally:
        tts.close()

    entries = []
    for speaker in speakers:
        for style in speaker.get("styles", []):
            entries.append((int(style["id"]), speaker["name"], style["name"]))
    for style_id, name, style in sorted(entries):
        marker = "  <- config" if style_id == cfg.speaker else ""
        print(f"{style_id:>4}  {name} / {style}{marker}")
    return 0


def cmd_kanji_setup(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    try:
        setup_kanjivg(cfg.root / "data", force=args.force)
    except Exception as exc:  # noqa: BLE001 - surface network/zip errors
        print(f"! {exc}")
        return 1
    print(f"stroke order: {cfg.kanjivg_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "batch":
            return cmd_batch(args)
        if args.command == "one":
            return cmd_one(args)
        if args.command == "voices":
            return cmd_voices(args)
        if args.command == "kanji-setup":
            return cmd_kanji_setup(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
