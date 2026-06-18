"""Mapeamento de nomes de seleção (OddsNotifier / calendário → chave Cartola)."""

from __future__ import annotations

import unicodedata

# OddsNotifier / FotMob → seleção Cartola (upper)
ALIAS_SELECOES: dict[str, str] = {
    "KOREA REPUBLIC": "SOUTH KOREA",
    "SOUTH KOREA": "SOUTH KOREA",
    "CZECH REPUBLIC": "CZECHIA",
    "CZECHIA": "CZECHIA",
    "BOSNIA & HERZ.": "BOSNIA AND HERZEGOVINA",
    "BOSNIA AND HERZEGOVINA": "BOSNIA AND HERZEGOVINA",
    "USA": "UNITED STATES",
    "UNITED STATES": "UNITED STATES",
    "TURKIYE": "TURKIYE",
    "TÜRKIYE": "TURKIYE",
    "CAPE VERDE ISLANDS": "CAPE VERDE",
    "CAPE VERDE": "CAPE VERDE",
    "CURACAO": "CURACAO",
    "CURAÇAO": "CURACAO",
    "COTE D'IVOIRE": "IVORY COAST",
    "CÔTE D'IVOIRE": "IVORY COAST",
    "CONGO DR": "DR CONGO",
    "IR IRAN": "IRAN",
    "IRAN": "IRAN",
    "IRAQ": "IRAQ",
}


def normalizar_selecao(nome: str) -> str:
    forma = unicodedata.normalize("NFKD", nome or "")
    ascii_n = "".join(c for c in forma if not unicodedata.combining(c)).upper().strip()
    return ALIAS_SELECOES.get(ascii_n, ascii_n)


def chave_confronto(home: str, away: str) -> tuple[str, str]:
    """Par de seleções normalizado, independente de mandante/visitante."""
    a = normalizar_selecao(home)
    b = normalizar_selecao(away)
    return tuple(sorted((a, b)))
