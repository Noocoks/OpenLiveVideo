import shutil
import subprocess
import sys
import threading
import pytest
from shortsfactory.renderer import render_short, _run
from shortsfactory.audio import probe_duration

@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg no está instalado")
def test_render_produces_vertical_mp4_with_audio_and_subtitles(tmp_path):
    video = tmp_path / "source video.mp4"
    audio = tmp_path / "voice.wav"
    music = tmp_path / "music.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
        "color=c=navy:s=320x240:r=25:d=2", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=1.2", "-c:a", "pcm_s16le", str(audio)],
        check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
        "sine=frequency=110:duration=2", "-c:a", "pcm_s16le", str(music)],
        check=True, capture_output=True)

    output = tmp_path / "review" / "rendered.mp4"
    render_short([video], [audio], ["Prueba de subtítulos de ShortsFactory."],
                 output, tmp_path / "work", music)
    assert output.exists() and output.stat().st_size > 1024
    assert 1.0 <= probe_duration(output) <= 1.5
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(output)],
        capture_output=True, text=True, check=True)
    assert probe.stdout.strip() == "1080x1920"
    assert "Prueba de subtítulos" in (tmp_path / "work" / "captions.srt").read_text(encoding="utf-8")



def test_ffmpeg_runner_terminates_process_on_cancel(tmp_path):
    cancel = threading.Event()
    output = tmp_path / "partial.mp4"
    timer = threading.Timer(0.3, cancel.set)
    timer.start()
    try:
        with pytest.raises(InterruptedError, match="cancelado"):
            _run([sys.executable, "-c", "import time; time.sleep(10)", str(output)],
                 cancel_event=cancel)
    finally:
        timer.cancel()
    assert not output.exists()
