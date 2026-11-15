#!/usr/bin/env python
"""Launcher that lets the project run without installation.

Usage:  python3 run.py <command> [options]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def venv_python() -> Path:
    venv = ROOT / ".venv"
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        from jpcard.cli import main as cli_main
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        print(f"error: missing Python package {missing!r}.", file=sys.stderr)
        print("kotoba-forge's dependencies live in its virtualenv, not in the", file=sys.stderr)
        print("system Python. Run the script with the virtualenv interpreter:", file=sys.stderr)
        python = venv_python()
        if python.exists():
            print(f"  {python} run.py ...", file=sys.stderr)
        else:
            print("  python3 scripts/setup.py", file=sys.stderr)
            print("  .venv/bin/python run.py ...     (Windows: .venv\\Scripts\\python run.py ...)", file=sys.stderr)
        return 2

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
