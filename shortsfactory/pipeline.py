from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from .audio import synthesize
from .models import Episode
from .providers.pixabay import PixabayClient
from .renderer import render_short, RenderError
from .runtime import find_tool

MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


class ProductionCancelled(RuntimeError):
    """Raised when the user cancels a production."""


@dataclass
class PreparedScene:
    text: str
    video: Path
    audio: Path
    source: dict
    audio_text: str = ""


@dataclass
class PreparedProduction:
    episode: Episode
    work_dir: Path
    music: Path | None
    scenes: list[PreparedScene]

    @property
    def sources(self) -> list[dict]:
        return [scene.source for scene in self.scenes]


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event and cancel_event.is_set():
        raise ProductionCancelled("Producción cancelada por el usuario.")


def _query_for_scene(text: str) -> str:
    words = re.findall(r"[\wáéíóúñü]{4,}", text.lower())
    stop = {"desde", "había", "estaba", "entonces", "porque", "cuando", "hasta",
            "sobre", "después", "mientras", "exactamente", "pensé"}
    return " ".join([w for w in words if w not in stop][:4]) or "cinematic mystery"


def _find_background_music(episode: Episode, project_dir: Path) -> Path | None:
    if episode.music_path:
        path = Path(episode.music_path)
        if not path.is_file():
            raise FileNotFoundError(f"No encuentro la música seleccionada: {path}")
        return path
    music_dir = project_dir / "assets" / "music"
    if music_dir.is_dir():
        tracks = sorted(p for p in music_dir.iterdir()
                        if p.is_file() and p.suffix.lower() in MUSIC_EXTENSIONS)
        if tracks:
            return tracks[0]
    return None


def prepare_episode(episode: Episode, api_key: str, project_dir: Path,
                    progress=None, data_dir: Path | None = None,
                    cancel_event: threading.Event | None = None) -> PreparedProduction:
    scenes = episode.scene_list()
    if not scenes:
        raise ValueError("Escribe una historia antes de producir.")
    if not find_tool("ffmpeg") or not find_tool("ffprobe"):
        raise RenderError("Falta FFmpeg/ffprobe. Instala FFmpeg y vuelve a abrir OLV.")
    music = _find_background_music(episode, project_dir)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", episode.title).strip("-").lower()[:48] or "short"
    work = (data_dir or project_dir) / "work" / slug
    downloads, voice_dir = work / "downloads", work / "voice"
    downloads.mkdir(parents=True, exist_ok=True)
    voice_dir.mkdir(parents=True, exist_ok=True)
    client = PixabayClient(api_key)
    prepared: list[PreparedScene] = []
    used_ids = set()
    for i, scene in enumerate(scenes):
        _check_cancel(cancel_event)
        if progress:
            progress(f"Buscando clips · escena {i+1}/{len(scenes)}", i, len(scenes), "search")
        hits = client.search_videos(_query_for_scene(scene), per_page=12)
        if not hits:
            hits = client.search_videos("cinematic dark mystery", per_page=12)
        if not hits:
            raise RuntimeError(f"Pixabay no encontró vídeos para la escena {i+1}.")
        hit = next((item for item in hits if item.get("id") not in used_ids), hits[0])
        if hit.get("id") is not None:
            used_ids.add(hit["id"])
        video = downloads / f"scene_{i:03}.mp4"
        source = client.download(hit, video, cancel_event=cancel_event)
        _check_cancel(cancel_event)
        if progress:
            progress(f"Generando narración · escena {i+1}/{len(scenes)}", i, len(scenes), "voice")
        audio = voice_dir / f"scene_{i:03}.mp3"
        synthesize(scene, audio, episode.voice, cancel_event=cancel_event)
        prepared.append(PreparedScene(scene, video, audio, source, scene))
    _check_cancel(cancel_event)
    if progress:
        progress("Preparación completada · lista para revisar", len(scenes), len(scenes), "prepared")
    return PreparedProduction(episode, work, music, prepared)


def render_prepared(prepared: PreparedProduction, progress=None,
                    cancel_event: threading.Event | None = None) -> Path:
    _check_cancel(cancel_event)
    if not prepared.scenes:
        raise ValueError("No hay escenas preparadas.")
    episode = prepared.episode
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", episode.title).strip("-").lower()[:48] or "short"
    output = episode.output_dir / f"{slug}.mp4"
    changed = [scene for scene in prepared.scenes if scene.text != scene.audio_text]
    for index, scene in enumerate(changed):
        _check_cancel(cancel_event)
        if progress:
            progress(f"Actualizando narración · escena {index+1}/{len(changed)}", index, len(changed), "voice")
        synthesize(scene.text, scene.audio, episode.voice, cancel_event=cancel_event)
        scene.audio_text = scene.text
    if progress:
        progress("Montando vídeo, voz y subtítulos…", 0, 1, "render")
    render_short([s.video for s in prepared.scenes],
                 [s.audio for s in prepared.scenes],
                 [s.text for s in prepared.scenes],
                 output, prepared.work_dir, prepared.music,
                 cancel_event=cancel_event)
    _check_cancel(cancel_event)
    manifest = {"title": episode.title, "output": str(output),
                "assets": prepared.sources, "voice": episode.voice,
                "music": str(prepared.music) if prepared.music else None,
                "scenes": [s.text for s in prepared.scenes],
                "review_required": True, "publishing": "manual_only"}
    output.with_suffix(".sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if progress:
        progress("Producción terminada", 1, 1, "complete")
    return output


def build_episode(episode: Episode, api_key: str, project_dir: Path, progress=None,
                  data_dir: Path | None = None,
                  cancel_event: threading.Event | None = None) -> Path:
    prepared = prepare_episode(episode, api_key, project_dir, progress, data_dir, cancel_event)
    return render_prepared(prepared, progress, cancel_event)
