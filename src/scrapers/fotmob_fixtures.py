"""Calendário da Copa — grupos, horários e status via FotMob."""

from __future__ import annotations

import gzip
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers.fotmob_mapa import fotmob_para_selecao

FOTMOB_LEAGUE_URL = "https://www.fotmob.com/api/data/leagues?id=77"
FUSO_CARTOLA = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class PartidaCalendario:
    match_id: str
    grupo: str
    rodada: int
    mandante: str
    visitante: str
    data: str
    hora: str
    utc_time: str
    finalizada: bool
    placar: str | None


def _fetch_json(url: str):
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def _utc_para_hora_brasil(utc_iso: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(FUSO_CARTOLA)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def listar_partidas_grupos() -> list[PartidaCalendario]:
    payload = _fetch_json(FOTMOB_LEAGUE_URL)
    partidas: list[PartidaCalendario] = []

    for bloco in payload.get("overview", {}).get("matches", {}).get("allMatches", []):
        grupo = bloco.get("group")
        rodada_raw = bloco.get("round")
        if not grupo or rodada_raw not in ("1", "2", "3"):
            continue

        home = bloco.get("home", {}).get("name", "")
        away = bloco.get("away", {}).get("name", "")
        mandante = fotmob_para_selecao(home)
        visitante = fotmob_para_selecao(away)
        if not mandante or not visitante:
            continue

        status = bloco.get("status") or {}
        utc_time = status.get("utcTime") or ""
        data, hora = _utc_para_hora_brasil(utc_time) if utc_time else ("", "")

        partidas.append(
            PartidaCalendario(
                match_id=str(bloco.get("id", "")),
                grupo=str(grupo),
                rodada=int(rodada_raw),
                mandante=mandante,
                visitante=visitante,
                data=data,
                hora=hora,
                utc_time=utc_time,
                finalizada=bool(status.get("finished")),
                placar=status.get("scoreStr"),
            )
        )

    partidas.sort(key=lambda p: (p.rodada, p.data, p.hora, p.match_id))
    return partidas


def extrair_classificacao_grupos() -> dict[str, list[dict]]:
    """Tabelas dos grupos A–L a partir do endpoint de ligas."""
    payload = _fetch_json(FOTMOB_LEAGUE_URL)
    tabelas: dict[str, list[dict]] = {}

    for block in payload.get("table", [{}])[0].get("data", {}).get("tables", []):
        nome = block.get("leagueName", "")
        if not nome.startswith("Grp. "):
            continue
        grupo = nome.replace("Grp. ", "").strip()
        linhas = []
        for idx, row in enumerate(block.get("table", {}).get("all", []), start=1):
            selecao = fotmob_para_selecao(row.get("name", ""))
            if not selecao:
                continue
            scores = (row.get("scoresStr") or "0-0").replace(" ", "").split("-")
            gm = int(scores[0]) if len(scores) > 0 else 0
            gs = int(scores[1]) if len(scores) > 1 else 0
            j = int(row.get("played") or 0)
            v = int(row.get("wins") or 0)
            e = int(row.get("draws") or 0)
            d = int(row.get("losses") or 0)
            pts = int(row.get("pts") or 0)
            aprov = round((pts / (j * 3) * 100), 1) if j > 0 else 0.0
            linhas.append(
                {
                    "posicao": idx,
                    "selecao": selecao,
                    "sigla": None,
                    "url_escudo": None,
                    "P": pts,
                    "J": j,
                    "V": v,
                    "E": e,
                    "D": d,
                    "GM": gm,
                    "GS": gs,
                    "SG": gm - gs,
                    "aprov": aprov,
                }
            )
        tabelas[grupo] = linhas

    return tabelas


def extrair_melhores_terceiros_fotmob(limite: int = 8) -> list[str]:
    """Top N da tabela FotMob 'Best 3rd placed teams' (Melhores Equipas Em 3º. Lugar)."""
    payload = _fetch_json(FOTMOB_LEAGUE_URL)

    for block in payload.get("table", [{}])[0].get("data", {}).get("tables", []):
        if block.get("leagueName") != "Best 3rd placed teams":
            continue
        rows = block.get("table", {}).get("all", [])
        selecoes: list[str] = []
        for row in rows[:limite]:
            selecao = fotmob_para_selecao(row.get("name", ""))
            if selecao:
                selecoes.append(selecao)
        return selecoes

    return []
