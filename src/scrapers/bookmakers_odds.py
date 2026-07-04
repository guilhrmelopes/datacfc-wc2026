"""Casas de aposta autorizadas no pipeline de odds."""

from __future__ import annotations

import unicodedata

BOOKMAKERS_PERMITIDOS: tuple[str, ...] = (
    "pinnacle",
    "betfair",
    "betfair exchange",
    "1xbet",
    "betano",
    "kalshi",
    "bet365",
    "unibet",
    "kambi",
    "betuk",
    "betclic",
    "leovegas",
    "stake",
)

BOOKMAKERS_ORDEM: tuple[str, ...] = (
    "pinnacle",
    "betfair exchange",
    "betfair",
    "1xbet",
    "bet365",
    "unibet",
    "kambi",
    "betuk",
    "betclic",
    "leovegas",
    "betano",
    "stake",
    "kalshi",
)


def _norm(texto: str) -> str:
    forma = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in forma if not unicodedata.combining(c)).lower().strip()


def bookmaker_permitido(nome: str) -> bool:
    n = _norm(nome)
    return any(marca in n for marca in BOOKMAKERS_PERMITIDOS)


def casa_prioridade(nome: str) -> int:
    if not bookmaker_permitido(nome):
        return 999
    n = _norm(nome)
    for i, marca in enumerate(BOOKMAKERS_ORDEM):
        if marca in n:
            return i
    return len(BOOKMAKERS_ORDEM)
