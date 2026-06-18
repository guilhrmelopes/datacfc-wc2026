"""Valida redução do scrape seletivo vs janela completa."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.odds_armazenamento import (  # noqa: E402
    carregar_armazenamento,
    confrontos_demanda_odds,
    confrontos_na_janela,
    filtrar_confrontos_para_scrape,
    mapa_sigla_por_selecao,
    referencia_hoje,
    scrape_seletivo_habilitado,
)

CAMINHO_MERCADO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"


def main() -> int:
    if not scrape_seletivo_habilitado():
        print("AVISO: ODDS_SCRAPE_COMPLETO ativo — seletivo desligado.")
        return 0

    hoje = referencia_hoje()
    mercado = json.loads(CAMINHO_MERCADO.read_text(encoding="utf-8"))
    selecao_sigla = mapa_sigla_por_selecao(mercado)
    janela = confrontos_na_janela(hoje, 7)
    demanda = confrontos_demanda_odds(mercado, janela, selecao_sigla, hoje)

    armaz = carregar_armazenamento()
    eventos_store = armaz.get("eventos") or {}
    pendentes, frescos = filtrar_confrontos_para_scrape(
        demanda, eventos_store, selecao_sigla, pular_frescos=True,
    )

    print(f"janela={len(janela)} demanda={len(demanda)} pendentes={len(pendentes)} frescos={len(frescos)}")

    if len(janela) == 0:
        print("Sem confrontos na janela.")
        return 0

    if len(demanda) > len(janela):
        print("FALHA: demanda maior que janela.")
        return 1

    reducao = 1 - (len(demanda) / len(janela))
    if len(demanda) >= len(janela):
        print("AVISO: seletivo nao reduziu (ok se poucos ADV no mercado).")
    elif reducao < 0.15:
        print(f"AVISO: reducao baixa ({reducao:.0%}) — verificar mercado.")
    else:
        print(f"OK: reducao ~{reducao:.0%} na fila de scrape.")

    if len(demanda) == 0:
        print("FALHA: nenhum confronto com demanda.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
