"""Raspagem isolada da API oficial Cartola Copa (/copa/)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scrapers.cartola_copa import buscar_dados_cartola_copa  # noqa: E402


def main() -> int:
    dados = buscar_dados_cartola_copa()
    print(
        json.dumps(
            {
                "rodada_atual": dados.status.get("rodada_atual"),
                "status_mercado": dados.status.get("status_mercado"),
                "bola_rolando": dados.status.get("bola_rolando"),
                "pontuados": len(dados.pontuados.get("atletas") or {}),
                "mercado_selecoes": len(dados.mercado.get("atletas") or []),
                "partidas": len(dados.partidas.get("partidas") or []),
                "avisos": dados.avisos,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
