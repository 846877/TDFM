"""Boucle de lecture de l'écran, dans un fil séparé pour ne pas figer l'interface."""

from __future__ import annotations

import time
import traceback

from PySide6.QtCore import QThread, Signal

from .capture import grab_screen, screen_origin
from .ocr import get_backend
from .parser import find_header, parse_forge


class ScreenWatcher(QThread):
    state_read = Signal(object)  # ForgeState ou None
    status = Signal(str)

    def __init__(self, interval: float = 1.0):
        super().__init__()
        self.interval = interval
        self._running = True
        self.region = None  # zone (x, y, w, h) autour de la fenêtre de FM une fois trouvée

    def stop(self):
        self._running = False

    def run(self):
        try:
            ocr = get_backend()
        except Exception as exc:
            self.status.emit(f"Lecture d'écran impossible : {exc}")
            return
        self.status.emit(f"Lecture de l'écran en cours ({ocr.name})…")
        misses = 0
        while self._running:
            t0 = time.monotonic()
            try:
                state = self._read_once(ocr)
                if state is None:
                    misses += 1
                    if misses >= 2:
                        self.region = None  # on recherche dans tout l'écran
                self.state_read.emit(state)
                if state is not None:
                    misses = 0
            except Exception:
                self.status.emit("Erreur de lecture : " + traceback.format_exc(limit=1).strip().splitlines()[-1])
            wait = self.interval - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)

    def _read_once(self, ocr):
        if self.region:
            x, y, w, h = self.region
            img = grab_screen(self.region)
            words = ocr.read(img, scale=2.0)
            words = [type(wd)(wd.text, wd.x + x, wd.y + y, wd.w, wd.h) for wd in words]
        else:
            img = grab_screen()
            ox, oy = screen_origin()
            words = ocr.read(img, scale=1.5)
            words = [type(wd)(wd.text, wd.x + ox, wd.y + oy, wd.w, wd.h) for wd in words]
        state = parse_forge(words)
        if state is not None and self.region is None:
            header = find_header(words)
            if header:
                mn = header[0]
                # Zone généreuse : reliquat au-dessus, tableau en dessous, historique à gauche.
                rx, ry = int(mn.x - 700), int(mn.y - 250)
                self.region = (rx, ry, 1600, 1100)
                self.region = self._clip(self.region)
        return state

    @staticmethod
    def _clip(region):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
        x, y, w, h = region
        x, y = max(mon["left"], x), max(mon["top"], y)
        w = min(w, mon["left"] + mon["width"] - x)
        h = min(h, mon["top"] + mon["height"] - y)
        return (x, y, w, h)
