from pathlib import Path

def _stamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def write_srt(scene_durations: list[float], scene_texts: list[str], path: Path) -> None:
    if len(scene_durations) != len(scene_texts):
        raise ValueError("La cantidad de duraciones y textos de subtítulos no coincide.")
    entries, cursor, number = [], 0.0, 1
    for duration, text in zip(scene_durations, scene_texts):
        if duration <= 0:
            raise ValueError("La duración de cada escena debe ser positiva.")
        words = text.split()
        chunks = [" ".join(words[i:i+8]) for i in range(0, len(words), 8)] or [text]
        part = duration / len(chunks)
        for chunk in chunks:
            entries.extend([str(number), f"{_stamp(cursor)} --> {_stamp(cursor + part)}", chunk, ""])
            cursor += part
            number += 1
    path.write_text("\n".join(entries), encoding="utf-8")
