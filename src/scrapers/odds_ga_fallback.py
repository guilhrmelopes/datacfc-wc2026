"""GA% derivado de G% + A% (mesma fórmula do frontend)."""

from __future__ import annotations

from typing import Any


def calcular_ga_pct_de_g_a(g_pct: float, a_pct: float) -> float:
    """P(marcar ou assistir) assumindo independência entre G e A (escala 0–100)."""
    pg = g_pct / 100.0
    pa = a_pct / 100.0
    pga = pg + pa - pg * pa
    return round(pga * 100, 2)


def enriquecer_odds_entrada(entrada: dict[str, Any]) -> dict[str, Any]:
    """
    Preenche ga_pct quando a casa traz G% e A% mas não o mercado combinado.
    Não sobrescreve ga_pct já presente nem define odds_ga (indica derivação).
    """
    if entrada.get("ga_pct") is not None:
        return entrada
    g = entrada.get("g_pct")
    a = entrada.get("a_pct")
    if g is None or a is None:
        return entrada
    try:
        g_f = float(g)
        a_f = float(a)
    except (TypeError, ValueError):
        return entrada
    entrada["ga_pct"] = calcular_ga_pct_de_g_a(g_f, a_f)
    return entrada


def enriquecer_mapa_odds(odds: dict[str, dict]) -> dict[str, dict]:
    for entrada in odds.values():
        if isinstance(entrada, dict):
            enriquecer_odds_entrada(entrada)
    return odds
