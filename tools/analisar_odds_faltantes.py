"""Lista jogadores ativos sem odds vigentes e confrontos a re-raspar."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.odds_armazenamento import parse_data_calendario, referencia_hoje  # noqa: E402

POS_ALVO = frozenset({1, 2, 3, 4, 5, 6})
POS_LINHA = frozenset({2, 3, 4, 5})
POS_SG = frozenset({1, 2, 3})


def vigente(j: dict, e: dict | None) -> bool:
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


def main() -> int:
    mercado = json.loads((RAIZ / "frontend/public/data/jogadores_mercado.json").read_text(encoding="utf-8"))
    odds_data = json.loads((RAIZ / "frontend/public/data/odds_jogadores.json").read_text(encoding="utf-8"))
    odds = odds_data.get("odds", {})
    arm = json.loads((RAIZ / "frontend/public/data/odds_eventos_armazenados.json").read_text(encoding="utf-8"))
    evs = arm.get("eventos", {})

    alvo = [
        j
        for j in mercado
        if j.get("ativo_playoffs") is not False
        and int(j.get("posicao_id") or 0) in POS_ALVO
        and j.get("proximo_adversario_sigla")
    ]
    sem = [j for j in alvo if not vigente(j, odds.get(str(j.get("atleta_id"))))]

    print(f"odds atualizado: {odds_data.get('atualizado_em')}")
    print(f"alvo={len(alvo)} vigentes={len(alvo)-len(sem)} faltando={len(sem)}")

    por_par = Counter((j["sigla"], j.get("proximo_adversario_sigla")) for j in sem)
    print("\nFaltando por par (sigla vs ADV):")
    for (sig, adv), n in por_par.most_common():
        print(f"  {sig} vs {adv}: {n}")

    # eventos KO no armazenamento
    print("\nEventos KO no armazenamento:")
    eventos_alvo: dict[str, dict] = {}
    for eid, ev in sorted(evs.items(), key=lambda x: (x[1].get("data", ""), x[0])):
        d = ev.get("data", "")
        if d < referencia_hoje().isoformat():
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
        in_arm = sum(1 for j in need if str(j["atleta_id"]) in odds_ev)
        missing = len(need) - in_arm
        print(
            f"  {d} {sm} vs {sv} id={eid} "
            f"odds_arm={len(odds_ev)} need={len(need)} in_arm={in_arm} missing={missing}"
        )
        if need:
            eventos_alvo[eid] = ev

    # event ids to re-scrape: those with missing players in arm OR zero/low odds count
    rescrape: list[tuple[str, int, int]] = []
    for eid, ev in eventos_alvo.items():
        sm = (ev.get("sigla_mandante") or "").upper()
        sv = (ev.get("sigla_visitante") or "").upper()
        odds_ev = ev.get("odds") or {}
        need = [
            j
            for j in sem
            if j["sigla"] in (sm, sv)
            and j.get("proximo_adversario_sigla") in (sm, sv)
        ]
        in_arm = sum(1 for j in need if str(j["atleta_id"]) in odds_ev)
        if in_arm < len(need) or len(odds_ev) < 80:
            rescrape.append((eid, len(need) - in_arm, len(odds_ev)))

    print("\nEventos para re-raspar (eid, missing, odds_arm):")
    for eid, missing, n_arm in rescrape:
        print(f"  {eid} missing={missing} odds_arm={n_arm}")

    out = RAIZ / "tools" / "eventos_rescrape.json"
    out.write_text(json.dumps([int(e) for e, _, _ in rescrape], indent=2), encoding="utf-8")
    print(f"\nSalvo: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
