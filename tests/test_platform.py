"""Cross-platform engine discovery."""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jpcard.tts import find_engine_executable  # noqa: E402

SCRATCH = ROOT / "out" / "_test_platform"


class PlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        SCRATCH.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def test_finds_native_launcher(self) -> None:
        name = "run.exe" if os.name == "nt" else "run"
        launcher = SCRATCH / name
        launcher.write_bytes(b"")
        self.assertEqual(find_engine_executable(SCRATCH), launcher)

    def test_missing(self) -> None:
        self.assertIsNone(find_engine_executable(None))
        self.assertIsNone(find_engine_executable(SCRATCH / "does-not-exist"))


if __name__ == "__main__":
    unittest.main()
