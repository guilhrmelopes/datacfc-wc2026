"""Recompila odds_jogadores.json a partir do armazenamento (virada de dia, sem scrape)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.odds_armazenamento import compilar_e_salvar  # noqa: E402


def main() -> int:
    odds = compilar_e_salvar()
    print(f"compilados={len(odds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
