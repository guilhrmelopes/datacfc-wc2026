"""Backfill moneyline (ML) nos eventos já armazenados (sem re-scrape de props)."""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from scrapers.scraper_odds_jogadores import extrair_ml_times, _rsc_de_pagina  # noqa: E402
from scrapers.odds_armazenamento import (  # noqa: E402
    CAMINHO_ARMAZENAMENTO,
    carregar_armazenamento,
    salvar_armazenamento,
)
from utils.interceptacao_rede_oddsnotifier import criar_navegador_chromium  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill_ml")


def _clicar(page, rotulo: str) -> bool:
    for seletor in [
        f"button:has-text('{rotulo}')",
        f"a:has-text('{rotulo}')",
        f"[role='tab']:has-text('{rotulo}')",
    ]:
        try:
            el = page.locator(seletor).first
            if el.count() and el.is_visible(timeout=2000):
                el.click(timeout=3000)
                page.wait_for_timeout(2000)
                return True
        except Exception:
            continue
    return False


def main() -> int:
    armaz = carregar_armazenamento()
    eventos = armaz.get("eventos") or {}
    pendentes = [
        (chave, ev)
        for chave, ev in eventos.items()
        if isinstance(ev, dict)
        and ev.get("p_vit_home") is None
        and ev.get("event_id")
    ]
    if not pendentes:
        log.info("Nenhum evento sem ML — nada a fazer.")
        return 0

    log.info("Backfill ML: %d eventos pendentes.", len(pendentes))
    atualizados = 0

    with sync_playwright() as p:
        browser, _ctx, page = criar_navegador_chromium(p)
        try:
            for idx, (chave, ev) in enumerate(pendentes, start=1):
                eid = int(ev["event_id"])
                home = ev.get("home") or ev.get("mandante") or "?"
                away = ev.get("away") or ev.get("visitante") or "?"
                url = f"https://hub.oddsnotifier.io/football/international-fifa-world-cup/{eid}"
                log.info("[%d/%d] %s vs %s", idx, len(pendentes), home, away)
                try:
                    page.goto(url, timeout=60000, wait_until="load")
                    page.wait_for_timeout(7000)
                    _clicar(page, "Main")
                    _clicar(page, "ML")
                    page.wait_for_timeout(4000)
                    rsc = _rsc_de_pagina(page)
                    ml = extrair_ml_times(rsc, str(home), str(away))
                except Exception as erro:
                    log.warning("  falha: %s", erro)
                    continue
                if not ml:
                    log.warning("  ML não encontrado.")
                    continue
                ev.update(ml)
                eventos[chave] = ev
                atualizados += 1
                log.info(
                    "  OK P(home)=%.1f%% P(away)=%.1f%% @ %s",
                    ml["p_vit_home"],
                    ml["p_vit_away"],
                    ml.get("casa_ml"),
                )
                if idx < len(pendentes):
                    time.sleep(3)
        finally:
            browser.close()

    if atualizados:
        armaz["atualizado_em"] = datetime.now(tz=timezone.utc).isoformat()
        salvar_armazenamento(armaz)
        publico = RAIZ / "frontend" / "public" / "data" / "odds_eventos_armazenados.json"
        publico.parent.mkdir(parents=True, exist_ok=True)
        with publico.open("w", encoding="utf-8") as f:
            json.dump(armaz, f, ensure_ascii=False, separators=(",", ":"))
        log.info("Salvo: %d eventos com ML (%s).", atualizados, publico)

    return 0 if atualizados else 1


if __name__ == "__main__":
    raise SystemExit(main())
