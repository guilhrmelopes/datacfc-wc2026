"""Valida cobertura mínima de odds_jogadores.json antes de commit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_TOTAL = 500
MIN_G = 0
MIN_A = 0
MIN_GA = 400
MIN_SG = 400

_RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"


def validar(caminho: Path | None = None) -> tuple[int, int, int, int, int]:
    path = caminho or CAMINHO
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    odds = data.get("odds", {})
    total = len(odds)
    g = sum(1 for v in odds.values() if v.get("g_pct"))
    a = sum(1 for v in odds.values() if v.get("a_pct"))
    ga = sum(1 for v in odds.values() if v.get("ga_pct"))
    sg = sum(1 for v in odds.values() if v.get("sg_pct"))
    return total, g, a, ga, sg


def main() -> None:
    total, g, a, ga, sg = validar()
    print(f"total={total} g={g} a={a} ga={ga} sg={sg}")
    if (
        total < MIN_TOTAL
        or g < MIN_G
        or a < MIN_A
        or ga < MIN_GA
        or sg < MIN_SG
    ):
        print("Cobertura insuficiente — abortando commit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
