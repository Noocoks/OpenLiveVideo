from __future__ import annotations

import json
import logging
import logging.handlers
import os
import shutil
from pathlib import Path

SECRET_SERVICE = "OLV"
SECRET_ACCOUNT = "pixabay-api-key"


class SecretStorageError(RuntimeError):
    """Raised when the OS credential store cannot securely save a secret."""


def user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or
                    (Path.home() / "AppData" / "Local"))
        path = base / "OLV"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "olv"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        path = base / "OLV"
    else:
        path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "olv"
    path.mkdir(parents=True, exist_ok=True)
    legacy_base = (Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
                   if os.name == "nt" else
                   Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")))
    legacy_file = legacy_base / ("ShortsFactory" if os.name == "nt" else "shortsfactory") / "settings.json"
    current_file = path / "settings.json"
    if not current_file.exists() and legacy_file.is_file():
        try:
            shutil.copy2(legacy_file, current_file)
        except OSError:
            logging.getLogger(__name__).warning("No se pudieron migrar los ajustes antiguos.", exc_info=True)
    return path


def configure_logging() -> Path:
    folder = user_data_dir() / "logs"
    log_path = folder / "olv.log"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        root_logger = logging.getLogger()
        if not any(getattr(handler, "baseFilename", None) == str(log_path) for handler in root_logger.handlers):
            handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"))
            root_logger.addHandler(handler)
            root_logger.setLevel(logging.INFO)
    except OSError:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("No se pudo activar el registro en disco.")
    return log_path


def migrate_legacy_drafts(project_dir: Path, data_dir: Path) -> int:
    legacy = project_dir / "drafts"
    destination = data_dir / "drafts"
    if not legacy.is_dir():
        return 0
    copied = 0
    for source in legacy.rglob("*"):
        if not source.is_file():
            continue
        target = destination / source.relative_to(legacy)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def load_settings() -> dict:
    try:
        data = json.loads((config_dir() / "settings.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict) -> None:
    """Persist preferences atomically; never write API credentials to this file."""
    safe = dict(settings)
    safe.pop("pixabay_api_key", None)
    path = config_dir() / "settings.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)


def save_pixabay_key(value: str) -> None:
    value = value.strip()
    if not value:
        delete_pixabay_key()
        return
    try:
        import keyring
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) <= 0:
            raise RuntimeError("No hay un almacén de credenciales del sistema disponible.")
        keyring.set_password(SECRET_SERVICE, SECRET_ACCOUNT, value)
        if keyring.get_password(SECRET_SERVICE, SECRET_ACCOUNT) != value:
            raise RuntimeError("El almacén del sistema no ha confirmado la credencial.")
    except Exception as exc:
        raise SecretStorageError(
            "No se pudo guardar la clave de forma segura en el almacén del sistema. "
            "Comprueba que el almacén de credenciales del sistema está disponible o "
            "define PIXABAY_API_KEY como variable de entorno."
        ) from exc
    settings = load_settings()
    if "pixabay_api_key" in settings:
        settings.pop("pixabay_api_key", None)
        save_settings(settings)
    _scrub_legacy_plaintext_key()


def _scrub_legacy_plaintext_key() -> None:
    if os.name == "nt":
        old_path = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "ShortsFactory" / "settings.json"
    else:
        old_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "shortsfactory" / "settings.json"
    try:
        if old_path.is_file():
            old = json.loads(old_path.read_text(encoding="utf-8"))
            if isinstance(old, dict) and "pixabay_api_key" in old:
                old.pop("pixabay_api_key", None)
                old_path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
                try:
                    os.chmod(old_path, 0o600)
                except OSError:
                    pass
    except (OSError, json.JSONDecodeError):
        logging.getLogger(__name__).warning("No se pudo limpiar la antigua clave en texto plano.", exc_info=True)


def delete_pixabay_key() -> None:
    try:
        import keyring
        keyring.delete_password(SECRET_SERVICE, SECRET_ACCOUNT)
    except Exception:
        pass
    settings = load_settings()
    if "pixabay_api_key" in settings:
        settings.pop("pixabay_api_key", None)
        save_settings(settings)
    _scrub_legacy_plaintext_key()


def get_pixabay_key() -> str:
    env_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        import keyring
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) > 0:
            value = keyring.get_password(SECRET_SERVICE, SECRET_ACCOUNT)
            if value:
                return value.strip()
    except Exception:
        logging.getLogger(__name__).warning("No se pudo consultar el almacén de credenciales.", exc_info=True)

    # One-time migration from the previous plaintext settings format.
    settings = load_settings()
    legacy = (settings.get("pixabay_api_key") or "").strip()
    if legacy:
        try:
            save_pixabay_key(legacy)
            return legacy
        except SecretStorageError:
            logging.getLogger(__name__).exception(
                "La clave antigua sigue en ajustes porque el almacén seguro no está disponible.")
    return ""
