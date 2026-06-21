"""Elo ratings das 48 seleções da Copa 2026 — fonte: eloratings.net."""

from __future__ import annotations

import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

URL_COPA_2026 = "https://www.eloratings.net/2026_World_Cup.tsv"

# Código eloratings.net (3 letras) → sigla Cartola
ELO_CODIGO_PARA_SIGLA: dict[str, str] = {
    "ES": "ESP",
    "AR": "ARG",
    "FR": "FRA",
    "EN": "ING",
    "CO": "COL",
    "BR": "BRA",
    "NL": "HOL",
    "PT": "POR",
    "DE": "ALE",
    "NO": "NOR",
    "JP": "JAP",
    "MX": "MEX",
    "EC": "EQU",
    "CH": "SUI",
    "HR": "CRO",
    "BE": "BEL",
    "UY": "URU",
    "MA": "MAR",
    "AT": "AUT",
    "SN": "SEN",
    "US": "EUA",
    "PY": "PAR",
    "TR": "TUR",
    "AU": "AUS",
    "CA": "CAN",
    "KR": "COR",
    "SQ": "ESC",
    "DZ": "AGL",
    "IR": "IRA",
    "CI": "CDM",
    "SE": "SUE",
    "EG": "EGI",
    "UZ": "UZB",
    "CZ": "TCH",
    "PA": "PAN",
    "CD": "RDC",
    "JO": "JOR",
    "CV": "CAB",
    "SA": "ARS",
    "BA": "BOS",
    "IQ": "IRQ",
    "TN": "TUN",
    "NZ": "NZE",
    "GH": "GAN",
    "HT": "HAI",
    "ZA": "AFS",
    "QA": "CAT",
    "CW": "CUR",
}


def _fetch_tsv(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def elo_para_rating_100(elo: float, elo_min: float, elo_max: float) -> float:
    if elo_max <= elo_min:
        return 50.0
    return round(max(0.0, min(100.0, (elo - elo_min) / (elo_max - elo_min) * 100)), 1)


def buscar_elos_copa_2026() -> dict[str, dict[str, Any]]:
    """
    Retorna {sigla: {elo, rating_100, rank, codigo_elo}} para as 48 seleções.
    """
    bruto = _fetch_tsv(URL_COPA_2026)
    linhas = [ln for ln in bruto.splitlines() if ln.strip()]
    if len(linhas) < 40:
        raise ValueError(f"TSV Copa 2026 incompleto ({len(linhas)} linhas).")

    por_sigla: dict[str, dict[str, Any]] = {}
    elos: list[float] = []

    for linha in linhas:
        partes = linha.split("\t")
        if len(partes) < 4:
            continue
        try:
            rank = int(partes[0])
            codigo = partes[2].strip().upper()
            elo = float(partes[3])
        except (TypeError, ValueError):
            continue
        sigla = ELO_CODIGO_PARA_SIGLA.get(codigo)
        if not sigla:
            logger.warning("Código Elo sem mapeamento: %s (rank %s)", codigo, rank)
            continue
        por_sigla[sigla] = {
            "elo": elo,
            "rank": rank,
            "codigo_elo": codigo,
        }
        elos.append(elo)

    if len(por_sigla) < 45:
        raise ValueError(f"Apenas {len(por_sigla)}/48 seleções mapeadas no Elo.")

    elo_min, elo_max = min(elos), max(elos)
    for info in por_sigla.values():
        info["rating_100"] = elo_para_rating_100(info["elo"], elo_min, elo_max)

    logger.info(
        "Elo Copa 2026: %d seleções (Elo %.0f–%.0f).",
        len(por_sigla),
        elo_min,
        elo_max,
    )
    return por_sigla


def atualizar_selecoes_elo(selecoes: list[dict]) -> tuple[int, list[str]]:
    """Preenche elo_rating, rating_elo_100 e elo_rank em cada seleção."""
    elos = buscar_elos_copa_2026()
    atualizados = 0
    faltando: list[str] = []

    for selecao in selecoes:
        sigla = str(selecao.get("sigla") or "").upper()
        info = elos.get(sigla)
        if not info:
            faltando.append(sigla)
            continue
        selecao["elo_rating"] = info["elo"]
        selecao["elo_rank"] = info["rank"]
        selecao["rating_elo_100"] = info["rating_100"]
        selecao["elo_atualizado_em"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        atualizados += 1

    return atualizados, faltando
