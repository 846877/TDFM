"""Interface Windows de TDFM (PySide6).

L'application ne fait que conseiller : elle n'envoie jamais rien au jeu.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from . import __version__
from .engine.advisor import Advisor
from .engine.item import Item, Outcome, item_from_dict, item_to_dict
from .engine.journal import Attempt, Journal
from .engine.model import bucket, quality
from .engine.runes import STATS, find_rune

EXO_CHOICES = ["pa", "pm", "po", "invo"]


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / "TDFM"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stat_combo(selected: str | None = None) -> QComboBox:
    box = QComboBox()
    for code, stat in STATS.items():
        box.addItem(stat.name, code)
    if selected:
        box.setCurrentIndex(box.findData(selected))
    return box


class LinesTable(QTableWidget):
    """Lignes de l'objet : caractéristique, min, max, actuel, objectif, priorité."""

    HEADERS = ["Caractéristique", "Min", "Max", "Actuel", "Objectif", "Priorité"]

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)

    def add_row(self, code="vi", mn=0, mx=0, cur=0, target=None, prio=1.0):
        r = self.rowCount()
        self.insertRow(r)
        self.setCellWidget(r, 0, stat_combo(code))
        for col, val in ((1, mn), (2, mx), (3, cur)):
            sb = QSpinBox()
            sb.setRange(-9999, 9999)
            sb.setValue(val)
            self.setCellWidget(r, col, sb)
        tg = QSpinBox()
        tg.setRange(-1, 9999)
        tg.setSpecialValueText("= max")
        tg.setValue(-1 if target is None else target)
        self.setCellWidget(r, 4, tg)
        pr = QDoubleSpinBox()
        pr.setRange(0, 10)
        pr.setSingleStep(0.5)
        pr.setValue(prio)
        self.setCellWidget(r, 5, pr)

    def remove_selected(self):
        for r in sorted({i.row() for i in self.selectedIndexes()}, reverse=True):
            self.removeRow(r)

    def load(self, item: Item):
        self.setRowCount(0)
        for code, l in item.lines.items():
            self.add_row(code, l.min, l.max, l.current, l.target, l.priority)

    def fill(self, item: Item):
        item.lines.clear()
        for r in range(self.rowCount()):
            code = self.cellWidget(r, 0).currentData()
            tg = self.cellWidget(r, 4).value()
            item.add_line(code, self.cellWidget(r, 1).value(), self.cellWidget(r, 2).value(),
                          self.cellWidget(r, 3).value(), target=None if tg < 0 else tg,
                          priority=self.cellWidget(r, 5).value())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"TDFM {__version__} : assistant de forgemagie")
        self.resize(1200, 760)
        self.journal = Journal(data_dir() / "journal.jsonl")
        self.prices_path = data_dir() / "prix.json"
        self.prices: dict[str, float] = self._load_json(self.prices_path, {})
        self.item = Item("Nouvel objet", 200)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(self._build_item_panel(), 3)
        right = QVBoxLayout()
        right.addWidget(self._build_advice_panel(), 3)
        right.addWidget(self._build_exo_panel(), 1)
        right.addWidget(self._build_result_panel(), 1)
        rw = QWidget()
        rw.setLayout(right)
        layout.addWidget(rw, 4)
        self.setCentralWidget(root)
        self.refresh()

    # --- Panneaux -------------------------------------------------------------------

    def _build_item_panel(self) -> QGroupBox:
        box = QGroupBox("Objet")
        v = QVBoxLayout(box)
        form = QFormLayout()
        self.name_edit = QLineEdit(self.item.name)
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 200)
        self.level_spin.setValue(self.item.level)
        self.puits_spin = QDoubleSpinBox()
        self.puits_spin.setRange(0, 10000)
        self.puits_spin.setDecimals(1)
        form.addRow("Nom", self.name_edit)
        form.addRow("Niveau", self.level_spin)
        form.addRow("Puits", self.puits_spin)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(-1, 100)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setSpecialValueText("auto")
        self.quality_spin.setValue(-1)
        self.quality_spin.setToolTip("Qualité de l'objet vue par le jeu. « auto » : poids actuel / poids max.")
        form.addRow("Qualité", self.quality_spin)
        v.addLayout(form)
        self.lines = LinesTable()
        v.addWidget(self.lines)
        h = QHBoxLayout()
        for label, slot in (("Ajouter une ligne", lambda: self.lines.add_row()),
                            ("Supprimer", self.lines.remove_selected),
                            ("Ouvrir…", self.open_item), ("Enregistrer…", self.save_item)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            h.addWidget(b)
        v.addLayout(h)
        upd = QPushButton("Mettre à jour les conseils")
        upd.clicked.connect(self.refresh)
        v.addWidget(upd)
        self.weight_label = QLabel()
        v.addWidget(self.weight_label)
        return box

    def _build_advice_panel(self) -> QGroupBox:
        box = QGroupBox("Prochaine rune")
        v = QVBoxLayout(box)
        h = QHBoxLayout()
        self.mode_value = QRadioButton("La plus intéressante")
        self.mode_safe = QRadioButton("Le plus de chances")
        self.mode_value.setChecked(True)
        grp = QButtonGroup(self)
        for b in (self.mode_value, self.mode_safe):
            grp.addButton(b)
            b.toggled.connect(self.refresh)
            h.addWidget(b)
        v.addLayout(h)
        self.best_label = QLabel()
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        self.best_label.setFont(f)
        self.best_label.setWordWrap(True)
        v.addWidget(self.best_label)
        self.advice_table = QTableWidget(0, 5)
        self.advice_table.setHorizontalHeaderLabels(["Rune", "SC", "Passe", "Prix", "Pourquoi"])
        self.advice_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.advice_table.verticalHeader().setVisible(False)
        self.advice_table.itemChanged.connect(self._price_edited)
        v.addWidget(self.advice_table)
        note = QLabel("Chances calculées avec la formule de Huz, puis affinées avec ton journal de tentatives.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        v.addWidget(note)
        return box

    def _build_exo_panel(self) -> QGroupBox:
        box = QGroupBox("Exo")
        v = QVBoxLayout(box)
        h = QHBoxLayout()
        h.addWidget(QLabel("Exo visée :"))
        self.exo_combo = QComboBox()
        self.exo_combo.addItem("Aucune", None)
        for code in EXO_CHOICES:
            self.exo_combo.addItem(STATS[code].name, code)
        self.exo_combo.currentIndexChanged.connect(self.refresh)
        h.addWidget(self.exo_combo)
        h.addStretch()
        v.addLayout(h)
        self.exo_label = QLabel()
        self.exo_label.setWordWrap(True)
        v.addWidget(self.exo_label)
        return box

    def _build_result_panel(self) -> QGroupBox:
        box = QGroupBox("Résultat de la rune que tu viens de passer")
        v = QVBoxLayout(box)
        h = QHBoxLayout()
        h.addWidget(QLabel("Rune :"))
        self.rune_combo = QComboBox()
        for stat in STATS.values():
            for rune in stat.runes():
                self.rune_combo.addItem(rune.name)
        h.addWidget(self.rune_combo, 1)
        h.addWidget(QLabel("Lignes perdues (ex. vi:15, po:1) :"))
        self.losses_edit = QLineEdit()
        h.addWidget(self.losses_edit, 1)
        v.addLayout(h)
        h2 = QHBoxLayout()
        for outcome in Outcome:
            b = QPushButton(outcome.value)
            b.setMinimumHeight(36)
            b.clicked.connect(lambda _=False, o=outcome: self.record(o))
            h2.addWidget(b)
        cap = QPushButton("Lire l'écran")
        cap.setEnabled(False)
        cap.setToolTip("Bientôt : lecture d'une capture de la fenêtre de forgemagie")
        h2.addWidget(cap)
        v.addLayout(h2)
        return box

    # --- Logique --------------------------------------------------------------------

    def _sync_item(self):
        self.item.name = self.name_edit.text()
        self.item.level = self.level_spin.value()
        self.item.puits = self.puits_spin.value()
        q = self.quality_spin.value()
        self.item.quality = None if q < 0 else q / 100
        self.lines.fill(self.item)

    def advisor(self) -> Advisor:
        return Advisor(prices=self.prices, stats=self.journal.stats())

    def refresh(self):
        self._sync_item()
        adv = self.advisor()
        sugg = adv.safest(self.item) if self.mode_safe.isChecked() else adv.suggestions(self.item)
        self.weight_label.setText(
            f"Poids de l'objet : {self.item.total_weight:g} / {self.item.max_weight:g}   ·   "
            f"Puits : {self.item.puits:g}   ·   Qualité : {quality(self.item):.0%}")
        exo_code = self.exo_combo.currentData()
        exo = adv.exo(self.item, exo_code) if exo_code else None
        if exo and exo.ready:
            self.best_label.setText(f"➜ {exo.rune.name} (exo)")
        elif sugg:
            s = sugg[0]
            self.best_label.setText(f"➜ {s.rune.name} : {s.odds.sc:.0%} de SC, {s.odds.passes:.0%} de passer")
        else:
            self.best_label.setText("Toutes les lignes ont atteint leur objectif.")
        self.exo_label.setText(exo.message if exo else "Choisis une exo pour savoir quand la tenter.")

        self.advice_table.blockSignals(True)
        self.advice_table.setRowCount(0)
        for s in sugg[:12]:
            r = self.advice_table.rowCount()
            self.advice_table.insertRow(r)
            cells = [s.rune.name, f"{s.odds.sc:.0%}", f"{s.odds.passes:.0%}",
                     f"{self.prices.get(s.rune.name, '')}", s.reason]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(str(text))
                if c != 3:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.advice_table.setItem(r, c, it)
        self.advice_table.blockSignals(False)
        if sugg and not (exo and exo.ready):
            self.rune_combo.setCurrentText(sugg[0].rune.name)
        elif exo and exo.ready:
            self.rune_combo.setCurrentText(exo.rune.name)

    def _price_edited(self, cell: QTableWidgetItem):
        if cell.column() != 3:
            return
        rune = self.advice_table.item(cell.row(), 0).text()
        try:
            txt = cell.text().replace(" ", "").replace(",", ".")
            if txt:
                self.prices[rune] = float(txt)
            else:
                self.prices.pop(rune, None)
        except ValueError:
            return
        self.prices_path.write_text(json.dumps(self.prices, ensure_ascii=False, indent=1), encoding="utf-8")
        self.refresh()

    def _parse_losses(self) -> dict[str, int]:
        out: dict[str, int] = {}
        txt = self.losses_edit.text().strip()
        if not txt:
            return out
        for part in txt.split(","):
            code, _, pts = part.partition(":")
            key = code.strip().lower()
            code = next((c for c, l in self.item.lines.items()
                         if key in (c, l.stat.name.lower())), key)
            if code not in self.item.lines:
                raise ValueError(f"« {code} » n'est pas une ligne de l'objet")
            out[code] = int(pts)
        return out

    def record(self, outcome: Outcome):
        self._sync_item()
        rune = find_rune(self.rune_combo.currentText())
        try:
            losses = self._parse_losses()
        except ValueError as exc:
            QMessageBox.warning(self, "TDFM", f"Lignes perdues invalides : {exc}")
            return
        before = self.item.puits
        situation = bucket(self.item, rune)
        self.item.apply(rune, outcome, losses)
        self.journal.add(Attempt(self.item.name, rune.name, situation, outcome.value,
                                 before, self.item.puits))
        self.losses_edit.clear()
        self.lines.load(self.item)
        self.puits_spin.setValue(self.item.puits)
        self.refresh()

    # --- Fichiers -------------------------------------------------------------------

    @staticmethod
    def _load_json(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def save_item(self):
        self._sync_item()
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'objet",
                                              str(data_dir() / f"{self.item.name}.json"), "Objet (*.json)")
        if path:
            Path(path).write_text(json.dumps(item_to_dict(self.item), ensure_ascii=False, indent=1),
                                  encoding="utf-8")

    def open_item(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un objet", str(data_dir()), "Objet (*.json)")
        if path:
            self.set_item(item_from_dict(self._load_json(Path(path), {})))

    def set_item(self, item: Item):
        self.item = item
        self.name_edit.setText(item.name)
        self.level_spin.setValue(item.level)
        self.puits_spin.setValue(item.puits)
        self.quality_spin.setValue(-1 if item.quality is None else round(item.quality * 100))
        self.lines.load(item)
        self.refresh()


STYLE = """
QWidget { background: #14171c; color: #e6e6e6; font-size: 10pt; }
QFrame#card { background: #1d2229; border: 1px solid #2c333d; border-radius: 10px; }
QFrame#card QLabel { background: transparent; }
QLabel#caption { color: #8b95a3; font-size: 9pt; font-weight: bold; letter-spacing: 1px; }
QLabel#big { font-size: 26pt; font-weight: bold; color: #f3c74f; }
QPushButton { background: #2a3340; border: 1px solid #3a4655; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: #33404f; }
QPushButton:disabled { color: #666; }
QTableWidget, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #1b2027; border: 1px solid #2c333d; border-radius: 4px; gridline-color: #2c333d; }
QHeaderView::section { background: #222831; color: #a9b3c0; border: none; padding: 4px; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #1b2027; padding: 8px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #2a3340; color: #f3c74f; }
QGroupBox { border: 1px solid #2c333d; border-radius: 8px; margin-top: 14px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #8b95a3; }
"""


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QTabWidget
        from .ui_live import LivePanel
        self.setWindowTitle(f"TDFM {__version__} : assistant de forgemagie")
        self.resize(820, 860)
        self.manual = MainWindow()
        self.live = LivePanel(self.manual.advisor, self)
        tabs = QTabWidget()
        tabs.addTab(self.live, "Direct (lecture de l'écran)")
        tabs.addTab(self.manual, "Manuel")
        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        self.live.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = AppWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
