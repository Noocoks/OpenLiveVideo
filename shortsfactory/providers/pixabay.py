from __future__ import annotations
import re
import threading
from pathlib import Path
from urllib.parse import urlparse
import requests

API_URL = "https://pixabay.com/api/videos/"

class PixabayError(RuntimeError):
    pass

class PixabayClient:
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key, self.timeout = api_key.strip(), timeout
        if not self.api_key:
            raise PixabayError("Falta la API key de Pixabay. Añádela en Ajustes.")

    def search_videos(self, query: str, per_page: int = 20) -> list[dict]:
        try:
            response = requests.get(API_URL, params={"key": self.api_key, "q": query,
                "per_page": min(max(per_page, 3), 50), "safesearch": "true"},
                timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("hits", [])
        except (requests.RequestException, ValueError) as exc:
            raise PixabayError(f"No se pudo consultar Pixabay: {str(exc).replace(self.api_key, '[REDACTED]')}") from None

    @staticmethod
    def choose_video(hit: dict) -> tuple[str, str]:
        for quality in ("large", "medium", "small", "tiny"):
            url = (hit.get("videos", {}).get(quality) or {}).get("url")
            if url:
                return url, quality
        raise PixabayError("Pixabay devolvió un vídeo sin URL descargable.")

    def download(self, hit: dict, destination: Path,
                 cancel_event: threading.Event | None = None) -> dict:
        url, quality = self.choose_video(hit)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with requests.get(url, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 256):
                        if cancel_event and cancel_event.is_set():
                            raise InterruptedError("Descarga cancelada por el usuario.")
                        if chunk:
                            handle.write(chunk)
        except (requests.RequestException, InterruptedError) as exc:
            destination.unlink(missing_ok=True)
            if isinstance(exc, InterruptedError):
                raise
            raise PixabayError(f"Error descargando vídeo: {exc}") from exc
        return {"file": str(destination), "source": "Pixabay",
            "page_url": hit.get("pageURL", ""), "creator": hit.get("user", ""),
            "video_id": hit.get("id"), "quality": quality,
            "download_url_host": urlparse(url).netloc,
            "license_note": "Verificar licencia y condiciones vigentes antes de publicar."}
