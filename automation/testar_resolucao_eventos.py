"""Testa resolução calendário → oddsEventId (Etapa 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_MERCADO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_ESTADO = RAIZ / "frontend" / "public" / "data" / "copa_estado.json"
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.mapeamento_selecoes_odds import chave_confronto  # noqa: E402
from scrapers.odds_armazenamento import (  # noqa: E402
    confrontos_demanda_odds,
    confrontos_na_janela,
    mapa_sigla_por_selecao,
    referencia_hoje,
    scrape_seletivo_habilitado,
)
from scrapers.resolucao_eventos_odds import (  # noqa: E402
    construir_indice_eventos,
    mapear_fixtures,
)
from scrapers.scraper_odds_jogadores import _fixtures_de_confrontos  # noqa: E402


def _modo_playoffs_flexivel() -> bool:
    if not CAMINHO_ESTADO.is_file():
        return False
    try:
        estado = json.loads(CAMINHO_ESTADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(estado.get("playoffs_ativos") or estado.get("transicao_playoffs"))


def _transicao_playoffs() -> bool:
    return _modo_playoffs_flexivel() and not _playoffs_completos()


def _playoffs_completos() -> bool:
    if not CAMINHO_ESTADO.is_file():
        return False
    try:
        estado = json.loads(CAMINHO_ESTADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(estado.get("playoffs_ativos"))


def _confrontos_alvo(hoje, janela: list[dict]) -> tuple[list[dict], str]:
    """Com scrape seletivo, valida só confrontos com demanda (ADV no mercado)."""
    if scrape_seletivo_habilitado() and CAMINHO_MERCADO.is_file():
        mercado = json.loads(CAMINHO_MERCADO.read_text(encoding="utf-8"))
        selecao_sigla = mapa_sigla_por_selecao(mercado)
        demanda = confrontos_demanda_odds(mercado, janela, selecao_sigla, hoje)
        if demanda:
            return demanda, "demanda"
    return janela, "janela"


def main() -> int:
    hoje = referencia_hoje()
    janela = confrontos_na_janela(hoje, 7)
    alvo, rotulo = _confrontos_alvo(hoje, janela)
    fixtures = _fixtures_de_confrontos(alvo)
    por_confronto, por_fixture = construir_indice_eventos()
    mapeados, faltando = mapear_fixtures(fixtures, por_confronto, por_fixture)

    print(f"janela={hoje.isoformat()}..+7d total={len(janela)} validacao={rotulo}={len(alvo)}")
    print(f"indice: confronto={len(por_confronto)} fixture_id={len(por_fixture)}")
    print(f"mapeados={len(mapeados)} faltando={len(faltando)}")

    if faltando:
        print("Sem oddsEventId:")
        for fx in faltando[:15]:
            ch = chave_confronto(fx.get("home", ""), fx.get("away", ""))
            print(f"  {fx.get('home')} vs {fx.get('away')} [{ch}]")
        if len(faltando) > 15:
            print(f"  ... +{len(faltando) - 15}")
        if mapeados and _modo_playoffs_flexivel():
            pct = len(mapeados) / len(alvo) if alvo else 0
            print(
                f"AVISO playoffs: {len(mapeados)}/{len(alvo)} mapeados ({pct:.0%}) — "
                "scrape parcial permitido."
            )
            if pct >= 0.9:
                return 0
        if rotulo == "demanda":
            print(
                "FALHA: confronto com demanda de odds sem oddsEventId "
                "(cache + API OddsNotifier)."
            )
        else:
            print("FALHA: confronto na janela sem oddsEventId.")
        return 1

    ids = {int(m["id"]) for m in mapeados}
    if len(ids) != len(mapeados):
        print("ERRO: event_id duplicado no mapeamento.")
        return 1

    if rotulo == "demanda" and len(alvo) < len(janela):
        print(
            f"OK: 100% dos {len(alvo)} confrontos com demanda mapeados "
            f"(janela completa {len(janela)} — restante sem scrape previsto)."
        )
    else:
        print("OK: 100% dos confrontos na janela mapeados via API/cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
