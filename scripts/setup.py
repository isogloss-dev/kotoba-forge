#!/usr/bin/env python3
"""Cross-platform bootstrap for kotoba-forge.

Creates a virtualenv, installs the package, prepares the audio folders,
copies the example CSV to cards.csv on first run, and downloads KanjiVG.

Usage:
    python scripts/setup.py
    python scripts/setup.py --no-venv --no-install --no-kanji
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
ENGINE_URL = "https://github.com/VOICEVOX/voicevox_engine/releases"


def log(message: str = "") -> None:
    print(message, flush=True)


def run(command: list[Path | str]) -> None:
    log("$ " + " ".join(str(part) for part in command))
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True)


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def engine_executable() -> Path | None:
    directory = ROOT / "voices" / "engine"
    names = ("run.exe", "run") if os.name == "nt" else ("run", "run.exe")
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set up kotoba-forge.")
    parser.add_argument("--no-venv", action="store_true", help="install into the current interpreter")
    parser.add_argument("--no-install", action="store_true", help="skip pip install")
    parser.add_argument("--no-kanji", action="store_true", help="skip the KanjiVG download")
    parser.add_argument("--force-kanji", action="store_true", help="re-download KanjiVG")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if sys.version_info < MIN_PYTHON:
        log(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; found {sys.version.split()[0]}")
        return 1

    if args.no_venv:
        python = Path(sys.executable)
        log("Using the current interpreter (--no-venv).")
    else:
        venv = ROOT / ".venv"
        python = venv_python(venv)
        if not python.exists():
            log(f"Creating virtual environment in {venv}")
            try:
                run([sys.executable, "-m", "venv", str(venv)])
            except subprocess.CalledProcessError:
                log("Could not create a virtualenv. On Debian/Ubuntu install python3-venv,")
                log("or rerun with --no-venv.")
                return 1
        else:
            log(f"Reusing virtual environment in {venv}")

    if not args.no_install:
        try:
            run([python, "-m", "pip", "install", "--upgrade", "pip"])
            run([python, "-m", "pip", "install", "-e", str(ROOT)])
        except subprocess.CalledProcessError:
            log("Dependency installation failed. Check the network and pip output above.")
            return 1
    else:
        log("Skipping dependency installation (--no-install).")

    for relative in ("audio/words", "audio/sentences", "out", "voices"):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)

    cards = ROOT / "cards.csv"
    example = ROOT / "cards.example.csv"
    if not cards.exists() and example.exists():
        shutil.copyfile(example, cards)
        log("Created cards.csv from cards.example.csv")

    if not args.no_kanji:
        command: list[Path | str] = [python, ROOT / "run.py", "kanji-setup"]
        if args.force_kanji:
            command.append("--force")
        try:
            run(command)
        except subprocess.CalledProcessError:
            log("KanjiVG download failed; rerun with --no-kanji to skip it for now.")
            return 1
    else:
        log("Skipping KanjiVG (--no-kanji). Stroke order will be empty until you run")
        log(f"  {python} run.py kanji-setup")

    exe = engine_executable()
    if exe is not None:
        log(f"VOICEVOX engine found: {exe}")
    else:
        log("")
        log("VOICEVOX is optional. For generated audio, download the CPU engine for")
        log(f"your platform from {ENGINE_URL}")
        log("and extract it so the launcher is at voices/engine/run.exe (Windows)")
        log("or voices/engine/run (Linux/macOS).")

    log("")
    log("Setup complete. Next:")
    if args.no_venv:
        command_name = "python" if os.name != "nt" else "py"
    else:
        command_name = str(python)
    log(f"  {command_name} run.py batch cards.csv")
    log(f"  {command_name} run.py batch cards.csv --dry-run")
    log(f"  {command_name} run.py voices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
