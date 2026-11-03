"""Suivi en direct : transforme ce qui est lu à l'écran en objet TDFM."""

from __future__ import annotations

from dataclasses import dataclass

from ..engine.item import Item
from .parser import ForgeState


@dataclass
class Change:
    outcome: str  # "SC", "SN" ou "EC"
    gained: dict[str, int]
    lost: dict[str, int]
    reliquat_delta: float


class LiveTracker:
    def __init__(self, level: int = 200):
        self.level = level
        self.bounds: dict[str, tuple[int, int]] = {}
        self.reliquat = 0.0
        self.last: ForgeState | None = None
        self.item: Item | None = None

    def update(self, state: ForgeState) -> Change | None:
        """Intègre une nouvelle lecture. Retourne le changement détecté, s'il y en a un."""
        for l in state.lines:
            if l.min is not None and l.max is not None:
                lo, hi = sorted((l.min, l.max))
                self.bounds[l.code] = (lo, hi)
        if state.reliquat is not None:
            new_rel = state.reliquat
        else:
            new_rel = self.reliquat
        change = self._diff(self.last, state, new_rel) if self.last else None
        self.reliquat = new_rel
        self.last = state
        self.item = self._build(state)
        return change

    def _build(self, state: ForgeState) -> Item:
        item = Item("Objet lu à l'écran", self.level, puits=self.reliquat)
        for l in state.lines:
            lo, hi = self.bounds.get(l.code, (0, 0))
            item.add_line(l.code, lo, hi, l.current)
        return item

    def _diff(self, old: ForgeState, new: ForgeState, new_rel: float) -> Change | None:
        before = {l.code: l.current for l in old.lines}
        after = {l.code: l.current for l in new.lines}
        gained, lost = {}, {}
        for code in before.keys() | after.keys():
            d = after.get(code, 0) - before.get(code, 0)
            if d > 0:
                gained[code] = d
            elif d < 0:
                lost[code] = -d
        rel_delta = new_rel - self.reliquat
        if not gained and not lost and abs(rel_delta) < 1e-9:
            return None
        if gained and not lost and abs(rel_delta) < 1e-9:
            outcome = "SC"
        elif gained:
            outcome = "SN"
        else:
            outcome = "EC"
        return Change(outcome, gained, lost, rel_delta)
