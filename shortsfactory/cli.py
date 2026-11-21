from __future__ import annotations
import argparse
import json
from pathlib import Path
from .config import get_pixabay_key, user_data_dir
from .models import Episode
from .pipeline import build_episode
from .runtime import configure_runtime_paths

def main() -> None:
    configure_runtime_paths()
    parser = argparse.ArgumentParser(description="OLV: producción local de Shorts")
    parser.add_argument("episode", nargs="?", help="Archivo JSON del episodio")
    parser.add_argument("--output", default="output/review")
    args = parser.parse_args()
    if not args.episode:
        from .gui import launch
        launch()
        return
    data = json.loads(Path(args.episode).read_text(encoding="utf-8"))
    data_dir = user_data_dir()
    output_dir = Path(args.output).expanduser()
    if not output_dir.is_absolute():
        output_dir = data_dir / output_dir
    episode = Episode(title=data["title"], script=data.get("script", ""),
        scenes=data.get("scenes", []), voice=data.get("voice", "es-ES-AlvaroNeural"),
        music_path=data.get("music_path"), output_dir=output_dir)
    def report(message, current=0, total=1, stage=""):
        print(message)

    result = build_episode(episode, get_pixabay_key(), Path(__file__).resolve().parent.parent,
                           report, data_dir=data_dir)
    print(f"Vídeo listo para revisar: {result}")

if __name__ == "__main__":
    main()
