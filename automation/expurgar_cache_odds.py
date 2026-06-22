"""Remove cache de odds contaminado (casas não autorizadas) e zera armazenamento."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.odds_armazenamento import limpar_armazenamento_odds  # noqa: E402


def main() -> int:
    limpar_armazenamento_odds()
    print("Cache de odds expurgado. Execute o scraper para re-raspar todos os eventos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
