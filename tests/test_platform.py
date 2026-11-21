"""Cross-platform engine discovery and Windows user-data link check."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jpcard import cli as cli_module  # noqa: E402
from jpcard import tts as tts_module  # noqa: E402
from jpcard.config import load_config  # noqa: E402
from jpcard.tts import check_windows_userdata, find_engine_executable  # noqa: E402

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


class WindowsUserdataTests(unittest.TestCase):
    """The VOICEVOX data junction is a documented Windows workaround."""

    def setUp(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        project = SCRATCH / "project"
        self.engine_dir = project / "voices" / "engine"
        self.userdata = project / "voices" / "userdata"
        self.local = project / "local"
        for directory in (self.engine_dir, self.userdata, self.local):
            directory.mkdir(parents=True, exist_ok=True)
        (self.engine_dir / "run.exe").write_bytes(b"")
        self.link = self.local / "voicevox-engine"

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def _check(self) -> str | None:
        with mock.patch.object(tts_module.os, "name", "nt"):
            return check_windows_userdata(self.engine_dir, self.local)

    def test_non_windows_is_silent(self) -> None:
        with mock.patch.object(tts_module.os, "name", "posix"):
            self.assertIsNone(check_windows_userdata(self.engine_dir, self.local))

    def test_no_engine_is_silent(self) -> None:
        empty = SCRATCH / "empty"
        empty.mkdir()
        with mock.patch.object(tts_module.os, "name", "nt"):
            self.assertIsNone(check_windows_userdata(empty, self.local))

    def test_missing_link_is_silent(self) -> None:
        # Engines started by kotoba-forge get LOCALAPPDATA pointed at
        # voices/userdata, so the junction is not needed for a batch.
        self.assertIsNone(self._check())

    def test_dangling_link_warns(self) -> None:
        with mock.patch.object(tts_module.os.path, "lexists", return_value=True), mock.patch.object(
            tts_module.Path, "exists", return_value=False
        ):
            warning = self._check()
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertIn("broken", warning)
        self.assertIn("setup.py", warning)
        self.assertIn("--tts none", warning)

    def test_real_folder_is_silent(self) -> None:
        # A manually started engine creates this folder; it is usable as-is.
        self.link.mkdir()
        self.assertIsNone(self._check())

    def test_link_to_this_project_is_silent(self) -> None:
        self.link.mkdir()
        with mock.patch.object(tts_module, "_is_junction", return_value=True), mock.patch.object(
            tts_module, "_link_target", return_value=self.userdata
        ):
            self.assertIsNone(self._check())

    def test_link_to_another_checkout_warns(self) -> None:
        self.link.mkdir()
        elsewhere = SCRATCH / "old-checkout" / "voices" / "userdata"
        elsewhere.mkdir(parents=True)
        with mock.patch.object(tts_module, "_is_junction", return_value=True), mock.patch.object(
            tts_module, "_link_target", return_value=elsewhere
        ):
            warning = self._check()
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertIn("points elsewhere", warning)
        self.assertIn("--tts none", warning)

    def test_tts_none_skips_the_check(self) -> None:
        args = argparse.Namespace(tts="none", no_audio=False)
        with mock.patch.object(cli_module, "check_windows_userdata") as check:
            self.assertIsNone(cli_module._make_tts(load_config(), args))
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
