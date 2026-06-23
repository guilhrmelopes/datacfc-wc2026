"""Elo ratings das 48 seleções da Copa 2026 — fonte: eloratings.net."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

URL_COPA_2026 = "https://www.eloratings.net/2026_World_Cup.tsv"

_RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_CACHE_ELO = _RAIZ / "frontend" / "public" / "data" / "elo_copa_2026.json"

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

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eloratings.net/",
}


def _normalizar_numero(valor: str) -> float:
    bruto = (valor or "").strip()
    bruto = bruto.replace("\u2212", "-").replace("\u2013", "-").replace(",", "")
    bruto = re.sub(r"[^\d.\-+]", "", bruto)
    return float(bruto)


def _fetch_tsv(url: str, *, tentativas: int = 3) -> str:
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=45) as resp:
                bruto = resp.read().decode("utf-8", errors="replace")
            if bruto.strip():
                return bruto
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo_erro = exc
            logger.warning(
                "Fetch Elo tentativa %d/%d falhou: %s",
                tentativa + 1,
                tentativas,
                exc,
            )
            time.sleep(2 * (tentativa + 1))
    raise RuntimeError(f"Falha ao baixar Elo de {url}") from ultimo_erro


def _carregar_cache_elo() -> dict[str, dict[str, Any]] | None:
    if not CAMINHO_CACHE_ELO.is_file():
        return None
    try:
        payload = json.loads(CAMINHO_CACHE_ELO.read_text(encoding="utf-8"))
        selecoes = payload.get("selecoes")
        if isinstance(selecoes, dict) and len(selecoes) >= 45:
            return selecoes
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Cache Elo inválido: %s", exc)
    return None


def _salvar_cache_elo(por_sigla: dict[str, dict[str, Any]]) -> None:
    payload = {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "fonte": URL_COPA_2026,
        "selecoes": por_sigla,
    }
    CAMINHO_CACHE_ELO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_CACHE_ELO.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parsear_tsv(bruto: str) -> dict[str, dict[str, Any]]:
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
            if len(codigo) != 2 and len(codigo) != 3:
                codigo = partes[1].strip().upper()
            elo = _normalizar_numero(partes[3])
        except (TypeError, ValueError):
            continue
        if not re.fullmatch(r"[A-Z]{2,3}", codigo or ""):
            continue
        sigla = ELO_CODIGO_PARA_SIGLA.get(codigo)
        if not sigla:
            logger.debug("Código Elo sem mapeamento: %s (rank %s)", codigo, rank)
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
    return por_sigla


def elo_para_rating_100(elo: float, elo_min: float, elo_max: float) -> float:
    if elo_max <= elo_min:
        return 50.0
    return round(max(0.0, min(100.0, (elo - elo_min) / (elo_max - elo_min) * 100)), 1)


def buscar_elos_copa_2026(*, permitir_cache: bool = True) -> dict[str, dict[str, Any]]:
    """
    Retorna {sigla: {elo, rating_100, rank, codigo_elo}} para as 48 seleções.
    Usa cache local se o fetch remoto falhar (comum em CI).
    """
    try:
        bruto = _fetch_tsv(URL_COPA_2026)
        por_sigla = _parsear_tsv(bruto)
        _salvar_cache_elo(por_sigla)
        logger.info(
            "Elo Copa 2026: %d seleções (Elo %.0f–%.0f).",
            len(por_sigla),
            min(v["elo"] for v in por_sigla.values()),
            max(v["elo"] for v in por_sigla.values()),
        )
        return por_sigla
    except (ValueError, RuntimeError, OSError) as exc:
        logger.warning("Fetch Elo remoto falhou: %s", exc)
        if not permitir_cache:
            raise
        cache = _carregar_cache_elo()
        if cache:
            logger.info("Elo: usando cache local (%d seleções).", len(cache))
            return cache
        raise


def atualizar_selecoes_elo(selecoes: list[dict]) -> tuple[int, list[str]]:
    """Preenche elo_rating, rating_elo_100 e elo_rank em cada seleção."""
    try:
        elos = buscar_elos_copa_2026()
    except (ValueError, RuntimeError, OSError) as exc:
        logger.error("Elo indisponível (remoto e cache): %s", exc)
        return 0, [str(s.get("sigla") or "") for s in selecoes if s.get("sigla")]

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
        selecao["elo_atualizado_em"] = datetime.now(tz=timezone.utc).isoformat()
        atualizados += 1

    return atualizados, faltando
