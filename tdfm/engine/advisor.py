"""Conseils : quelle rune passer ensuite, et quand tenter l'exo."""

from __future__ import annotations

from dataclasses import dataclass

from .item import Item
from .model import Odds, Observed, blend, bucket, estimate
from .runes import Rune, get_stat


@dataclass
class Suggestion:
    rune: Rune
    odds: Odds
    expected_gain: float  # poids utile gagné en moyenne (pondéré par la priorité)
    expected_loss: float  # poids retiré des lignes en moyenne (après le puits)
    score: float  # intérêt par kama (ou par tentative si pas de prix)
    reason: str


@dataclass
class ExoAdvice:
    rune: Rune
    ready: bool
    puits_missing: float
    expected_attempts: float
    expected_cost: float | None
    message: str


class Advisor:
    def __init__(self, prices: dict[str, float] | None = None,
                 stats: dict[tuple[str, str], Observed] | None = None,
                 loss_aversion: float = 1.0):
        self.prices = prices or {}
        self.stats = stats or {}
        self.loss_aversion = loss_aversion

    def odds(self, item: Item, rune: Rune) -> Odds:
        return blend(estimate(item, rune), self.stats.get((rune.name, bucket(item, rune))))

    def evaluate(self, item: Item, rune: Rune) -> Suggestion:
        line = item.lines[rune.stat.code]
        odds = self.odds(item, rune)
        useful = min(rune.value, line.missing)
        gain = odds.passes * useful * rune.stat.weight * line.priority
        uncovered = max(0.0, rune.weight - item.puits)
        loss = (odds.sn + odds.ec) * uncovered
        price = self.prices.get(rune.name)
        net = gain - self.loss_aversion * loss
        score = net / price if price else net
        if uncovered == 0:
            reason = f"le puits ({item.puits:g}) couvre la rune : aucun risque de perte"
        elif useful < rune.value:
            reason = f"rune trop forte : seuls {useful} points sur {rune.value} sont utiles"
        else:
            reason = f"{odds.sc:.0%} de SC, {odds.passes:.0%} de chances que la rune passe"
        return Suggestion(rune, odds, gain, loss, score, reason)

    def suggestions(self, item: Item) -> list[Suggestion]:
        """Runes classées de la plus intéressante à la moins intéressante."""
        out = []
        for line in item.lines.values():
            if line.missing <= 0 or line.exo:
                continue
            for rune in line.stat.runes():
                out.append(self.evaluate(item, rune))
        return sorted(out, key=lambda s: s.score, reverse=True)

    def safest(self, item: Item) -> list[Suggestion]:
        """Runes classées par chance de succès critique."""
        return sorted(self.suggestions(item), key=lambda s: s.odds.sc, reverse=True)

    def exo(self, item: Item, stat_code: str) -> ExoAdvice:
        stat = get_stat(stat_code)
        rune = stat.runes()[0]
        line = item.lines.get(stat_code)
        if line is not None and not line.exo and line.max > 0:
            return ExoAdvice(rune, False, 0, 0, None,
                             f"{stat.name} est déjà une ligne normale de l'objet : c'est un over, pas une exo.")
        if line is not None and line.current > 0:
            return ExoAdvice(rune, False, 0, 0, None, f"L'exo {stat.name} est déjà passée.")
        odds = self.odds(item, rune)
        attempts = 1 / odds.sc if odds.sc > 0 else float("inf")
        missing = max(0.0, rune.weight - item.puits)
        price = self.prices.get(rune.name)
        cost = attempts * price if price else None
        unfinished = [l for l in item.lines.values() if l.missing > 0 and not l.exo]
        if missing == 0:
            msg = (f"Passe la {rune.name} maintenant : le puits ({item.puits:g}) couvre son poids "
                   f"({rune.weight:g}), un échec ne fera sauter aucune ligne. "
                   f"Compte environ {attempts:.0f} tentatives en moyenne ({odds.sc:.0%} par essai).")
            ready = True
        else:
            msg = (f"Pas encore : il manque {missing:g} de puits pour couvrir la {rune.name} "
                   f"(poids {rune.weight:g}). Un échec maintenant ferait sauter des lignes.")
            ready = False
        if unfinished and ready:
            msg += (" Astuce : finis l'exo avant de remonter "
                    + ", ".join(l.stat.name for l in unfinished)
                    + ", tant que le puits protège tes lignes.")
        return ExoAdvice(rune, ready, missing, attempts, cost, msg)
