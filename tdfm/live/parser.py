"""Lecture de la fenêtre de forgemagie à partir des mots reconnus par l'OCR.

On repère l'en-tête « Min  Max  Effets » puis on lit chaque ligne en dessous :
min, max, valeur actuelle et nom de la caractéristique. On lit aussi le « reliquat ».
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from statistics import median

from .ocr import Word

# Nom affiché dans le jeu -> code TDFM. La clé « % » indique une valeur en pourcentage.
_NAMES: dict[tuple[str, bool], str] = {}


def _add(code: str, *names: str, percent: bool = False):
    for n in names:
        _NAMES[(norm(n), percent)] = code


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z ]+", " ", t)
    words = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in t.split()]
    return " ".join(words)


_add("pa", "PA", "Point d'Action", "Points d'Action")
_add("pm", "PM", "Point de Mouvement", "Points de Mouvement")
_add("po", "Portée")
_add("invo", "Invocations", "Invocation")
_add("do", "Dommages", "Dommage")
_add("pdo_sorts", "Dommages aux sorts", "Dommages sorts", percent=True)
_add("pdo_armes", "Dommages d'armes", "Dommages aux armes", percent=True)
_add("pdo_dist", "Dommages distance", "Dommages à distance", percent=True)
_add("pdo_melee", "Dommages mêlée", "Dommages en mêlée", percent=True)
_add("pres_dist", "Résistance distance", "Résistances distance", "Résistance à distance", percent=True)
_add("pres_melee", "Résistance mêlée", "Résistances mêlée", "Résistance en mêlée", percent=True)
_add("so", "Soins", "Soin")
_add("cri", "Critique", "Coups Critiques", percent=True)
_add("ret_pa", "Retrait PA")
_add("ret_pm", "Retrait PM")
_add("esq_pa", "Esquive PA")
_add("esq_pm", "Esquive PM")
for code, n in [("terre", "Terre"), ("feu", "Feu"), ("eau", "Eau"), ("air", "Air"), ("neutre", "Neutre")]:
    _add(f"pres_{code}", f"Résistance {n}", f"Résistances {n}", percent=True)
    _add(f"res_{code}", f"Résistance {n}", f"Résistances {n}")
    _add(f"do_{code}", f"Dommages {n}", f"Dommage {n}")
_add("do_cri", "Dommages Critiques", "Dommage Critiques")
_add("do_pou", "Dommages Poussée")
_add("renvoi", "Renvoie dommages", "Renvoi de dommages", "Dommages renvoyés")
_add("fuite", "Fuite")
_add("tacle", "Tacle")
_add("sa", "Sagesse")
_add("pp", "Prospection")
_add("pui", "Puissance")
_add("res_cri", "Résistance Critiques", "Résistances Critiques")
_add("res_pou", "Résistance Poussée", "Résistances Poussée")
_add("fo", "Force")
_add("ine", "Intelligence")
_add("cha", "Chance")
_add("age", "Agilité")
_add("pod", "Pods", "Pod")
_add("vi", "Vitalité")
_add("ini", "Initiative")

_NUM = re.compile(r"^[+\-−–]?\d+%?$")
_DEC = re.compile(r"(\d+(?:[.,]\d+)?)")


def match_stat(name: str, percent: bool) -> str | None:
    key = norm(name)
    if not key:
        return None
    exact = _NAMES.get((key, percent)) or _NAMES.get((key, not percent))
    if exact:
        return exact
    keys = [k for (k, p) in _NAMES if p == percent] or [k for k, _ in _NAMES]
    best = difflib.get_close_matches(key, keys, n=1, cutoff=0.75)
    if not best:
        best = difflib.get_close_matches(key, [k for k, _ in _NAMES], n=1, cutoff=0.8)
        if not best:
            return None
    return _NAMES.get((best[0], percent)) or _NAMES.get((best[0], not percent))


def _int(token: str) -> int | None:
    t = token.replace("−", "-").replace("–", "-").replace("%", "").replace("+", "")
    try:
        return int(t)
    except ValueError:
        return None


@dataclass
class ReadLine:
    code: str
    min: int | None
    max: int | None
    current: int
    raw: str = ""


@dataclass
class ForgeState:
    lines: list[ReadLine] = field(default_factory=list)
    reliquat: float | None = None

    def key(self) -> tuple:
        return (tuple((l.code, l.current) for l in self.lines), self.reliquat)


def _find(words: list[Word], target: str) -> list[Word]:
    return [w for w in words if norm(w.text) == target]


def _rows(words: list[Word]) -> list[list[Word]]:
    if not words:
        return []
    tol = 0.6 * median(w.h for w in words)
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda w: w.cy):
        if rows and abs(rows[-1][-1].cy - w.cy) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w.x) for r in rows]


def find_header(words: list[Word]):
    """Retourne (min, max, effets, modif) : les mots de l'en-tête du tableau."""
    for mn in _find(words, "min"):
        same_row = [w for w in words if abs(w.cy - mn.cy) <= max(mn.h, 8) and w.x > mn.x]
        mx = next((w for w in sorted(same_row, key=lambda w: w.x) if norm(w.text) == "max"), None)
        if not mx:
            continue
        eff = next((w for w in sorted(same_row, key=lambda w: w.x) if norm(w.text).startswith("effet")), None)
        if not eff:
            continue
        modif = next((w for w in same_row if norm(w.text).startswith("modif")), None)
        return mn, mx, eff, modif
    return None


def read_reliquat(words: list[Word]) -> float | None:
    for w in words:
        if "reliquat" not in norm(w.text):
            continue
        after = [o for o in words if abs(o.cy - w.cy) <= max(w.h, 8) and o.x >= w.x]
        text = " ".join(o.text for o in sorted(after, key=lambda o: o.x))
        if ":" not in text:
            continue
        m = _DEC.search(text.split(":", 1)[1])
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def parse_forge(words: list[Word]) -> ForgeState | None:
    header = find_header(words)
    if header is None:
        return None
    mn, mx, eff, modif = header
    col = mx.cx - mn.cx
    left = mn.x - col
    right = modif.x - 2 if modif else eff.x + 12 * col
    body = [w for w in words if w.cy > mn.cy + mn.h * 0.8 and left <= w.cx <= right]
    state = ForgeState(reliquat=read_reliquat(words))
    seen: set[str] = set()
    for row in _rows(body):
        min_v = max_v = None
        rest = []
        for w in row:
            if w.cx < (mn.cx + mx.cx) / 2 and _NUM.match(w.text) and abs(w.cx - mn.cx) < col * 0.6:
                min_v = _int(w.text)
            elif w.cx < eff.x - col * 0.15 and _NUM.match(w.text) and abs(w.cx - mx.cx) < col * 0.6:
                max_v = _int(w.text)
            elif w.cx >= eff.x - col * 0.3:
                rest.append(w)
            elif w.text in ("-", "–", "—"):
                pass
        # Valeur = dernier nombre avant le nom ; nom = mots qui suivent.
        value_idx = None
        for i, w in enumerate(rest):
            if _NUM.match(w.text) or re.match(r"^[+\-−–]?\d+%$", w.text):
                value_idx = i
            elif value_idx is not None and re.search(r"[A-Za-zÀ-ÿ]{2,}", w.text):
                break
        if value_idx is None:
            continue
        value_tok = rest[value_idx].text
        name_words = []
        for w in rest[value_idx + 1:]:
            if _NUM.match(w.text):
                break
            name_words.append(w.text)
        percent = value_tok.endswith("%") or (name_words and name_words[0] == "%")
        if name_words and name_words[0] == "%":
            name_words = name_words[1:]
        name = " ".join(name_words)
        code = match_stat(name, percent)
        value = _int(value_tok)
        if code is None or value is None or code in seen:
            continue
        seen.add(code)
        state.lines.append(ReadLine(code, min_v, max_v, value, raw=" ".join(w.text for w in row)))
    return state if state.lines else None
