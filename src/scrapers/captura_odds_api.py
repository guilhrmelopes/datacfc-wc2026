"""Extrai odds a partir de payloads JSON da API OddsNotifier."""

from __future__ import annotations

import json
from typing import Any


def payload_para_texto(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False)
    return ""


def extrair_odds_de_payload(payload: Any, extrair_fn) -> dict[str, dict[str, tuple[float, str]]]:
    """
    Reutiliza extrair_odds_rsc quando o payload contém bookmakers.
    extrair_fn: scraper.extrair_odds_rsc
    """
    texto = payload_para_texto(payload)
    if not texto or "bookmakers" not in texto:
        return {"g": {}, "a": {}, "ga": {}}
    return extrair_fn(texto)


def extrair_sg_de_payload(payload: Any, extrair_sg_fn) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    texto = payload_para_texto(payload)
    if not texto or "bookmakers" not in texto:
        return None, None
    return extrair_sg_fn(texto)


def extrair_ml_de_payload(
    payload: Any,
    extrair_ml_fn,
    home_name: str = "",
    away_name: str = "",
) -> dict | None:
    texto = payload_para_texto(payload)
    if not texto or "bookmakers" not in texto:
        return None
    return extrair_ml_fn(texto, home_name=home_name, away_name=away_name)
