"""Testes do resolver híbrido de status (Cartola + Prováveis lineups)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.cartola_copa_sync import resolver_status_id  # noqa: E402


def main() -> int:
    prov = {100, 200}
    duv = {300}
    casos = [
        (100, 6, 6, "lineup provavel", prov, set()),
        (300, 6, 2, "lineup duvida prevalece sobre cartola 6", prov, duv),
        (300, 7, 2, "lineup duvida sobre nulo", prov, duv),
        (400, 6, 7, "cartola 6 sem lineup", prov, duv),
        (100, 3, 3, "lesionado prevalece", prov, duv),
        (100, 5, 5, "suspenso prevalece", prov, duv),
        (100, 2, 2, "duvida cartola", prov, duv),
        (400, 7, 7, "nulo cartola", prov, duv),
    ]
    for aid, cartola, esperado, desc, p, d in casos:
        obtido = resolver_status_id(aid, cartola, p, d)
        if obtido != esperado:
            print(f"FALHA {desc}: {obtido} != {esperado}")
            return 1
    print("OK: resolver_status_id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
