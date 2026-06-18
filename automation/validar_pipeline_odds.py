"""Validações rápidas antes do scrape de odds (matching, eventos, parser, aliases)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "avaliar_matching_odds.py",
    "testar_resolucao_eventos.py",
    "testar_parser_odds_api.py",
    "testar_aprendizado_aliases.py",
    "testar_scrape_seletivo.py",
)


def main() -> int:
    python = sys.executable
    falhas: list[str] = []
    for nome in SCRIPTS:
        caminho = RAIZ / "automation" / nome
        print(f"--- {nome} ---")
        r = subprocess.run([python, str(caminho)], cwd=RAIZ, check=False)
        if r.returncode != 0:
            falhas.append(nome)
    if falhas:
        print(f"Pipeline odds: FALHOU ({', '.join(falhas)})")
        return 1
    print("Pipeline odds: todas as validações OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
