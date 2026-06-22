"""Re-raspa um único evento OddsNotifier e recompila odds_jogadores.json."""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from scrapers.odds_armazenamento import (  # noqa: E402
    carregar_armazenamento,
    compilar_e_salvar,
    enriquecer_confronto,
    mapa_sigla_por_selecao,
    montar_registro_evento,
    referencia_hoje,
    salvar_armazenamento,
)
from scrapers.scraper_odds_jogadores import (  # noqa: E402
    Relatorio,
    STEALTH_INIT_SCRIPT,
    _headless,
    _url_evento,
    carregar_jogadores,
    carregar_todos_jogadores,
    processar_evento,
)
from utils.interceptacao_rede_oddsnotifier import ArmazenamentoCapturaOdds  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("raspar_evento")

CAMINHO_GRUPOS = RAIZ / "frontend" / "public" / "data" / "grupos_wc2026.json"
CAMINHO_MERCADO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"


def _confronto_por_event_id(event_id: int) -> dict | None:
    armaz = carregar_armazenamento()
    bruto = armaz.get("eventos", {}).get(str(event_id))
    if isinstance(bruto, dict):
        return bruto

    if not CAMINHO_GRUPOS.is_file():
        return None
    grupos = json.loads(CAMINHO_GRUPOS.read_text(encoding="utf-8"))
    jogadores = json.loads(CAMINHO_MERCADO.read_text(encoding="utf-8"))
    sigla_map = mapa_sigla_por_selecao(jogadores)

    for c in grupos.get("confrontos") or []:
        enriquecido = enriquecer_confronto(c, sigla_map)
        # tentativa via cache eventos_odds_rodada1
        pass
    return None


def _evento_de_armazenamento(event_id: int) -> tuple[dict, dict] | None:
    armaz = carregar_armazenamento()
    reg = armaz.get("eventos", {}).get(str(event_id))
    if not isinstance(reg, dict):
        return None
    evento = {
        "id": event_id,
        "home": reg.get("home") or reg.get("mandante", ""),
        "away": reg.get("away") or reg.get("visitante", ""),
        "date": reg.get("data", ""),
        "rodada": reg.get("rodada"),
        "grupo": reg.get("grupo", ""),
        "confronto": reg,
    }
    return evento, reg


def main() -> int:
    bruto = os.environ.get("ODDS_EVENT_ID", "").strip() or (
        sys.argv[1] if len(sys.argv) > 1 else ""
    )
    if not bruto.isdigit():
        log.error("Informe ODDS_EVENT_ID ou argumento numérico (ex.: 66457000).")
        return 1

    event_id = int(bruto)
    par = _evento_de_armazenamento(event_id)
    if not par:
        log.error("Evento %d não encontrado no armazenamento.", event_id)
        return 1

    evento, confronto = par
    log.info(
        "Re-scrape: %s vs %s (id=%d, data=%s)",
        evento.get("home"),
        evento.get("away"),
        event_id,
        confronto.get("data"),
    )

    jogadores = carregar_jogadores(CAMINHO_MERCADO)
    jogadores_todos = carregar_todos_jogadores(CAMINHO_MERCADO)
    if not jogadores:
        log.error("jogadores_mercado.json vazio.")
        return 1

    armazenamento = carregar_armazenamento()
    eventos_store: dict[str, dict] = armazenamento.setdefault("eventos", {})
    chave = str(event_id)
    eventos_store.pop(chave, None)

    relatorio = Relatorio()
    extras: dict = {}
    odds_evento: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=_headless(),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-size=1440,900",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        ctx.add_init_script(STEALTH_INIT_SCRIPT)
        pagina = ctx.new_page()
        rsc_acumulado: list[str] = []
        captura_api = ArmazenamentoCapturaOdds(log)
        captura_api.vincular_pagina(pagina)

        def _capturar_rsc(resp) -> None:
            if "oddsnotifier" not in resp.url:
                return
            try:
                texto = resp.text()
                if texto and ("bookmakers" in texto or "__next_f" in texto):
                    rsc_acumulado.append(texto)
            except Exception:
                pass

        pagina.on("response", _capturar_rsc)

        log.info("Warm-up: %s", _url_evento(event_id))
        pagina.goto(_url_evento(event_id), timeout=55000, wait_until="domcontentloaded")
        pagina.wait_for_timeout(random.randint(5000, 8000))

        max_tentativas = int(os.environ.get("ODDS_EVENT_RETRIES", "3"))
        n = 0
        for tentativa in range(1, max_tentativas + 1):
            odds_evento = {}
            extras = {}
            log.info("Tentativa %d/%d...", tentativa, max_tentativas)
            n = processar_evento(
                evento,
                pagina,
                jogadores,
                jogadores_todos,
                odds_evento,
                relatorio,
                rsc_acumulado,
                modo_armazenamento=True,
                captura_api=captura_api,
                extras_evento=extras,
            )
            if n >= int(os.environ.get("ODDS_MIN_ODDS_EVENTO", "45")):
                break
            log.warning("Apenas %d atletas — recarregando página...", n)
            pagina.reload(timeout=55000, wait_until="domcontentloaded")
            pagina.wait_for_timeout(random.randint(8000, 12000))

        ctx.close()
        browser.close()

    if n <= 0:
        log.error("Scrape falhou para evento %d.", event_id)
        relatorio.imprimir()
        return 1

    eventos_store[chave] = montar_registro_evento(
        evento, confronto, odds_evento, ml=extras or None,
    )
    eventos_store[chave]["raspar_em"] = datetime.now(tz=timezone.utc).isoformat()

    hoje = referencia_hoje()
    armazenamento["referencia_data"] = hoje.isoformat()
    armazenamento["atualizado_em"] = datetime.now(tz=timezone.utc).isoformat()
    salvar_armazenamento(armazenamento)

    relatorio.imprimir()
    log.info("Evento %d: %d atletas raspados.", event_id, n)

    odds = compilar_e_salvar(hoje=hoje)
    log.info("Dashboard recompilado: %d atletas.", len(odds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
