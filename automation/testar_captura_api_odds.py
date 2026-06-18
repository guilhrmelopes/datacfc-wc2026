"""Smoke test: captura API OddsNotifier para um evento (Etapa 3)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from scrapers.resolucao_eventos_odds import carregar_cache_arquivo, mapear_fixtures  # noqa: E402
from scrapers.scraper_odds_jogadores import (  # noqa: E402
    URL_HUB_FIFA,
    _fixtures_de_confrontos,
    _navegar_clicar_player,
    _raspar_mercados_ptsoa,
    _url_evento,
    extrair_odds_rsc,
    extrair_sg_times,
)
from scrapers.odds_armazenamento import confrontos_na_janela, referencia_hoje  # noqa: E402
from utils.interceptacao_rede_oddsnotifier import (  # noqa: E402
    ArmazenamentoCapturaOdds,
    SCRIPT_EVASAO_AUTOMACAO,
    USER_AGENT_CHROME,
    aguardar_odds_capturadas,
)


def main() -> int:
    hoje = referencia_hoje()
    confrontos = confrontos_na_janela(hoje, 7)
    if not confrontos:
        print("Sem confrontos na janela.")
        return 1

    por_confronto, por_fixture, eventos_cache = carregar_cache_arquivo()
    eid_env = os.environ.get("ODDS_TEST_EVENT_ID", "").strip()

    if eid_env.isdigit():
        eid = int(eid_env)
        home, away = "?", "?"
        for ev in eventos_cache:
            if int(ev.get("id", 0)) == eid:
                home, away = ev.get("home", "?"), ev.get("away", "?")
                break
        print(f"Testando event_id={eid} ({home} vs {away}) [env]")
    else:
        alvo = None
        for c in confrontos:
            mand = (c.get("mandante") or "").upper()
            vis = (c.get("visitante") or "").upper()
            if mand in ("ENGLAND", "PORTUGAL", "BRAZIL", "ARGENTINA") or vis in (
                "ENGLAND", "PORTUGAL", "BRAZIL", "ARGENTINA",
            ):
                alvo = c
                break
        if alvo is None:
            alvo = confrontos[0]
        fixtures = _fixtures_de_confrontos([alvo])
        mapeados, faltando = mapear_fixtures(fixtures, por_confronto, por_fixture)
        if not mapeados:
            print("Evento nao mapeado:", faltando)
            return 1
        eid = int(mapeados[0]["id"])
        print(f"Testando event_id={eid} ({mapeados[0].get('home')} vs {mapeados[0].get('away')})")

    import logging

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("test_api_odds")

    headless = os.environ.get("ODDSNOTIFIER_HEADLESS", "true").lower() not in ("0", "false", "no")

    payload = None
    capturas = 0
    rsc_acumulado: list[str] = []
    odds_ptsoa: dict = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=USER_AGENT_CHROME, locale="pt-BR")
        ctx.add_init_script(SCRIPT_EVASAO_AUTOMACAO)
        page = ctx.new_page()

        armaz = ArmazenamentoCapturaOdds(log)
        armaz.vincular_pagina(page)

        page.goto(URL_HUB_FIFA, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        url = _url_evento(eid)
        page.goto(url, timeout=45000, wait_until="load")
        page.wait_for_timeout(8000)

        rsc_acumulado: list[str] = []

        def _capturar_rsc(resp) -> None:
            if "oddsnotifier" not in resp.url:
                return
            ct = (resp.headers.get("content-type") or "").lower()
            try:
                if "json" in ct:
                    corpo = resp.text()
                    if corpo:
                        rsc_acumulado.append(corpo)
                    return
            except Exception:
                pass
            if "x-component" in ct or "javascript" in ct or "text/html" in ct:
                try:
                    texto = resp.text()
                    if texto and ("bookmakers" in texto or "__next_f" in texto):
                        rsc_acumulado.append(texto)
                except Exception:
                    pass

        page.on("response", _capturar_rsc)

        _navegar_clicar_player(page)
        odds_ptsoa = _raspar_mercados_ptsoa(page, rsc_acumulado, 0, "teste")
        aguardar_odds_capturadas(page, armaz, eid, timeout_segundos=20)

        payload = armaz.obter_odds_evento(eid)
        capturas = armaz.quantidade_capturas()

        ctx.close()
        browser.close()

    if not payload:
        print("API vazia — tentando parse via respostas de rede capturadas (RSC/JSON)...")
        for chunk in rsc_acumulado:
            if "bookmakers" in chunk:
                payload = chunk
                break

    if not payload:
        print("FALHA: nenhum payload capturado.")
        print(f"  ptsoa via scraper: g={len(odds_ptsoa.get('g',{}))} a={len(odds_ptsoa.get('a',{}))} ga={len(odds_ptsoa.get('ga',{}))}")
        return 1

    print("capturas:", capturas)
    print("tipo payload:", type(payload).__name__)
    if isinstance(payload, dict):
        print("keys:", list(payload.keys())[:20])

    bruto = json.dumps(payload, ensure_ascii=False)
    odds = extrair_odds_rsc(bruto)
    sg = extrair_sg_times(bruto)
    g, a, ga = len(odds["g"]), len(odds["a"]), len(odds["ga"])
    print(f"parse: g={g} a={a} ga={ga} sg_home={bool(sg[0])} sg_away={bool(sg[1])}")

    if g + a + ga == 0 and not sg[0] and not sg[1]:
        print("FALHA: parser nao extraiu odds do payload API.")
        return 1

    print("OK: captura API + parse funcionando.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
