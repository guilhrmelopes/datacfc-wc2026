"""Valida cobertura mínima de odds_jogadores.json antes de commit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_TOTAL = 500
MIN_GA = 400
MIN_SG = 400

_RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"


def validar(caminho: Path | None = None) -> tuple[int, int, int]:
    path = caminho or CAMINHO
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    odds = data.get("odds", {})
    total = len(odds)
    ga = sum(1 for v in odds.values() if v.get("ga_pct"))
    sg = sum(1 for v in odds.values() if v.get("sg_pct"))
    return total, ga, sg


def main() -> None:
    total, ga, sg = validar()
    print(f"total={total} ga={ga} sg={sg}")
    if total < MIN_TOTAL or ga < MIN_GA or sg < MIN_SG:
        print("Cobertura insuficiente — abortando commit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
