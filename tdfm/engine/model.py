"""Probabilités de SC / SN / EC.

Formule de la difficulté D d'après la vidéo de Huz « J'ai PERCÉ le secret de la forgemagie
DOFUS » (Dofus 3) :

    D = 5
      + 45 si 80 % du jet <= valeur <= max         (palier des 80 %)
      + (65 + 4 x poids au-dessus du max) si over   (over)
      + 12 x max(0, ligne / rune - 14)              (règle du x20)
      - 20 x max(0, 1,1 - qualité) si niveau < 170  (niveau 170)
      + 60 x qualité^12                             (qualité de l'objet)

    SC = max(2, (100 - D) / 2) ; SN ~ 50 ; EC = 100 - SC - SN
    Exo PA, PM, PO : 1 % de SC, pas de SN.

« 80 % du jet » = min + 0,8 x (max - min). Les conditions sont évaluées sur la valeur
actuelle de la ligne (avant la rune). La baisse du SN en over et au-delà de D = 100 est lue
sur les graphiques de la vidéo (approximation). Le journal des tentatives corrige le tout.
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


def quality(item: Item) -> float:
    """Qualité de l'objet vue par le jeu (0 à 1).

    Par défaut : poids actuel / poids maximal, plafonné à 1. Peut être forcée via
    `item.quality` si le jeu l'affiche autrement.
    """
    if item.quality is not None:
        return item.quality
    return _clamp(item.total_weight / item.max_weight) if item.max_weight else 1.0


def difficulty(item: Item, rune: Rune) -> float:
    line = item.lines[rune.stat.code]
    cur = line.current
    d = 5.0
    threshold = line.min + 0.8 * (line.max - line.min)
    if threshold <= cur <= line.max:
        d += 45
    if cur > line.max:
        d += 65 + 4 * (cur - line.max) * line.stat.weight
    if rune.value:
        d += 12 * max(0.0, abs(cur) / rune.value - 14)
    q = quality(item)
    if item.level < 170:
        d -= 20 * max(0.0, 1.1 - q)
    d += 60 * q ** 12
    return d


def estimate(item: Item, rune: Rune) -> Odds:
    line = item.lines.get(rune.stat.code)
    if line is None or line.exo:
        if rune.stat.heavy or rune.weight > 20:
            return Odds(EXO_SC, 0.0, 1 - EXO_SC)
        line = None
    if line is None:
        # Exo d'une rune légère : on la traite comme une ligne vide en over.
        sc, sn = 0.02, 0.50
        return Odds(sc, sn, 1 - sc - sn)
    d = difficulty(item, rune)
    sc = max(2.0, (100 - d) / 2) / 100
    if line.current > line.max:
        sn = 50 - 1.5 * (line.current - line.max) * line.stat.weight
    else:
        sn = 50 - 0.375 * max(0.0, d - 100)
    sn = _clamp(sn / 100, 0.0, 1 - sc)
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
