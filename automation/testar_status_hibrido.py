"""Testes do resolver híbrido de status (Cartola + Prováveis lineups)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.cartola_copa_sync import resolver_status_id  # noqa: E402


def main() -> int:
    prov = {100, 200}
    casos = [
        (100, 6, 6, "lineup provavel"),
        (300, 6, 7, "cartola 6 sem lineup"),
        (100, 3, 3, "lesionado prevalece"),
        (100, 5, 5, "suspenso prevalece"),
        (100, 2, 2, "duvida cartola"),
        (400, 7, 7, "nulo cartola"),
    ]
    for aid, cartola, esperado, desc in casos:
        obtido = resolver_status_id(aid, cartola, prov)
        if obtido != esperado:
            print(f"FALHA {desc}: {obtido} != {esperado}")
            return 1
    print("OK: resolver_status_id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
