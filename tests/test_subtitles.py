from shortsfactory.subtitles import write_srt

def test_subtitle_timestamps_are_sequential(tmp_path):
    target = tmp_path / "captions.srt"
    write_srt([4.0, 2.0], ["uno dos tres cuatro cinco seis siete ocho nueve", "final"], target)
    content = target.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "00:00:04,000 --> 00:00:06,000" in content
    assert "\n3\n" in content
