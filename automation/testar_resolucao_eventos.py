"""Testa resolução calendário → oddsEventId (Etapa 2)."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.mapeamento_selecoes_odds import chave_confronto  # noqa: E402
from scrapers.odds_armazenamento import confrontos_na_janela, referencia_hoje  # noqa: E402
from scrapers.resolucao_eventos_odds import (  # noqa: E402
    construir_indice_eventos,
    mapear_fixtures,
)
from scrapers.scraper_odds_jogadores import _fixtures_de_confrontos  # noqa: E402


def main() -> int:
    hoje = referencia_hoje()
    confrontos = confrontos_na_janela(hoje, 7)
    fixtures = _fixtures_de_confrontos(confrontos)
    por_confronto, por_fixture = construir_indice_eventos()
    mapeados, faltando = mapear_fixtures(fixtures, por_confronto, por_fixture)

    print(f"janela={hoje.isoformat()}..+7d confrontos={len(confrontos)}")
    print(f"indice: confronto={len(por_confronto)} fixture_id={len(por_fixture)}")
    print(f"mapeados={len(mapeados)} faltando={len(faltando)}")

    if faltando:
        print("Sem oddsEventId:")
        for fx in faltando[:15]:
            ch = chave_confronto(fx.get("home", ""), fx.get("away", ""))
            print(f"  {fx.get('home')} vs {fx.get('away')} [{ch}]")
        if len(faltando) > 15:
            print(f"  ... +{len(faltando) - 15}")
        return 1

    ids = {int(m["id"]) for m in mapeados}
    if len(ids) != len(mapeados):
        print("ERRO: event_id duplicado no mapeamento.")
        return 1

    print("OK: 100% dos confrontos na janela mapeados via API/cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
