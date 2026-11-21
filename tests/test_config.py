import json
import os
from shortsfactory.config import (load_settings, save_settings, get_pixabay_key,
                                  user_data_dir, migrate_legacy_drafts)


def test_settings_round_trip_never_persists_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr("shortsfactory.config.config_dir", lambda: tmp_path)
    save_settings({"voice": "es-ES-ElviraNeural", "pixabay_api_key": "abc123"})
    assert load_settings()["voice"] == "es-ES-ElviraNeural"
    raw = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "abc123" not in raw
    assert "pixabay_api_key" not in raw


def test_user_data_dir_uses_platform_user_location(tmp_path, monkeypatch):
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        target = tmp_path / "OLV"
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        target = tmp_path / "olv"
    assert user_data_dir() == target
    assert target.is_dir()



def test_legacy_drafts_are_copied_without_overwriting_newer_user_files(tmp_path):
    project = tmp_path / "project"
    data = tmp_path / "user-data"
    (project / "drafts" / "archive").mkdir(parents=True)
    (project / "drafts" / "last_draft.json").write_text('{"script":"old"}')
    (project / "drafts" / "archive" / "story.json").write_text('{"title":"legacy"}')
    (data / "drafts").mkdir(parents=True)
    (data / "drafts" / "last_draft.json").write_text('{"script":"new"}')

    copied = migrate_legacy_drafts(project, data)

    assert copied == 1
    assert (data / "drafts" / "last_draft.json").read_text() == '{"script":"new"}'
    assert (data / "drafts" / "archive" / "story.json").read_text() == '{"title":"legacy"}'
    assert (project / "drafts" / "last_draft.json").exists()
