"""Mapeamento FotMob ↔ nomes/siglas usados nos JSONs do frontend."""

from __future__ import annotations

# Nome exibido no FotMob → chave `selecao` em selecoes.json
FOTMOB_PARA_SELECAO: dict[str, str] = {
    "Mexico": "MEXICO",
    "South Africa": "SOUTH AFRICA",
    "South Korea": "SOUTH KOREA",
    "Czechia": "CZECHIA",
    "Canada": "CANADA",
    "Bosnia and Herzegovina": "BOSNIA AND HERZEGOVINA",
    "Qatar": "QATAR",
    "Switzerland": "SWITZERLAND",
    "Brazil": "BRAZIL",
    "Morocco": "MOROCCO",
    "Haiti": "HAITI",
    "Scotland": "SCOTLAND",
    "USA": "UNITED STATES",
    "United States": "UNITED STATES",
    "Paraguay": "PARAGUAY",
    "Australia": "AUSTRALIA",
    "Turkiye": "TURKIYE",
    "Germany": "GERMANY",
    "Curacao": "CURACAO",
    "Ivory Coast": "IVORY COAST",
    "Ecuador": "ECUADOR",
    "Netherlands": "NETHERLANDS",
    "Japan": "JAPAN",
    "Sweden": "SWEDEN",
    "Tunisia": "TUNISIA",
    "Belgium": "BELGIUM",
    "Egypt": "EGYPT",
    "Iran": "IRAN",
    "New Zealand": "NEW ZEALAND",
    "Spain": "SPAIN",
    "Cape Verde": "CAPE VERDE",
    "Saudi Arabia": "SAUDI ARABIA",
    "Uruguay": "URUGUAY",
    "France": "FRANCE",
    "Senegal": "SENEGAL",
    "Iraq": "IRAQ",
    "Norway": "NORWAY",
    "Argentina": "ARGENTINA",
    "Algeria": "ALGERIA",
    "Austria": "AUSTRIA",
    "Jordan": "JORDAN",
    "Portugal": "PORTUGAL",
    "DR Congo": "DR CONGO",
    "Uzbekistan": "UZBEKISTAN",
    "Colombia": "COLOMBIA",
    "England": "ENGLAND",
    "Croatia": "CROATIA",
    "Ghana": "GHANA",
    "Panama": "PANAMA",
}

# Sigla → nome curto FotMob (stats API)
SIGLA_PARA_FOTMOB_STATS: dict[str, str] = {
    "MEX": "Mexico",
    "AFS": "South Africa",
    "COR": "South Korea",
    "TCH": "Czechia",
    "CAN": "Canada",
    "BOS": "Bosnia and Herzegovina",
    "CAT": "Qatar",
    "SUI": "Switzerland",
    "BRA": "Brazil",
    "MAR": "Morocco",
    "HAI": "Haiti",
    "ESC": "Scotland",
    "EUA": "USA",
    "PAR": "Paraguay",
    "AUS": "Australia",
    "TUR": "Turkiye",
    "ALE": "Germany",
    "CUR": "Curacao",
    "CMF": "Ivory Coast",
    "CDM": "Ivory Coast",  # abreviação Cartola (Costa do Marfim)
    "EQU": "Ecuador",
    "HOL": "Netherlands",
    "JAP": "Japan",
    "SUE": "Sweden",
    "TUN": "Tunisia",
    "BEL": "Belgium",
    "EGI": "Egypt",
    "IRA": "Iran",
    "NZL": "New Zealand",
    "NZE": "New Zealand",
    "ESP": "Spain",
    "CAB": "Cape Verde",
    "ARS": "Saudi Arabia",
    "URU": "Uruguay",
    "FRA": "France",
    "SEN": "Senegal",
    "IRQ": "Iraq",
    "NOR": "Norway",
    "ARG": "Argentina",
    "ALG": "Algeria",
    "AGL": "Algeria",
    "AUT": "Austria",
    "JOR": "Jordan",
    "POR": "Portugal",
    "RDC": "DR Congo",
    "UZB": "Uzbekistan",
    "COL": "Colombia",
    "ING": "England",
    "CRO": "Croatia",
    "GAN": "Ghana",
    "PAN": "Panama",
}


def fotmob_para_selecao(nome_fotmob: str) -> str | None:
    return FOTMOB_PARA_SELECAO.get(nome_fotmob)


def cartola_abrev_para_selecao(abrev: str) -> str | None:
    """Abreviação Cartola (ex: SUE, TUN) → chave `selecao` do dashboard."""
    nome_fotmob = SIGLA_PARA_FOTMOB_STATS.get((abrev or "").strip().upper())
    if not nome_fotmob:
        return None
    return fotmob_para_selecao(nome_fotmob)


def url_escudo_cartola(sigla: str) -> str:
    return (
        "https://s3.glbimg.com/v1/AUTH_925c4b2308d342c6ba7864ea930fdada"
        f"/clubes_2026/escudos/{sigla.strip().upper()}/60x60.png"
    )
