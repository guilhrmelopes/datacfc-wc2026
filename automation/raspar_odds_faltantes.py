"""
Identifica jogadores sem odds vigentes, recompila do armazenamento e
re-raspa somente eventos KO ainda incompletos.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.odds_armazenamento import (  # noqa: E402
    carregar_armazenamento,
    compilar_e_salvar,
    referencia_hoje,
)
from scrapers.scraper_odds_jogadores import carregar_todos_jogadores  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("odds_faltantes")

CAMINHO_MERCADO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_ODDS = RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"

POS_ALVO = frozenset({1, 2, 3, 4, 5, 6})
POS_LINHA = frozenset({2, 3, 4, 5})
POS_SG = frozenset({1, 2, 3})


def _vigente(j: dict, e: dict | None) -> bool:
    if not e:
        return False
    prox = (j.get("proximo_adversario_sigla") or "").strip().upper()
    prox_data = (j.get("proximo_adversario_data") or "").strip()
    data_odds = (e.get("data_confronto") or "").strip()
    adv = (e.get("adversario_sigla") or "").strip().upper()
    if not prox or not data_odds:
        return False
    if data_odds < referencia_hoje().isoformat():
        return False
    if adv != prox:
        return False
    if prox_data and data_odds != prox_data:
        from scrapers.odds_armazenamento import parse_data_calendario

        d1 = parse_data_calendario(data_odds)
        d2 = parse_data_calendario(prox_data)
        if d1 is None or d2 is None or abs((d1 - d2).days) > 2:
            return False
    pos = int(j.get("posicao_id") or 0)
    if pos in POS_LINHA:
        return bool(e.get("ga_pct") or e.get("g_pct") or e.get("a_pct"))
    if pos in POS_SG:
        return bool(e.get("sg_pct"))
    return False


def listar_faltantes() -> tuple[list[dict], dict[str, dict]]:
    mercado = json.loads(CAMINHO_MERCADO.read_text(encoding="utf-8"))
    odds = json.loads(CAMINHO_ODDS.read_text(encoding="utf-8")).get("odds", {})
    alvo = [
        j
        for j in mercado
        if j.get("ativo_playoffs") is not False
        and int(j.get("posicao_id") or 0) in POS_ALVO
        and j.get("proximo_adversario_sigla")
    ]
    sem = [j for j in alvo if not _vigente(j, odds.get(str(j.get("atleta_id"))))]
    return sem, odds


def eventos_incompletos(sem: list[dict]) -> list[int]:
    arm = carregar_armazenamento()
    evs = arm.get("eventos", {})
    ids: list[int] = []

    for eid, ev in evs.items():
        if (ev.get("data") or "") < referencia_hoje().isoformat():
            continue
        sm = (ev.get("sigla_mandante") or "").upper()
        sv = (ev.get("sigla_visitante") or "").upper()
        odds_ev = ev.get("odds") or {}
        need = [
            j
            for j in sem
            if j["sigla"] in (sm, sv)
            and j.get("proximo_adversario_sigla") in (sm, sv)
        ]
        if not need:
            continue
        in_arm = sum(1 for j in need if str(j["atleta_id"]) in odds_ev)
        if in_arm < len(need) or len(odds_ev) < 80:
            ids.append(int(eid))
    return sorted(set(ids))


def main() -> int:
    sem_antes, _ = listar_faltantes()
    log.info("Antes: %d jogadores sem odds vigentes.", len(sem_antes))
    if sem_antes:
        por_par = Counter((j["sigla"], j.get("proximo_adversario_sigla")) for j in sem_antes)
        for (sig, adv), n in por_par.most_common(8):
            log.info("  %s vs %s: %d", sig, adv, n)

    log.info("Recompilando odds_jogadores.json do armazenamento...")
    compilar_e_salvar()

    sem_depois, _ = listar_faltantes()
    log.info("Após compilação: %d jogadores sem odds vigentes.", len(sem_depois))

    eventos = eventos_incompletos(sem_depois)
    if not eventos:
        if sem_depois:
            log.warning(
                "%d jogadores ainda sem odds — nenhum evento incompleto no armazenamento.",
                len(sem_depois),
            )
        else:
            log.info("Todos os jogadores alvo com odds vigentes.")
        return 0 if not sem_depois else 1

    log.info("Re-raspando %d evento(s): %s", len(eventos), eventos)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(RAIZ / "src")

    for eid in eventos:
        log.info("--- Evento %d ---", eid)
        r = subprocess.run(
            [sys.executable, str(RAIZ / "automation" / "raspar_evento_odds.py"), str(eid)],
            cwd=RAIZ,
            env=env,
            check=False,
        )
        if r.returncode != 0:
            log.error("Falha ao raspar evento %d (exit %d).", eid, r.returncode)

    sem_final, _ = listar_faltantes()
    log.info("Final: %d jogadores sem odds vigentes.", len(sem_final))
    return 0 if len(sem_final) < len(sem_antes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
