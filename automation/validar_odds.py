"""Valida cobertura mínima de odds_jogadores.json antes de commit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MIN_TOTAL = int(os.environ.get("ODDS_MIN_TOTAL", "500"))
MIN_TOTAL_PLAYOFFS = int(os.environ.get("ODDS_MIN_TOTAL_PLAYOFFS", "80"))
MIN_G = 200
MIN_A = 200
MIN_GA = 400
MIN_SG = 400
MIN_VIGENTES_PCT = float(os.environ.get("ODDS_MIN_VIGENTES_PCT", "1.0"))

POS_LINHA = frozenset({2, 3, 4, 5})
POS_SG = frozenset({1, 2, 3})

_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RAIZ / "src"))
CAMINHO = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"
CAMINHO_MERCADO = _RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_ESTADO = _RAIZ / "frontend" / "public" / "data" / "copa_estado.json"


def _modo_playoffs_flexivel() -> bool:
    if not CAMINHO_ESTADO.is_file():
        return False
    try:
        estado = json.loads(CAMINHO_ESTADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(
        estado.get("playoffs_ativos")
        or estado.get("transicao_playoffs")
        or estado.get("transicao_r16")
    )


def _transicao_playoffs() -> bool:
    if not CAMINHO_ESTADO.is_file():
        return False
    try:
        estado = json.loads(CAMINHO_ESTADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(estado.get("transicao_playoffs")) and not estado.get("playoffs_ativos")


def validar(caminho: Path | None = None) -> tuple[int, int, int, int, int]:
    path = caminho or CAMINHO
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    odds = data.get("odds", {})
    total = len(odds)
    g = sum(1 for v in odds.values() if v.get("g_pct"))
    a = sum(1 for v in odds.values() if v.get("a_pct"))
    ga = sum(
        1
        for v in odds.values()
        if enriquecer_odds_entrada(dict(v)).get("ga_pct")
    )
    sg = sum(1 for v in odds.values() if v.get("sg_pct"))
    return total, g, a, ga, sg


def _entrada_vigente(jog: dict, entrada: dict) -> bool:
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    entrada = enriquecer_odds_entrada(dict(entrada))
    from scrapers.odds_armazenamento import referencia_hoje

    data_odds = (entrada.get("data_confronto") or "").strip()
    if data_odds:
        if data_odds < referencia_hoje().isoformat():
            return False
        prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        prox_data = (jog.get("proximo_adversario_data") or "").strip()
        odds_adv = (entrada.get("adversario_sigla") or "").strip().upper()
        if prox and odds_adv:
            if odds_adv != prox:
                return False
            if prox_data and data_odds != prox_data:
                from scrapers.odds_armazenamento import parse_data_calendario

                d_odds = parse_data_calendario(data_odds)
                d_prox = parse_data_calendario(prox_data)
                if (
                    d_odds is None
                    or d_prox is None
                    or abs((d_odds - d_prox).days) > 2
                ):
                    return False
        pos = int(jog.get("posicao_id") or 0)
        if pos in POS_LINHA:
            return bool(entrada.get("ga_pct") or entrada.get("g_pct") or entrada.get("a_pct"))
        if pos in POS_SG:
            return bool(entrada.get("sg_pct"))
        return False

    prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
    if not prox:
        return bool(
            entrada.get("ga_pct")
            or entrada.get("g_pct")
            or entrada.get("a_pct")
            or entrada.get("sg_pct")
        )
    odds_adv = (entrada.get("adversario_sigla") or "").strip().upper()
    if odds_adv != prox:
        return False
    pos = int(jog.get("posicao_id") or 0)
    if pos in POS_LINHA:
        return bool(entrada.get("ga_pct") or entrada.get("g_pct") or entrada.get("a_pct"))
    if pos in POS_SG:
        return bool(entrada.get("sg_pct"))
    return False


def validar_odds_vigentes(
    caminho_odds: Path | None = None,
    caminho_mercado: Path | None = None,
) -> tuple[int, int, int]:
    """
    Jogadores com ADV no mercado (qualquer status) precisam de odds alinhadas
    ao próximo adversário — GA/G/A para linha, SG para GOL/LAT/ZAG.
    """
    path_odds = caminho_odds or CAMINHO
    path_mercado = caminho_mercado or CAMINHO_MERCADO
    if not path_odds.is_file() or not path_mercado.is_file():
        return 0, 0, 0

    odds = json.loads(path_odds.read_text(encoding="utf-8")).get("odds", {})
    mercado = json.loads(path_mercado.read_text(encoding="utf-8"))

    alvo = 0
    vigentes = 0
    sem_odd = 0

    for jog in mercado:
        if jog.get("ativo_playoffs") is False:
            continue
        prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        if not prox:
            continue
        pos = int(jog.get("posicao_id") or 0)
        if pos not in POS_LINHA and pos not in POS_SG:
            continue
        alvo += 1
        entrada = odds.get(str(jog.get("atleta_id")))
        if not isinstance(entrada, dict):
            sem_odd += 1
            continue
        if _entrada_vigente(jog, entrada):
            vigentes += 1
        else:
            sem_odd += 1

    return alvo, vigentes, sem_odd


def main() -> None:
    total, g, a, ga, sg = validar()
    alvo, vigentes, sem_odd = validar_odds_vigentes()
    pct_vig = (vigentes / alvo * 100) if alvo else 100.0
    transicao = _transicao_playoffs()
    playoffs_flex = _modo_playoffs_flexivel()
    min_total = MIN_TOTAL_PLAYOFFS if playoffs_flex else MIN_TOTAL

    print(f"total={total} g={g} a={a} ga={ga} sg={sg}")
    print(f"vigentes={vigentes}/{alvo} ({pct_vig:.0f}%) sem_odd={sem_odd}")
    if playoffs_flex:
        print(f"modo=playoffs_flexivel (min_total={min_total})")

    if (
        total < min_total
        or (not playoffs_flex and g < MIN_G)
        or (not playoffs_flex and a < MIN_A)
        or (not playoffs_flex and ga < MIN_GA)
        or (not playoffs_flex and sg < MIN_SG)
    ):
        if playoffs_flex and total >= min_total and vigentes > 100:
            print(
                f"AVISO playoffs: cobertura bruta ok ({total} entradas, "
                f"{vigentes} vigentes) — commit permitido."
            )
        else:
            print("Cobertura insuficiente — abortando commit.")
            sys.exit(1)

    min_vig_pct = 0.85 if playoffs_flex else MIN_VIGENTES_PCT
    if alvo > 0 and vigentes / alvo < min_vig_pct:
        if playoffs_flex and vigentes > 100:
            print(
                f"AVISO playoffs: vigentes {vigentes}/{alvo} "
                f"({pct_vig:.0f}%) — commit permitido."
            )
        elif transicao and vigentes > 0:
            print(
                f"AVISO transicao: vigentes {vigentes}/{alvo} "
                f"({pct_vig:.0f}%) — commit permitido."
            )
        else:
            print(
                f"Odds vigentes abaixo de {min_vig_pct:.0%} "
                f"para jogadores com ADV ({vigentes}/{alvo}). "
                "Abortando commit."
            )
            sys.exit(1)

    if sem_odd > 0:
        if playoffs_flex and vigentes > 100:
            print(
                f"AVISO playoffs: {sem_odd} jogador(es) ainda sem odds vigentes."
            )
        elif transicao and vigentes > 0:
            print(
                f"AVISO transicao: {sem_odd} jogador(es) ainda sem odds vigentes."
            )
        else:
            print(f"{sem_odd} jogador(es) com ADV sem odds no arquivo — abortando commit.")
            sys.exit(1)


if __name__ == "__main__":
    main()
