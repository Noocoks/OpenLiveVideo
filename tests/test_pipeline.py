import json
import threading
import shortsfactory.pipeline as pipeline
from shortsfactory.models import Episode

class FakePixabay:
    def __init__(self, api_key):
        assert api_key == "test-key"
    def search_videos(self, query, per_page=20):
        return [{"id": 123, "videos": {"large": {"url": "https://cdn.invalid/clip.mp4"}},
                 "pageURL": "https://pixabay.com/videos/example", "user": "tester"}]
    def download(self, hit, destination, cancel_event=None):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake video")
        return {"file": str(destination), "source": "Pixabay", "video_id": hit["id"]}

def test_build_episode_creates_review_manifest_without_upload(tmp_path, monkeypatch):
    def fake_synthesize(text, output, voice, cancel_event=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake audio")
        return output
    def fake_render(videos, audios, texts, output, work, music=None, cancel_event=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake mp4")
        return output
    monkeypatch.setattr(pipeline, "PixabayClient", FakePixabay)
    monkeypatch.setattr(pipeline, "synthesize", fake_synthesize)
    monkeypatch.setattr(pipeline, "render_short", fake_render)
    episode = Episode(title="Prueba local", script="Escena uno.\n\nEscena dos.", output_dir=tmp_path / "review")
    result = pipeline.build_episode(episode, "test-key", tmp_path)
    assert result.exists()
    manifest = json.loads(result.with_suffix(".sources.json").read_text(encoding="utf-8"))
    assert manifest["review_required"] is True
    assert manifest["publishing"] == "manual_only"
    assert len(manifest["assets"]) == 2
    assert len(manifest["scenes"]) == 2

def test_music_is_found_automatically_in_assets_folder(tmp_path):
    music_dir = tmp_path / "assets" / "music"
    music_dir.mkdir(parents=True)
    track = music_dir / "background.mp3"
    track.write_bytes(b"music")
    episode = Episode(title="music", script="Scene")
    assert pipeline._find_background_music(episode, tmp_path) == track

def test_no_music_is_valid_when_folder_is_empty(tmp_path):
    assert pipeline._find_background_music(Episode(title="no music", script="Scene"), tmp_path) is None



def test_prepare_episode_returns_reviewable_scenes(tmp_path, monkeypatch):
    def fake_synthesize(text, output, voice, cancel_event=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake audio")
        return output

    monkeypatch.setattr(pipeline, "PixabayClient", FakePixabay)
    monkeypatch.setattr(pipeline, "synthesize", fake_synthesize)
    episode = Episode(title="Review", script="Escena A.\n\nEscena B.", output_dir=tmp_path / "review")
    prepared = pipeline.prepare_episode(episode, "test-key", tmp_path, data_dir=tmp_path / "data")

    assert [scene.text for scene in prepared.scenes] == ["Escena A.", "Escena B."]
    assert all(scene.video.is_file() and scene.audio.is_file() for scene in prepared.scenes)
    assert len(prepared.sources) == 2


def test_prepare_episode_honours_cancel_before_network_work(tmp_path, monkeypatch):
    cancelled = threading.Event()
    cancelled.set()
    episode = Episode(title="Cancel", script="Una escena")
    try:
        pipeline.prepare_episode(episode, "test-key", tmp_path, cancel_event=cancelled)
    except pipeline.ProductionCancelled:
        pass
    else:
        raise AssertionError("Expected ProductionCancelled")



def test_render_prepared_regenerates_voice_after_review_text_edit(tmp_path, monkeypatch):
    spoken = []

    def fake_synthesize(text, output, voice, cancel_event=None):
        spoken.append(text)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"updated audio")
        return output

    def fake_render(videos, audios, texts, output, work, music=None, cancel_event=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake mp4")
        return output

    monkeypatch.setattr(pipeline, "PixabayClient", FakePixabay)
    monkeypatch.setattr(pipeline, "synthesize", fake_synthesize)
    monkeypatch.setattr(pipeline, "render_short", fake_render)
    episode = Episode(title="Edit", script="Texto original", output_dir=tmp_path / "review")
    prepared = pipeline.prepare_episode(episode, "test-key", tmp_path, data_dir=tmp_path / "data")
    prepared.scenes[0].text = "Texto corregido en revisión"

    result = pipeline.render_prepared(prepared)

    assert result.is_file()
    assert spoken == ["Texto original", "Texto corregido en revisión"]
    assert prepared.scenes[0].audio_text == "Texto corregido en revisión"
