"""Integração provaveisdocartola.com.br — lineups, bolas paradas e fotos."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from scrapers.matching_cartola import atribuir_nomes_a_jogadores

URL_LINEUPS = "https://provaveisdocartola.com.br/api/copa/lineups"
URL_BOLAS_PARADAS = "https://provaveisdocartola.com.br/api/copa/bolas-paradas"
SIT_PROVAVEL = "provavel"

_CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://provaveisdocartola.com.br/copa",
}


def _fetch_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers=_CABECALHOS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    if not isinstance(payload, dict):
        raise ValueError(f"Resposta inesperada de {url}")
    return payload


def buscar_ids_provaveis_lineup(
    logger: logging.Logger | None = None,
) -> set[int]:
    """
    Titulares com sit=provavel nos lineups da Copa.
    Usado exclusivamente para status_id=6; demais status vêm do Cartola /copa.
    """
    log = logger or logging.getLogger("provaveis_copa")
    try:
        payload = _fetch_json(URL_LINEUPS)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as erro:
        log.warning("Lineups Prováveis indisponíveis: %s", erro)
        return set()

    ids: set[int] = set()
    for team in (payload.get("teams") or {}).values():
        if not isinstance(team, dict):
            continue
        for titular in team.get("titulares") or []:
            if not isinstance(titular, dict):
                continue
            if titular.get("sit") != SIT_PROVAVEL:
                continue
            try:
                ids.add(int(titular["id"]))
            except (TypeError, ValueError, KeyError):
                continue

    log.info("Prováveis lineups: %d titulares (sit=provavel).", len(ids))
    return ids


def buscar_bolas_paradas(
    logger: logging.Logger | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Retorna slug → {penaltis, escanteios_faltas} (apelidos Prováveis)."""
    log = logger or logging.getLogger("provaveis_copa")
    url = f"{URL_BOLAS_PARADAS}?_={int(time.time() * 1000)}"
    try:
        payload = _fetch_json(url)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as erro:
        log.warning("Bolas paradas Prováveis indisponíveis: %s", erro)
        return {}

    selecoes = payload.get("selecoes") or {}
    resultado: dict[str, dict[str, list[str]]] = {}
    for slug, bloco in selecoes.items():
        if not isinstance(bloco, dict):
            continue
        pen = [str(x).strip() for x in (bloco.get("penaltis") or []) if str(x).strip()]
        bp = [
            str(x).strip()
            for x in (bloco.get("escanteios_faltas") or [])
            if str(x).strip()
        ]
        if pen or bp:
            resultado[str(slug)] = {"penaltis": pen, "escanteios_faltas": bp}

    log.info("Bolas paradas: %d seleções com cobradores.", len(resultado))
    return resultado


def _slug_por_clube(lineups: dict) -> dict[int, str]:
    mapa: dict[int, str] = {}
    for slug, team in (lineups.get("teams") or {}).items():
        if not isinstance(team, dict):
            continue
        try:
            clube_id = int(team.get("selecao_id"))
        except (TypeError, ValueError):
            continue
        mapa[clube_id] = str(slug)
    return mapa


def compilar_cobradores_por_atleta(
    mercado: list[dict],
    *,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """
    Cruza bolas-paradas (apelidos) com elenco Cartola por clube_id.
    Retorna payload pronto para cobradores_copa.json.
    """
    log = logger or logging.getLogger("provaveis_copa")

    try:
        lineups = _fetch_json(URL_LINEUPS)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as erro:
        log.warning("Lineups indisponíveis para cobradores: %s", erro)
        return _payload_cobradores_vazio()

    bolas = buscar_bolas_paradas(log)
    if not bolas:
        return _payload_cobradores_vazio()

    slug_por_clube = _slug_por_clube(lineups)
    pool_por_clube: dict[int, list[dict]] = {}
    for jog in mercado:
        try:
            cid = int(jog.get("clube_id") or 0)
        except (TypeError, ValueError):
            continue
        if cid:
            pool_por_clube.setdefault(cid, []).append(jog)

    por_atleta: dict[str, dict[str, int | bool]] = {}
    nao_resolvidos: list[str] = []

    for clube_id, slug in slug_por_clube.items():
        bloco = bolas.get(slug)
        if not bloco:
            continue
        pool = pool_por_clube.get(clube_id) or []
        if not pool:
            continue

        pen_map = atribuir_nomes_a_jogadores(bloco.get("penaltis") or [], pool)
        bp_map = atribuir_nomes_a_jogadores(bloco.get("escanteios_faltas") or [], pool)

        for idx, nome in enumerate(bloco.get("penaltis") or [], start=1):
            par = pen_map.get(nome)
            if not par:
                nao_resolvidos.append(f"{slug}/P:{nome}")
                continue
            aid = str(int(par[0]["atleta_id"]))
            entry = por_atleta.setdefault(aid, {})
            entry["penalti"] = True
            entry["ordem_penalti"] = idx

        for idx, nome in enumerate(bloco.get("escanteios_faltas") or [], start=1):
            par = bp_map.get(nome)
            if not par:
                nao_resolvidos.append(f"{slug}/BP:{nome}")
                continue
            aid = str(int(par[0]["atleta_id"]))
            entry = por_atleta.setdefault(aid, {})
            entry["escanteio"] = True
            entry["ordem_escanteio"] = idx
            entry["falta"] = True
            entry["ordem_falta"] = idx

    if nao_resolvidos:
        log.warning(
            "Cobradores não resolvidos (%d): %s",
            len(nao_resolvidos),
            ", ".join(nao_resolvidos[:8]),
        )

    log.info(
        "Cobradores compilados: %d atletas (%d P + %d BP únicos).",
        len(por_atleta),
        sum(1 for v in por_atleta.values() if v.get("penalti")),
        sum(1 for v in por_atleta.values() if v.get("escanteio")),
    )

    return {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "fonte": "provaveisdocartola.com.br/api/copa/bolas-paradas",
        "selecoes_com_dados": len(bolas),
        "por_atleta": por_atleta,
    }


def _payload_cobradores_vazio() -> dict[str, Any]:
    return {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "fonte": URL_BOLAS_PARADAS,
        "selecoes_com_dados": 0,
        "por_atleta": {},
    }
