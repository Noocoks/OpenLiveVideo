from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
from pathlib import Path
from .runtime import find_tool


async def _synth(text: str, output: Path, voice: str,
                 cancel_event: threading.Event | None = None) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    with output.open("wb") as handle:
        async for chunk in communicate.stream():
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Generación de voz cancelada por el usuario.")
            if chunk.get("type") == "audio":
                handle.write(chunk["data"])


def synthesize(text: str, output: Path, voice: str = "es-ES-AlvaroNeural",
               cancel_event: threading.Event | None = None) -> Path:
    if not text.strip():
        raise ValueError("No hay texto para narrar.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    try:
        asyncio.run(_synth(text, output, voice, cancel_event))
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, InterruptedError):
            raise
        raise RuntimeError(f"No se pudo generar la voz con Edge TTS: {exc}") from exc
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("El servicio TTS no generó audio.")
    return output


def probe_duration(path: Path) -> float:
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        raise RuntimeError("No se encuentra ffprobe. Instala FFmpeg y añádelo al PATH.")
    try:
        result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True)
        return max(float(result.stdout.strip()), 0.1)
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise RuntimeError(f"No se pudo leer la duración del audio {path}: {exc}") from exc
