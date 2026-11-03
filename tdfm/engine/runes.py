"""Table des caractéristiques et des runes (Dofus 3 / Unity).

Sources : guides communautaires (JeuxOnline, Gamosaurus, Sigilos). Le poids est donné
par point de caractéristique. Les runes Pa et Ra valent 3x et 10x la rune de base.
"""

from __future__ import annotations

from dataclasses import dataclass

# Plafond d'over : on ne peut pas dépasser le max théorique de plus de 101 de densité.
OVER_CAP_WEIGHT = 101.0


@dataclass(frozen=True)
class Stat:
    code: str
    name: str
    weight: float  # poids par point
    rune_values: tuple[int, ...]  # gain des runes disponibles : (base, Pa, Ra)
    rune_names: tuple[str, ...]
    heavy: bool = False  # PA, PM, PO... : pas de succès neutre en exo

    def runes(self) -> list["Rune"]:
        return [Rune(self, n, v) for n, v in zip(self.rune_names, self.rune_values)]

    @property
    def over_cap(self) -> float:
        """Nombre de points d'over maximum au-delà du max théorique."""
        pts = OVER_CAP_WEIGHT / self.weight
        # Pour les runes lourdes, au moins un point d'over est autorisé (ex. +1 PA).
        return max(1, int(pts + 1e-9))


@dataclass(frozen=True)
class Rune:
    stat: Stat
    name: str
    value: int

    @property
    def weight(self) -> float:
        return self.stat.weight * self.value


def _s(code, name, weight, values, names, heavy=False):
    return Stat(code, name, weight, tuple(values), tuple(names), heavy)


STATS: dict[str, Stat] = {s.code: s for s in [
    _s("pa", "PA", 100, [1], ["Ga Pa"], heavy=True),
    _s("pm", "PM", 90, [1], ["Ga Pme"], heavy=True),
    _s("po", "Portée", 51, [1], ["Po"], heavy=True),
    _s("invo", "Invocation", 30, [1], ["Invo"]),
    _s("do", "Dommages", 20, [1], ["Do"]),
    _s("pdo_sorts", "% Dommages aux sorts", 15, [1], ["Do Per So"]),
    _s("pdo_armes", "% Dommages d'armes", 15, [1], ["Do Per Ar"]),
    _s("pdo_dist", "% Dommages distance", 15, [1], ["Do Per Di"]),
    _s("pdo_melee", "% Dommages mêlée", 15, [1], ["Do Per Mé"]),
    _s("pres_dist", "% Résistance distance", 15, [1], ["Ré Per Di"]),
    _s("pres_melee", "% Résistance mêlée", 15, [1], ["Ré Per Mé"]),
    _s("so", "Soins", 10, [1, 3], ["So", "Pa So"]),
    _s("cri", "% Critique", 10, [1], ["Cri"]),
    _s("ret_pa", "Retrait PA", 7, [1, 3], ["Ret Pa", "Pa Ret Pa"]),
    _s("ret_pm", "Retrait PM", 7, [1, 3], ["Ret Pme", "Pa Ret Pme"]),
    _s("esq_pa", "Esquive PA", 7, [1, 3], ["Ré Pa", "Pa Ré Pa"]),
    _s("esq_pm", "Esquive PM", 7, [1, 3], ["Ré Pme", "Pa Ré Pme"]),
    *[_s(f"pres_{e}", f"% Résistance {n}", 6, [1], [f"Ré Per {n}"])
      for e, n in [("terre", "Terre"), ("feu", "Feu"), ("eau", "Eau"), ("air", "Air"), ("neutre", "Neutre")]],
    *[_s(f"do_{e}", f"Dommages {n}", 5, [1, 3], [f"Do {n}", f"Pa Do {n}"])
      for e, n in [("terre", "Terre"), ("feu", "Feu"), ("eau", "Eau"), ("air", "Air"), ("neutre", "Neutre")]],
    _s("do_cri", "Dommages Critiques", 5, [1, 3], ["Do Cri", "Pa Do Cri"]),
    _s("do_pou", "Dommages Poussée", 5, [1, 3], ["Do Pou", "Pa Do Pou"]),
    _s("renvoi", "Renvoie dommages", 5, [1], ["Do Ren"]),
    _s("fuite", "Fuite", 4, [1, 3], ["Fui", "Pa Fui"]),
    _s("tacle", "Tacle", 4, [1, 3], ["Tac", "Pa Tac"]),
    _s("sa", "Sagesse", 3, [1, 3, 10], ["Sa", "Pa Sa", "Ra Sa"]),
    _s("pp", "Prospection", 3, [1, 3], ["Prospe", "Pa Prospe"]),
    _s("pui", "Puissance", 2, [1, 3, 10], ["Pui", "Pa Pui", "Ra Pui"]),
    *[_s(f"res_{e}", f"Résistance {n}", 2, [1, 3], [f"Ré {n}", f"Pa Ré {n}"])
      for e, n in [("terre", "Terre"), ("feu", "Feu"), ("eau", "Eau"), ("air", "Air"), ("neutre", "Neutre")]],
    _s("res_cri", "Résistance Critiques", 2, [1, 3], ["Ré Cri", "Pa Ré Cri"]),
    _s("res_pou", "Résistance Poussée", 2, [1, 3], ["Ré Pou", "Pa Ré Pou"]),
    _s("fo", "Force", 1, [1, 3, 10], ["Fo", "Pa Fo", "Ra Fo"]),
    _s("ine", "Intelligence", 1, [1, 3, 10], ["Ine", "Pa Ine", "Ra Ine"]),
    _s("cha", "Chance", 1, [1, 3, 10], ["Cha", "Pa Cha", "Ra Cha"]),
    _s("age", "Agilité", 1, [1, 3, 10], ["Age", "Pa Age", "Ra Age"]),
    _s("pod", "Pods", 0.25, [10, 30, 100], ["Pod", "Pa Pod", "Ra Pod"]),
    _s("vi", "Vitalité", 0.2, [5, 15, 50], ["Vi", "Pa Vi", "Ra Vi"]),
    _s("ini", "Initiative", 0.1, [10, 30, 100], ["Ini", "Pa Ini", "Ra Ini"]),
]}


def get_stat(code: str) -> Stat:
    try:
        return STATS[code]
    except KeyError as exc:
        raise KeyError(f"Caractéristique inconnue : {code}") from exc


def find_rune(name: str) -> Rune:
    for stat in STATS.values():
        for rune in stat.runes():
            if rune.name.lower() == name.lower():
                return rune
    raise KeyError(f"Rune inconnue : {name}")
