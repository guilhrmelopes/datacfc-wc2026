"""Rating das seleções na Copa: scouts, Elo de mata-mata e híbrido.

Camadas:
  - rating_scouts_100: percentis das métricas coletivas (normalizadas por jogo)
  - rating_ko_100: Elo margem-aware só com jogos de eliminatórias (seed = Elo mundial)
  - rating_copa_100: fusão Elo mundial + scouts + Elo KO (principal no HUB)
"""

from __future__ import annotations

import math
from typing import Any

# Campos per-match (já vêm como média no FotMob)
_METRICAS_MAIOR_MELHOR = (
    "goals_team_match",
    "possession_percentage_team",
    "expected_goals_team",
    "clean_sheet_team",
    "ontarget_scoring_att_team",
    "big_chance_team",
    "touches_in_opp_box_team",
    "total_tackle_team",
    "poss_won_att_3rd_team",
    "saves_team",
    "fk_foul_lost_team",
)

_METRICAS_MENOR_MELHOR = (
    "goals_conceded_team_match",
    "expected_goals_conceded_team",
    "total_yel_card_team",
    "total_red_card_team",
)

# Totais acumulados no season stats — converter para /jogo no rating
_METRICAS_TOTAIS = frozenset(
    {
        "expected_goals_team",
        "expected_goals_conceded_team",
        "clean_sheet_team",
        "big_chance_team",
        "touches_in_opp_box_team",
        "total_yel_card_team",
        "total_red_card_team",
    }
)

K_KO_BASE = 48.0
ELO_KO_INICIAL = 1500.0


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _percentil(valor: float, amostra: list[float]) -> float:
    if not amostra:
        return 50.0
    abaixo = sum(1 for x in amostra if x < valor)
    iguais = sum(1 for x in amostra if x == valor)
    pct = ((abaixo + iguais * 0.5) / len(amostra)) * 100.0
    return round(max(1.0, min(100.0, pct)), 1)


def _metrica_por_jogo(campo: str, valor: float, jogos: float) -> float:
    if campo in _METRICAS_TOTAIS and jogos > 0:
        return valor / jogos
    return valor


def valor_metrica_rating(selecao: dict, campo: str) -> float | None:
    metricas = selecao.get("metricas_coletivas") or {}
    bruto = _f(metricas.get(campo))
    if bruto is None:
        return None
    jogos = _f(metricas.get("J")) or 0.0
    return _metrica_por_jogo(campo, bruto, jogos)


def calcular_rating_scouts(selecao: dict, pool: list[dict]) -> float | None:
    """Percentil médio das métricas (0–100) entre seleções que estrearam."""
    jogos = _f((selecao.get("metricas_coletivas") or {}).get("J")) or 0.0
    if jogos <= 0:
        return None

    estrearam = [
        s
        for s in pool
        if (_f((s.get("metricas_coletivas") or {}).get("J")) or 0) > 0
    ]
    if not estrearam:
        return None

    percentis: list[float] = []
    for campo in _METRICAS_MAIOR_MELHOR:
        valor = valor_metrica_rating(selecao, campo)
        if valor is None:
            continue
        amostra = [
            v
            for s in estrearam
            if (v := valor_metrica_rating(s, campo)) is not None
        ]
        if amostra:
            percentis.append(_percentil(valor, amostra))

    for campo in _METRICAS_MENOR_MELHOR:
        valor = valor_metrica_rating(selecao, campo)
        if valor is None:
            continue
        amostra = [
            v
            for s in estrearam
            if (v := valor_metrica_rating(s, campo)) is not None
        ]
        if amostra:
            percentis.append(round(100.0 - _percentil(valor, amostra), 1))

    if not percentis:
        return None
    return round(sum(percentis) / len(percentis), 1)


def _iter_confrontos_ko(mata_mata: dict):
    for fase in mata_mata.get("fases") or []:
        stage = str(fase.get("stage") or "")
        for confronto in fase.get("confrontos") or []:
            yield stage, confronto
    for stage, chave in (("final", "final"), ("bronze", "disputa_bronze")):
        bloco = mata_mata.get(chave)
        if isinstance(bloco, dict):
            yield stage, bloco


def jogos_ko_por_sigla(mata_mata: dict) -> dict[str, int]:
    """Jogos de mata-mata finalizados por sigla Cartola."""
    contagem: dict[str, int] = {}
    for _stage, confronto in _iter_confrontos_ko(mata_mata):
        if not confronto.get("finalizada"):
            continue
        for chave in ("mandante", "visitante"):
            bloco = confronto.get(chave) or {}
            if bloco.get("tbd"):
                continue
            sigla = (bloco.get("sigla") or "").strip().upper()
            if sigla and sigla != "TBD":
                contagem[sigla] = contagem.get(sigla, 0) + 1
    return contagem


def _ordem_stage(stage: str) -> int:
    return {"1/16": 1, "1/8": 2, "1/4": 3, "1/2": 4, "bronze": 5, "final": 6}.get(stage, 9)


def _resultado_ko(confronto: dict) -> tuple[str, str, float, float, float] | None:
    """
    Retorna (sigla_home, sigla_away, score_home, gd_home, k_mult).
    score: 1 vitória / 0 derrota / 0.5 empate (não esperado em KO).
    """
    mandante = confronto.get("mandante") or {}
    visitante = confronto.get("visitante") or {}
    if mandante.get("tbd") or visitante.get("tbd"):
        return None
    sh = (mandante.get("sigla") or "").strip().upper()
    sa = (visitante.get("sigla") or "").strip().upper()
    if not sh or not sa or sh == "TBD" or sa == "TBD":
        return None

    pm = confronto.get("placar_mandante")
    pv = confronto.get("placar_visitante")
    try:
        pm_i = int(pm) if pm is not None else None
        pv_i = int(pv) if pv is not None else None
    except (TypeError, ValueError):
        pm_i, pv_i = None, None

    venceu_m = bool(confronto.get("mandante_venceu"))
    venceu_v = bool(confronto.get("visitante_venceu"))

    if venceu_m and not venceu_v:
        score_h, gd = 1.0, float((pm_i or 0) - (pv_i or 0))
        # pênaltis / 0-0: margem simbólica
        if pm_i is not None and pv_i is not None and pm_i == pv_i:
            gd = 0.5
        return sh, sa, score_h, gd, 1.0
    if venceu_v and not venceu_m:
        score_h, gd = 0.0, float((pm_i or 0) - (pv_i or 0))
        if pm_i is not None and pv_i is not None and pm_i == pv_i:
            gd = -0.5
        return sh, sa, score_h, gd, 1.0

    if pm_i is not None and pv_i is not None and pm_i != pv_i:
        if pm_i > pv_i:
            return sh, sa, 1.0, float(pm_i - pv_i), 1.0
        return sh, sa, 0.0, float(pm_i - pv_i), 1.0

    return None


def _esperado(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def _fator_margem(gd: float) -> float:
    """Lampl-style: amplifica update pela margem (pênaltis ≈ 0.5)."""
    return math.log(abs(gd) + 1.0) / math.log(2.0)  # 1 gol → 1.0; 3 → ~2.0


def calcular_elo_ko(
    mata_mata: dict,
    elo_seed_por_sigla: dict[str, float],
) -> dict[str, float]:
    """
    Elo só com resultados KO, semeado no Elo mundial.
    Retorna mapa sigla → Elo bruto (só quem jogou KO).
    """
    ratings: dict[str, float] = {}
    jogos = sorted(
        (
            (stage, conf)
            for stage, conf in _iter_confrontos_ko(mata_mata)
            if conf.get("finalizada")
        ),
        key=lambda par: (
            _ordem_stage(par[0]),
            str(par[1].get("data") or ""),
            str(par[1].get("hora") or ""),
            str(par[1].get("match_id") or ""),
        ),
    )

    for stage, confronto in jogos:
        parsed = _resultado_ko(confronto)
        if not parsed:
            continue
        sh, sa, score_h, gd, _ = parsed
        ra = ratings.get(sh, elo_seed_por_sigla.get(sh, ELO_KO_INICIAL))
        rb = ratings.get(sa, elo_seed_por_sigla.get(sa, ELO_KO_INICIAL))
        ea = _esperado(ra, rb)
        eb = 1.0 - ea
        k = K_KO_BASE * (1.0 + 0.15 * max(0, _ordem_stage(stage) - 1))
        k *= max(0.85, _fator_margem(gd))
        ratings[sh] = ra + k * (score_h - ea)
        ratings[sa] = rb + k * ((1.0 - score_h) - eb)

    return ratings


def normalizar_0_100(valores: dict[str, float]) -> dict[str, float]:
    if not valores:
        return {}
    lo = min(valores.values())
    hi = max(valores.values())
    if hi <= lo:
        return {k: 50.0 for k in valores}
    return {
        k: round(max(0.0, min(100.0, (v - lo) / (hi - lo) * 100.0)), 1)
        for k, v in valores.items()
    }


def rating_hibrido(
    *,
    elo_100: float | None,
    scouts_100: float | None,
    ko_100: float | None,
    jogos_ko: int,
) -> float | None:
    """Fundê as camadas com pesos que crescem no mata-mata."""
    partes: list[tuple[float, float]] = []
    if elo_100 is not None:
        w_elo = 0.55 if jogos_ko <= 0 else (0.40 if jogos_ko == 1 else 0.30)
        partes.append((w_elo, elo_100))
    if scouts_100 is not None:
        w_s = 0.45 if jogos_ko <= 0 else (0.35 if jogos_ko == 1 else 0.35)
        partes.append((w_s, scouts_100))
    if ko_100 is not None and jogos_ko > 0:
        w_k = 0.25 if jogos_ko == 1 else 0.35
        partes.append((w_k, ko_100))

    if not partes:
        return None
    peso = sum(w for w, _ in partes)
    if peso <= 0:
        return None
    return round(sum(w * v for w, v in partes) / peso, 1)


def aplicar_ratings_selecoes(
    selecoes: list[dict],
    mata_mata: dict,
) -> dict[str, Any]:
    """Mutações in-place em selecoes.json — retorna resumo."""
    jogos_ko = jogos_ko_por_sigla(mata_mata)
    seeds = {
        s["sigla"]: float(s["elo_rating"])
        for s in selecoes
        if s.get("sigla") and s.get("elo_rating") is not None
    }
    elo_ko_bruto = calcular_elo_ko(mata_mata, seeds)
    elo_ko_100 = normalizar_0_100(elo_ko_bruto)

    n_scouts = n_hibrido = 0
    for s in selecoes:
        sigla = s.get("sigla")
        if not sigla:
            continue
        scouts = calcular_rating_scouts(s, selecoes)
        j_ko = int(jogos_ko.get(sigla, 0))
        s["jogos_mata_mata"] = j_ko
        s["rating_scouts_100"] = scouts
        s["rating_ko_100"] = elo_ko_100.get(sigla) if j_ko > 0 else None
        s["elo_ko"] = round(elo_ko_bruto[sigla], 1) if sigla in elo_ko_bruto else None
        hibrido = rating_hibrido(
            elo_100=_f(s.get("rating_elo_100")),
            scouts_100=scouts,
            ko_100=s.get("rating_ko_100"),
            jogos_ko=j_ko,
        )
        s["rating_copa_100"] = hibrido
        if scouts is not None:
            n_scouts += 1
        if hibrido is not None:
            n_hibrido += 1

    return {
        "com_rating_scouts": n_scouts,
        "com_rating_copa": n_hibrido,
        "com_elo_ko": len(elo_ko_bruto),
        "jogos_ko_siglas": len(jogos_ko),
    }
