from pathlib import Path
import pytest
import shortsfactory.pipeline as pipeline
from shortsfactory.models import Episode
from shortsfactory.renderer import RenderError

def test_pipeline_fails_before_network_if_ffmpeg_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.shutil, "which", lambda name: None)
    monkeypatch.setattr(pipeline, "PixabayClient",
        lambda key: pytest.fail("Pixabay must not be called when FFmpeg is missing"))
    with pytest.raises(RenderError, match="Falta FFmpeg"):
        pipeline.build_episode(Episode(title="Preflight", script="Una escena."), "key", tmp_path)
