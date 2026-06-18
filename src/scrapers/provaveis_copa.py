"""Lineups prováveis da Copa — provaveisdocartola.com.br (somente status Provável)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

URL_LINEUPS = "https://provaveisdocartola.com.br/api/copa/lineups"
SIT_PROVAVEL = "provavel"

_CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
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
