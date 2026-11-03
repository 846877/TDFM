import shutil
from pathlib import Path

import pytest

from tdfm.live.ocr import Word
from tdfm.live.parser import ForgeState, ReadLine, match_stat, parse_forge
from tdfm.live.tracker import LiveTracker


def W(text, x, y, w=None, h=12):
    return Word(text, x, y, w or 8 * len(text), h)


def test_match_stat_names():
    assert match_stat("Vitalité", False) == "vi"
    assert match_stat("Vitolité", False) == "vi"  # faute d'OCR
    assert match_stat("Résistance Terre", True) == "pres_terre"
    assert match_stat("Résistances Eau", False) == "res_eau"
    assert match_stat("Dommages Critiques", False) == "do_cri"
    assert match_stat("Critique", True) == "cri"


def test_parse_synthetic_window():
    words = [
        W("reliquat", 400, 50), W(":", 470, 50), W("2,5", 480, 50),
        W("Min", 100, 100), W("Max", 160, 100), W("Effets", 220, 100), W("/", 270, 100),
        W("Carac.", 280, 100), W("Modif.", 500, 100),
        W("151", 100, 130), W("200", 160, 130), W("176", 220, 130), W("Vitalité", 255, 130),
        W("6", 100, 160), W("8", 160, 160), W("8%", 220, 160), W("Résistance", 255, 160), W("Terre", 340, 160),
        W("-7", 100, 190), W("-10", 160, 190), W("-6", 220, 190), W("Tacle", 255, 190),
    ]
    st = parse_forge(words)
    assert st.reliquat == 2.5
    assert [(l.code, l.min, l.max, l.current) for l in st.lines] == [
        ("vi", 151, 200, 176), ("pres_terre", 6, 8, 8), ("tacle", -7, -10, -6)]


def test_no_window():
    assert parse_forge([W("Bonjour", 10, 10)]) is None


def _state(vi, sa, rel):
    return ForgeState([ReadLine("vi", 151, 200, vi), ReadLine("sa", 11, 15, sa)], rel)


def test_tracker_outcomes():
    t = LiveTracker(level=200)
    assert t.update(_state(160, 12, 0)) is None
    assert t.item.lines["vi"].max == 200 and t.item.puits == 0
    assert t.update(_state(175, 12, 0)).outcome == "SC"
    c = t.update(_state(190, 11, 0))
    assert c.outcome == "SN" and c.lost == {"sa": 1}
    assert t.update(_state(190, 10, 0)).outcome == "EC"
    assert t.update(_state(190, 10, 0)) is None


def test_tracker_keeps_bounds_when_unread():
    t = LiveTracker()
    t.update(_state(160, 12, 0))
    t.update(ForgeState([ReadLine("vi", None, None, 170), ReadLine("sa", None, 15, 12)], None))
    assert t.item.lines["vi"].min == 151 and t.item.lines["sa"].max == 15


HUZ = Path("/root/.claude/uploads/780e0e39-ca49-55c4-8f6b-674b0d73e0e0/fc220d11-image.png")


@pytest.mark.skipif(not shutil.which("tesseract") or not HUZ.exists(), reason="tesseract ou capture absents")
def test_huz_capture_with_tesseract():
    from PIL import Image
    from tdfm.live.ocr import TesseractOcr
    st = parse_forge(TesseractOcr().read(Image.open(HUZ), scale=2.5))
    got = {l.code: l.current for l in st.lines}
    assert got["sa"] == 24 and got["ini"] == 304 and got["pres_terre"] == 8 and got["tacle"] == -6
