"""Capture de l'écran (lecture seule)."""

from __future__ import annotations

from PIL import Image


def grab_screen(region: tuple[int, int, int, int] | None = None, monitor: int = 0) -> Image.Image:
    """Capture tout l'écran (tous les moniteurs si monitor=0) ou une zone (x, y, w, h)."""
    import mss

    with mss.mss() as sct:
        if region:
            x, y, w, h = region
            mon = {"left": x, "top": y, "width": w, "height": h}
        else:
            mon = sct.monitors[monitor]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def screen_origin() -> tuple[int, int]:
    """Coin haut-gauche de l'écran virtuel (peut être négatif avec plusieurs écrans)."""
    import mss

    with mss.mss() as sct:
        mon = sct.monitors[0]
        return mon["left"], mon["top"]
