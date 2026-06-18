"""Raspa odds e valida cobertura (uso local, CI e scripts PowerShell)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

SOFT_FAIL = os.environ.get("ODDS_SOFT_FAIL", "").strip().lower() in ("1", "true", "yes")


def main() -> int:
    env = os.environ.copy()
    src = str(RAIZ / "src")
    env["PYTHONPATH"] = src if not env.get("PYTHONPATH") else f"{src}{os.pathsep}{env['PYTHONPATH']}"

    skip_preflight = os.environ.get("ODDS_SKIP_PREFLIGHT", "").strip().lower() in ("1", "true", "yes")
    if not skip_preflight:
        pre = subprocess.run(
            [sys.executable, str(RAIZ / "automation" / "validar_pipeline_odds.py")],
            cwd=RAIZ,
            env=env,
            check=False,
        )
        if pre.returncode != 0:
            return pre.returncode

    scrape = subprocess.run(
        [sys.executable, "-m", "scrapers.scraper_odds_jogadores"],
        cwd=RAIZ,
        env=env,
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
        msg = (
            f"AVISO: scraper exit {scrape.returncode}, mas validacao OK "
            "(dados anteriores preservados)."
        )
        print(msg, file=sys.stderr)
        if SOFT_FAIL:
            return 0
        return scrape.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
