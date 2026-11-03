"""Onglet « Direct » : TDFM lit ton écran et te conseille en temps réel."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .engine.advisor import Advisor
from .engine.model import Odds, quality
from .engine.runes import STATS
from .live.tracker import LiveTracker

GREEN, BLUE, RED = QColor("#2ea55a"), QColor("#355a8a"), QColor("#a33a3a")


class OddsBar(QWidget):
    """Barre SC / SN / EC."""

    def __init__(self):
        super().__init__()
        self.odds: Odds | None = None
        self.setMinimumHeight(46)

    def set_odds(self, odds: Odds | None):
        self.odds = odds
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), 22
        if not self.odds:
            return
        x = 0.0
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        for val, col, lab in ((self.odds.sc, GREEN, "SC"), (self.odds.sn, BLUE, "SN"), (self.odds.ec, RED, "EC")):
            seg = w * val
            p.fillRect(QRectF(x, 0, seg, h), col)
            p.setPen(col.lighter(150))
            text = f"{lab} {val:.1%}".replace(".", ",")
            if lab == "EC":
                p.drawText(QRectF(0, h + 2, w, 20), Qt.AlignRight, text)
            elif seg > 0 or lab == "SC":
                p.drawText(QRectF(x, h + 2, max(seg, 90), 20), Qt.AlignLeft, text)
            x += seg
        p.end()


def _fmt_stat(code: str) -> str:
    return STATS[code].name


class LivePanel(QWidget):
    def __init__(self, get_advisor, window):
        super().__init__()
        self.get_advisor = get_advisor
        self.window_ref = window
        self.tracker = LiveTracker()
        self.watcher = None
        self.last_change_text = ""

        v = QVBoxLayout(self)

        # Barre du haut : état + boutons
        top = QHBoxLayout()
        self.status = QLabel("Clique sur « Démarrer » puis ouvre ta fenêtre de forgemagie dans Dofus.")
        self.status.setWordWrap(True)
        top.addWidget(self.status, 1)
        self.start_btn = QPushButton("▶  Démarrer")
        self.start_btn.setMinimumHeight(34)
        self.start_btn.clicked.connect(self.toggle)
        top.addWidget(self.start_btn)
        v.addLayout(top)

        opts = QHBoxLayout()
        self.on_top = QCheckBox("Toujours au premier plan")
        self.on_top.toggled.connect(self._set_on_top)
        opts.addWidget(self.on_top)
        opts.addSpacing(16)
        opts.addWidget(QLabel("Niveau de l'objet :"))
        self.level = QSpinBox()
        self.level.setRange(1, 200)
        self.level.setValue(200)
        self.level.valueChanged.connect(self.refresh)
        opts.addWidget(self.level)
        opts.addStretch()
        self.mode_value = QRadioButton("Plus intéressante")
        self.mode_safe = QRadioButton("Plus de chances")
        self.mode_value.setChecked(True)
        grp = QButtonGroup(self)
        for b in (self.mode_value, self.mode_safe):
            grp.addButton(b)
            opts.addWidget(b)
        self.mode_value.toggled.connect(self.refresh)
        v.addLayout(opts)

        # Carte principale : la rune à passer
        card = QFrame()
        card.setObjectName("card")
        cv = QVBoxLayout(card)
        t = QLabel("PROCHAINE RUNE")
        t.setObjectName("caption")
        cv.addWidget(t)
        self.best = QLabel("—")
        self.best.setObjectName("big")
        cv.addWidget(self.best)
        self.best_reason = QLabel("")
        self.best_reason.setWordWrap(True)
        cv.addWidget(self.best_reason)
        self.bar = OddsBar()
        cv.addWidget(self.bar)
        v.addWidget(card)

        # Exo
        exo = QFrame()
        exo.setObjectName("card")
        ev = QVBoxLayout(exo)
        eh = QHBoxLayout()
        lab = QLabel("EXO")
        lab.setObjectName("caption")
        eh.addWidget(lab)
        self.exo_combo = QComboBox()
        self.exo_combo.addItem("Aucune", None)
        for code in ("pa", "pm", "po", "invo"):
            self.exo_combo.addItem(STATS[code].name, code)
        self.exo_combo.currentIndexChanged.connect(self.refresh)
        eh.addWidget(self.exo_combo)
        eh.addStretch()
        ev.addLayout(eh)
        self.exo_msg = QLabel("Choisis l'exo que tu vises : je te dirai quand la tenter.")
        self.exo_msg.setWordWrap(True)
        ev.addWidget(self.exo_msg)
        v.addWidget(exo)

        # Autres choix + lignes lues
        bottom = QHBoxLayout()
        self.alts = QTableWidget(0, 3)
        self.alts.setHorizontalHeaderLabels(["Autres runes", "SC", "Passe"])
        self.alts.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.alts.verticalHeader().setVisible(False)
        self.alts.setEditTriggers(QTableWidget.NoEditTriggers)
        bottom.addWidget(self.alts, 1)
        right = QVBoxLayout()
        self.lines = QTableWidget(0, 4)
        self.lines.setHorizontalHeaderLabels(["Ligne lue", "Min", "Max", "Actuel"])
        self.lines.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lines.verticalHeader().setVisible(False)
        self.lines.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.lines, 1)
        self.info = QLabel("")
        right.addWidget(self.info)
        bottom.addLayout(right, 1)
        v.addLayout(bottom, 1)

        self.last = QLabel("")
        self.last.setObjectName("caption")
        v.addWidget(self.last)

    # --- Lecture de l'écran ----------------------------------------------------------

    def toggle(self):
        if self.watcher and self.watcher.isRunning():
            self.watcher.stop()
            self.watcher.wait(3000)
            self.watcher = None
            self.start_btn.setText("▶  Démarrer")
            self.status.setText("En pause.")
            return
        from .live.worker import ScreenWatcher
        self.watcher = ScreenWatcher()
        self.watcher.state_read.connect(self.on_state)
        self.watcher.status.connect(self.status.setText)
        self.watcher.start()
        self.start_btn.setText("⏸  Pause")

    def stop(self):
        if self.watcher:
            self.watcher.stop()
            self.watcher.wait(3000)

    def _set_on_top(self, on: bool):
        w = self.window_ref
        w.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        w.show()

    def on_state(self, state):
        if state is None:
            self.status.setText("● Fenêtre de forgemagie introuvable : ouvre-la dans Dofus (bien visible à l'écran).")
            return
        self.status.setText("● En direct : fenêtre de forgemagie détectée.")
        change = self.tracker.update(state)
        if change:
            parts = [f"+{v} {_fmt_stat(c)}" for c, v in change.gained.items()]
            parts += [f"−{v} {_fmt_stat(c)}" for c, v in change.lost.items()]
            if abs(change.reliquat_delta) > 1e-9:
                parts.append(f"reliquat {change.reliquat_delta:+g}")
            self.last.setText(f"Dernier résultat : {change.outcome}  ({', '.join(parts)})")
        self.refresh()

    # --- Conseils --------------------------------------------------------------------

    def refresh(self):
        item = self.tracker.item
        if item is None:
            return
        item.level = self.tracker.level = self.level.value()
        adv: Advisor = self.get_advisor()
        sugg = adv.safest(item) if self.mode_safe.isChecked() else adv.suggestions(item)
        exo_code = self.exo_combo.currentData()
        exo = adv.exo(item, exo_code) if exo_code else None

        if exo and exo.ready:
            self.best.setText(f"{exo.rune.name}  (exo)")
            self.best_reason.setText(exo.message)
            self.bar.set_odds(adv.odds(item, exo.rune))
        elif sugg:
            s = sugg[0]
            self.best.setText(s.rune.name)
            self.best_reason.setText(s.reason)
            self.bar.set_odds(s.odds)
        else:
            self.best.setText("Objet terminé")
            self.best_reason.setText("Toutes les lignes ont atteint leur max.")
            self.bar.set_odds(None)
        self.exo_msg.setText(exo.message if exo else "Choisis l'exo que tu vises : je te dirai quand la tenter.")

        self.alts.setRowCount(0)
        for s in sugg[1:7]:
            r = self.alts.rowCount()
            self.alts.insertRow(r)
            for c, txt in enumerate((s.rune.name, f"{s.odds.sc:.0%}", f"{s.odds.passes:.0%}")):
                self.alts.setItem(r, c, QTableWidgetItem(txt))

        self.lines.setRowCount(0)
        for code, l in item.lines.items():
            r = self.lines.rowCount()
            self.lines.insertRow(r)
            vals = (l.stat.name, "–" if l.exo else str(l.min), "–" if l.exo else str(l.max), str(l.current))
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                if c == 3 and not l.exo and l.current > l.max:
                    it.setForeground(QColor("#e0b040"))
                self.lines.setItem(r, c, it)
        self.info.setText(f"Reliquat : {item.puits:g}   ·   Qualité : {quality(item):.0%}")
