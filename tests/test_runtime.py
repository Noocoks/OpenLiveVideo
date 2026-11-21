import os
from pathlib import Path

from shortsfactory import runtime


def test_bundled_bin_directory_is_preferred(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")).write_text("fake")
    monkeypatch.setattr(runtime.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert runtime.bundled_bin_dir() == bin_dir


def test_configure_runtime_paths_adds_bundled_tools(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr(runtime, "bundled_bin_dir", lambda: bin_dir)
    monkeypatch.setenv("PATH", "original-path")
    runtime.configure_runtime_paths()
    assert os.environ["PATH"].split(os.pathsep)[0] == str(bin_dir)
