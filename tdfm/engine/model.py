"""Probabilités estimées de SC / SN / EC.

ATTENTION : Ankama ne publie pas la formule. Ce modèle est une heuristique fondée sur les
observations communautaires :
  - les chances baissent quand la ligne approche ou dépasse son max ;
  - elles baissent quand l'objet est déjà « chargé » en poids ;
  - en exo, les runes lourdes (PA, PM, PO) ont 1 % de SC et pas de SN.
Les statistiques réelles du joueur (journal) viennent corriger cette estimation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .item import Item
from .runes import Rune

EXO_SC = 0.01


@dataclass(frozen=True)
class Odds:
    sc: float
    sn: float
    ec: float

    @property
    def passes(self) -> float:
        """Probabilité que la rune s'ajoute (SC ou SN)."""
        return self.sc + self.sn


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def bucket(item: Item, rune: Rune) -> str:
    """Catégorie de situation, utilisée pour regrouper les statistiques du journal."""
    line = item.lines.get(rune.stat.code)
    if line is None or line.exo:
        return "exo"
    after = line.current + rune.value
    if after > line.max:
        return "over"
    fill = after / line.max if line.max else 1.0
    return "bas" if fill <= 0.5 else ("haut" if fill <= 0.85 else "max")


def estimate(item: Item, rune: Rune) -> Odds:
    line = item.lines.get(rune.stat.code)
    if line is None or line.exo:
        if rune.stat.heavy or rune.weight > 20:
            return Odds(EXO_SC, 0.0, 1 - EXO_SC)
        return Odds(0.05, 0.25, 0.70)

    after = line.current + rune.value
    load = item.total_weight / item.max_weight if item.max_weight else 1.0
    load_penalty = 1 - 0.3 * _clamp((load - 0.8) / 0.4)

    if after > line.max:
        over_pts = after - line.max
        frac = _clamp(over_pts / line.stat.over_cap)
        sc = (0.08 - 0.06 * frac) * load_penalty
        sn = 0.35 - 0.15 * frac
    else:
        fill = after / line.max if line.max > 0 else 1.0
        sc = (0.05 + 0.65 * (1 - fill) ** 0.7) * load_penalty
        ec = 0.10 + 0.30 * fill
        sn = 1 - sc - ec
    sc, sn = _clamp(sc), _clamp(sn)
    sn = min(sn, 1 - sc)
    return Odds(sc, sn, 1 - sc - sn)


@dataclass
class Observed:
    sc: int = 0
    sn: int = 0
    ec: int = 0

    @property
    def n(self) -> int:
        return self.sc + self.sn + self.ec


def blend(prior: Odds, obs: Observed | None, strength: float = 15.0) -> Odds:
    """Mélange l'estimation avec les résultats observés (prior de Dirichlet).

    Plus le joueur a de tentatives dans une situation, plus elles pèsent.
    """
    if obs is None or obs.n == 0:
        return prior
    tot = strength + obs.n
    return Odds(
        (prior.sc * strength + obs.sc) / tot,
        (prior.sn * strength + obs.sn) / tot,
        (prior.ec * strength + obs.ec) / tot,
    )
