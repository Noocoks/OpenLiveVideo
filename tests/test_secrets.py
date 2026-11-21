import sys
from types import SimpleNamespace

from shortsfactory import config


class FakeKeyring:
    priority = 1

    def __init__(self):
        self.values = {}

    def set_password(self, service, account, value):
        self.values[(service, account)] = value

    def get_password(self, service, account):
        return self.values.get((service, account))

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


def test_pixabay_key_is_saved_to_keyring_not_plaintext(tmp_path, monkeypatch):
    backend = FakeKeyring()
    fake = SimpleNamespace(get_keyring=lambda: backend,
                            set_password=backend.set_password,
                            get_password=backend.get_password,
                            delete_password=backend.delete_password)
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    config.save_settings({"voice": "es-ES-AlvaroNeural"})
    config.save_pixabay_key("secret-token")

    assert config.get_pixabay_key() == "secret-token"
    assert "secret-token" not in (tmp_path / "settings.json").read_text()
    assert backend.values[("OLV", "pixabay-api-key")] == "secret-token"


def test_legacy_plaintext_key_migrates_to_keyring(tmp_path, monkeypatch):
    backend = FakeKeyring()
    fake = SimpleNamespace(get_keyring=lambda: backend,
                            set_password=backend.set_password,
                            get_password=backend.get_password,
                            delete_password=backend.delete_password)
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "settings.json").write_text(
        '{"pixabay_api_key":"old-token","voice":"es-ES-ElviraNeural"}')
    assert config.get_pixabay_key() == "old-token"
    assert "old-token" not in (tmp_path / "settings.json").read_text()
    assert backend.values[("OLV", "pixabay-api-key")] == "old-token"

def test_keyring_migration_scrubs_legacy_settings_file(tmp_path, monkeypatch):
    backend = FakeKeyring()
    fake = SimpleNamespace(get_keyring=lambda: backend,
                            set_password=backend.set_password,
                            get_password=backend.get_password,
                            delete_password=backend.delete_password)
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    current = tmp_path / "olv"
    current.mkdir()
    monkeypatch.setattr(config, "config_dir", lambda: current)
    old_dir = tmp_path / "shortsfactory"
    old_dir.mkdir()
    old_file = old_dir / "settings.json"
    old_file.write_text('{"pixabay_api_key":"legacy-secret","voice":"es-ES-AlvaroNeural"}')

    config.save_pixabay_key("legacy-secret")

    assert "legacy-secret" not in old_file.read_text()
    assert backend.values[("OLV", "pixabay-api-key")] == "legacy-secret"



def test_clearing_pixabay_key_removes_plaintext_legacy_value(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "settings.json").write_text('{"pixabay_api_key":"stale-secret","voice":"es-ES-ElviraNeural"}')
    config.delete_pixabay_key()
    saved = (tmp_path / "settings.json").read_text()
    assert "stale-secret" not in saved
    assert "pixabay_api_key" not in saved
