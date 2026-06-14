"""Raspa odds e valida cobertura (uso local, CI e scripts PowerShell)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    scrape = subprocess.run(
        [sys.executable, "-m", "src.scrapers.scraper_odds_jogadores"],
        cwd=RAIZ,
        check=False,
    )
    validar = subprocess.run(
        [sys.executable, str(RAIZ / "automation" / "validar_odds.py")],
        cwd=RAIZ,
        check=False,
    )
    if validar.returncode != 0:
        return validar.returncode
    if scrape.returncode != 0:
        print(
            f"AVISO: scraper exit {scrape.returncode}, mas validacao OK.",
            file=sys.stderr,
        )
        return scrape.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
