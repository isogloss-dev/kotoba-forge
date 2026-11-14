#!/usr/bin/env python
"""Launcher that lets the project run without installation.

Usage:  py run.py <command> [options]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    from jpcard.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
