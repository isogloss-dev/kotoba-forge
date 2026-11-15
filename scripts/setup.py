#!/usr/bin/env python3
"""Cross-platform bootstrap for kotoba-forge.

Creates a virtualenv, installs the package, prepares the audio folders,
copies the example CSV to cards.csv on first run, and downloads KanjiVG.

Usage:
    python3 scripts/setup.py
    python3 scripts/setup.py --no-venv --no-install --no-kanji
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


def has_pip(python: Path) -> bool:
    """True when the interpreter can actually run pip."""
    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "--version"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def bootstrap_pip(python: Path) -> bool:
    """Try to install pip into an existing environment with ensurepip."""
    log(f"pip is missing from {python}; trying ensurepip ...")
    try:
        run([python, "-m", "ensurepip", "--upgrade", "--default-pip"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return has_pip(python)


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
        log("Install a newer Python and run this script with it, for example:")
        log(f"  python3.{MIN_PYTHON[1]} scripts/setup.py")
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
                log("Could not create a virtualenv (the venv/ensurepip module may be missing).")
                log("On Debian/Ubuntu: sudo apt install python3-venv")
                log("If a partial .venv was left behind, remove it before rerunning:")
                log("  rm -rf .venv")
                log("(Rerunning with --no-venv installs into the current interpreter,")
                log("which some distributions block under PEP 668.)")
                return 1
        else:
            log(f"Reusing virtual environment in {venv}")

    if not args.no_install and not has_pip(python):
        if bootstrap_pip(python):
            log("pip installed.")
        else:
            log("")
            log(f"{python} exists but has no working pip.")
            if args.no_venv:
                log("Install pip for this interpreter (Debian/Ubuntu: sudo apt install python3-pip),")
                log("or omit --no-venv to use a project virtualenv.")
            else:
                log("The virtualenv is incomplete. This usually happens when the Python")
                log("that created it had no ensurepip/venv support.")
                log("On Debian/Ubuntu install the venv package for this interpreter, e.g.:")
                log("  sudo apt install python3-venv      # or python3.12-venv")
                log("Then remove the broken environment and run setup again:")
                log(f"  rm -rf {ROOT / '.venv'}")
            return 1

    if not args.no_install:
        try:
            run([python, "-m", "pip", "install", "--upgrade", "pip"])
            run([python, "-m", "pip", "install", "-e", str(ROOT)])
        except subprocess.CalledProcessError:
            log("Dependency installation failed. Check the network and pip output above.")
            if args.no_venv:
                log("A system Python may refuse packages under PEP 668; omit --no-venv")
                log("to install into the project virtualenv instead.")
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
    log(f"  {python} run.py batch cards.csv")
    log(f"  {python} run.py batch cards.csv --dry-run")
    log(f"  {python} run.py voices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
