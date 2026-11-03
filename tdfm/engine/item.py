"""État d'un objet en cours de forgemagie : lignes, poids, puits."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .runes import Rune, Stat, get_stat


class Outcome(str, Enum):
    SC = "SC"  # succès critique : la rune passe, rien ne saute
    SN = "SN"  # succès neutre : la rune passe, son poids est retiré ailleurs
    EC = "EC"  # échec critique : la rune ne passe pas, son poids est retiré


@dataclass
class Line:
    stat: Stat
    min: int
    max: int
    current: int
    target: int | None = None  # valeur visée par le joueur (par défaut : le max)
    priority: float = 1.0  # importance de la ligne pour le joueur

    @property
    def exo(self) -> bool:
        """Ligne absente du jet théorique (ajoutée en exo)."""
        return self.max == 0 and self.min == 0

    @property
    def weight(self) -> float:
        return max(0, self.current) * self.stat.weight

    @property
    def max_weight(self) -> float:
        return max(0, self.max) * self.stat.weight

    @property
    def over(self) -> int:
        return max(0, self.current - self.max)

    @property
    def goal(self) -> int:
        return self.max if self.target is None else self.target

    @property
    def missing(self) -> int:
        return max(0, self.goal - self.current)


@dataclass
class Item:
    name: str
    level: int
    lines: dict[str, Line] = field(default_factory=dict)
    puits: float = 0.0

    def add_line(self, code: str, min_: int, max_: int, current: int | None = None, **kw) -> Line:
        line = Line(get_stat(code), min_, max_, max_ if current is None else current, **kw)
        self.lines[code] = line
        return line

    def line_for(self, stat: Stat) -> Line:
        if stat.code not in self.lines:
            # Nouvelle ligne : c'est une exo.
            self.lines[stat.code] = Line(stat, 0, 0, 0)
        return self.lines[stat.code]

    @property
    def total_weight(self) -> float:
        return sum(l.weight for l in self.lines.values())

    @property
    def max_weight(self) -> float:
        return sum(l.max_weight for l in self.lines.values())

    def apply(self, rune: Rune, outcome: Outcome, losses: dict[str, int] | None = None,
              puits_seen: float | None = None) -> float:
        """Applique le résultat d'une rune.

        `losses` : points perdus par ligne (lu sur l'écran ou saisi).
        `puits_seen` : valeur du puits affichée par le jeu, si connue (prioritaire).
        Retourne la variation du puits.
        """
        losses = losses or {}
        before = self.puits
        if outcome in (Outcome.SC, Outcome.SN):
            self.line_for(rune.stat).current += rune.value
        lost_weight = 0.0
        for code, pts in losses.items():
            line = self.lines[code]
            line.current -= pts
            lost_weight += pts * line.stat.weight
        if outcome is not Outcome.SC:
            # Reliquat = poids perdu - poids de la rune ; le puits ne descend pas sous 0.
            self.puits = max(0.0, self.puits + lost_weight - rune.weight)
        if puits_seen is not None:
            self.puits = float(puits_seen)
        # Une ligne exo retombée à 0 disparaît.
        for code in [c for c, l in self.lines.items() if l.exo and l.current <= 0]:
            del self.lines[code]
        return self.puits - before
