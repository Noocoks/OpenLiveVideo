from dataclasses import dataclass, field
from pathlib import Path
import re

def suggest_title(script: str) -> str:
    """Create a readable title from the first sentence of a story."""
    text = " ".join(script.strip().split())
    if not text:
        return "Nuevo Short"
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip(" .!?")
    title = " ".join(first.split()[:8]).strip()
    return title[:64].rstrip() or "Nuevo Short"

@dataclass
class Episode:
    title: str
    script: str
    scenes: list[str] = field(default_factory=list)
    voice: str = "es-ES-AlvaroNeural"
    music_path: str | None = None
    output_dir: Path = Path("output/review")

    def scene_list(self) -> list[str]:
        source = self.scenes or [p.strip() for p in self.script.split("\n\n") if p.strip()]
        return [s.strip() for s in source if s.strip()]
