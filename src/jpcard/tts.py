"""TTS backends. Voicevox talks to the local engine over HTTP.

The engine is started on demand (headless) and stopped when a batch finishes,
so it never has to be running in the background.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class TTSError(Exception):
    pass


def find_engine_executable(engine_dir: Path | None) -> Path | None:
    """Locate the VOICEVOX launcher on Windows, Linux or macOS."""
    if engine_dir is None:
        return None
    directory = Path(engine_dir)
    names = ("run.exe", "run") if os.name == "nt" else ("run", "run.exe")
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


class VoicevoxTTS:
    def __init__(
        self,
        base_url: str,
        engine_dir: Path | None,
        speaker: int,
        speed: float,
        pitch: float,
        intonation: float,
        sample_rate: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.engine_dir = Path(engine_dir) if engine_dir else None
        self.speaker = speaker
        self.speed = speed
        self.pitch = pitch
        self.intonation = intonation
        self.sample_rate = sample_rate
        self._process: subprocess.Popen | None = None
        self._log_handle = None

    # -- engine lifecycle -------------------------------------------------
    @property
    def port(self) -> int:
        parsed = urllib.parse.urlparse(self.base_url)
        return parsed.port or 50021

    def is_alive(self) -> bool:
        try:
            self._get("/version", timeout=2)
            return True
        except TTSError:
            return False

    def ensure_running(self, timeout: float = 90.0) -> None:
        if self.is_alive():
            return
        if self.engine_dir is None:
            raise TTSError(
                f"VOICEVOX engine not reachable at {self.base_url} and no engine_dir configured"
            )
        exe = find_engine_executable(self.engine_dir)
        if exe is None:
            raise TTSError(
                "VOICEVOX engine executable not found in "
                f"{self.engine_dir}; expected run.exe (Windows) or run (Linux/macOS)"
            )

        if os.name != "nt":
            mode = exe.stat().st_mode
            if not mode & 0o111:
                exe.chmod(mode | 0o111)

        popen_kwargs: dict = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        # The engine normally logs nothing useful to us, but if it dies on
        # startup the log is the only clue. Keep it inside the project.
        log_path = self.engine_dir.parent / "engine.log"
        self._log_handle = open(log_path, "ab")
        self._log_handle.write(b"\n--- engine start ---\n")
        self._log_handle.flush()

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # VOICEVOX keeps its user dictionary and presets under the platform
        # data directory. A read-only home (sandbox, locked-down machine) makes
        # the engine exit before it listens, so keep that state in the project.
        userdata = (self.engine_dir.parent / "userdata").resolve()
        userdata.mkdir(parents=True, exist_ok=True)
        env["XDG_DATA_HOME"] = str(userdata)  # Linux / BSD
        if os.name == "nt":
            env["LOCALAPPDATA"] = str(userdata)

        self._process = subprocess.Popen(
            [str(exe), "--host", "127.0.0.1", "--port", str(self.port), "--output_log_utf8"],
            cwd=str(self.engine_dir),
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            **popen_kwargs,
        )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_alive():
                return
            if self._process.poll() is not None:
                raise TTSError(
                    f"VOICEVOX engine exited immediately (code {self._process.returncode})"
                )
            time.sleep(0.5)
        raise TTSError(f"VOICEVOX engine did not become ready within {timeout:.0f}s")

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    # -- HTTP -------------------------------------------------------------
    def _get(self, path: str, timeout: float = 60.0):
        url = self.base_url + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TTSError(f"GET {url} failed: {exc}") from exc

    def _post(self, path: str, payload: dict | None, timeout: float = 120.0) -> bytes:
        url = self.base_url + path
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TTSError(f"POST {url} failed: {exc}") from exc

    def speakers(self) -> list[dict]:
        self.ensure_running()
        return self._get("/speakers")

    def synthesize(self, text: str, out_path: Path) -> Path:
        self.ensure_running()
        query_path = "/audio_query?" + urllib.parse.urlencode(
            {"text": text, "speaker": self.speaker}
        )
        # VOICEVOX >= 0.19 exposes audio_query as POST with query parameters.
        query = json.loads(self._post(query_path, None).decode("utf-8"))
        query["speedScale"] = self.speed
        query["pitchScale"] = self.pitch
        query["intonationScale"] = self.intonation
        query["outputSamplingRate"] = self.sample_rate
        query["outputStereo"] = False

        wav = self._post(f"/synthesis?speaker={self.speaker}", query)
        if not wav.startswith(b"RIFF"):
            raise TTSError("VOICEVOX returned data that is not a WAV file")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(wav)
        return out_path
