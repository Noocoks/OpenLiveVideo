from __future__ import annotations
import shutil
import subprocess
import threading
import time
import tempfile
from pathlib import Path
from .audio import probe_duration
from .subtitles import write_srt
from .runtime import find_tool

class RenderError(RuntimeError):
    pass

def _run(command: list[str], cwd: Path | None = None,
         cancel_event: threading.Event | None = None) -> None:
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_log:
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.DEVNULL,
                                   stderr=error_log, text=True)
        while process.poll() is None:
            if cancel_event and cancel_event.wait(0.15):
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                try:
                    Path(command[-1]).unlink(missing_ok=True)
                except (OSError, TypeError):
                    pass
                raise InterruptedError("Renderizado cancelado por el usuario.")
            time.sleep(0.05)
        error_log.seek(0)
        stderr = error_log.read()
        if process.returncode:
            detail = (stderr or "Error desconocido de FFmpeg")[-4000:]
            raise RenderError(detail)

def _concat_quote(path: Path) -> str:
    # concat demuxer uses its own quoting rules, not the shell's.
    return path.resolve().as_posix().replace("'", "'\\''")

def render_short(video_files: list[Path], audio_files: list[Path], scene_texts: list[str],
                 output: Path, work_dir: Path, music: Path | None = None,
                 cancel_event: threading.Event | None = None) -> Path:
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg or not find_tool("ffprobe"):
        raise RenderError("No se encuentra FFmpeg/ffprobe. Instálalos y añádelos al PATH.")
    if not video_files or len(video_files) != len(audio_files) or len(audio_files) != len(scene_texts):
        raise RenderError("La cantidad de clips, audios y escenas no coincide.")
    for path in [*video_files, *audio_files]:
        if not path.is_file():
            raise RenderError(f"No existe el archivo necesario: {path}")
    if music is not None and not music.is_file():
        raise RenderError(f"No existe el archivo de música: {music}")
    work_dir.mkdir(parents=True, exist_ok=True)
    segments, durations = [], []
    for idx, (video, audio) in enumerate(zip(video_files, audio_files)):
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Renderizado cancelado por el usuario.")
        duration = probe_duration(audio)
        durations.append(duration)
        segment = work_dir / f"segment_{idx:03}.mp4"
        _run([ffmpeg, "-y", "-stream_loop", "-1", "-i", str(video.resolve()), "-i", str(audio.resolve()),
            "-t", f"{duration:.3f}", "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "23", "-c:a", "aac", "-b:a", "160k", "-shortest", str(segment.resolve())], cancel_event=cancel_event)
        segments.append(segment)
    concat = work_dir / "concat.txt"
    concat.write_text("".join(f"file '{_concat_quote(p)}'\n" for p in segments), encoding="utf-8")
    joined = work_dir / "joined.mp4"
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat.resolve()),
          "-c", "copy", str(joined.resolve())], cancel_event=cancel_event)
    srt = work_dir / "captions.srt"
    write_srt(durations, scene_texts, srt)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", str(joined.resolve())]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music.resolve()),
            "-filter_complex", "[0:a]volume=1.0[voice];[1:a]volume=0.13[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v:0", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    cmd += ["-vf", "subtitles=captions.srt:force_style='FontName=Arial,FontSize=18,Outline=2,Shadow=1,Alignment=2,MarginV=110'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output.resolve())]
    _run(cmd, cwd=work_dir, cancel_event=cancel_event)
    if not output.is_file() or output.stat().st_size < 1024:
        raise RenderError("FFmpeg terminó sin producir un MP4 válido.")
    return output
