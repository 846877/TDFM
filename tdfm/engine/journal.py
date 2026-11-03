"""Journal des tentatives : sert à recalculer les probabilités à partir de tes vrais résultats."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .model import Observed


@dataclass
class Attempt:
    item: str
    rune: str
    bucket: str
    outcome: str  # "SC", "SN" ou "EC"
    puits_before: float
    puits_after: float


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)

    def add(self, attempt: Attempt) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(attempt), ensure_ascii=False) + "\n")

    def attempts(self) -> list[Attempt]:
        if not self.path.exists():
            return []
        out = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                out.append(Attempt(**json.loads(raw)))
        return out

    def stats(self) -> dict[tuple[str, str], Observed]:
        table: dict[tuple[str, str], Observed] = {}
        for a in self.attempts():
            obs = table.setdefault((a.rune, a.bucket), Observed())
            setattr(obs, a.outcome.lower(), getattr(obs, a.outcome.lower()) + 1)
        return table
