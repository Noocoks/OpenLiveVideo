from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def bundled_bin_dir() -> Path | None:
    roots = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root) / "bin")
    roots.append(Path(sys.executable).resolve().parent / "bin")
    for root in roots:
        if root.is_dir():
            return root
    return None


def configure_runtime_paths() -> None:
    """Prefer the FFmpeg binaries shipped with a frozen OLV build."""
    folder = bundled_bin_dir()
    if folder:
        current = os.environ.get("PATH", "").split(os.pathsep)
        if str(folder) not in current:
            os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


def find_tool(name: str) -> str | None:
    configure_runtime_paths()
    return shutil.which(name)
