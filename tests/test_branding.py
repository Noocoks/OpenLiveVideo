from importlib import resources
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


def test_master_brand_svg_is_packaged_and_valid():
    svg = resources.files("shortsfactory").joinpath(
        "assets", "branding", "olv-master.svg")
    assert svg.is_file()
    ET.fromstring(svg.read_bytes())


def test_master_brand_svg_renders_to_png_when_cairo_is_available():
    svg = resources.files("shortsfactory").joinpath(
        "assets", "branding", "olv-master.svg")
    try:
        import cairosvg
        rendered = cairosvg.svg2png(bytestring=svg.read_bytes(), output_width=192, output_height=192)
    except OSError as exc:
        if "cairo" in str(exc).lower():
            pytest.skip("Native Cairo runtime is unavailable; OLV uses its Tk fallback.")
        raise
    assert rendered.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10]))
    assert len(rendered) > 1000



def test_packaged_master_matches_editable_repository_master():
    packaged = resources.files("shortsfactory").joinpath(
        "assets", "branding", "olv-master.svg").read_bytes()
    repository = Path(__file__).resolve().parents[1] / "assets" / "branding" / "olv-master.svg"
    assert packaged == repository.read_bytes()
