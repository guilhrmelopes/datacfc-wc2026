"""
Resolução determinística calendário → oddsEventId (OddsNotifier).

Prioridade:
  1. fixture_id / match_id (cache versionado)
  2. chave de confronto (API pública + cache local)
  3. varredura de IDs (somente se ODDS_ALLOW_ID_SCAN=1)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scrapers.mapeamento_selecoes_odds import chave_confronto, normalizar_selecao
from scrapers.odds_armazenamento import parse_data_calendario, referencia_hoje

logger = logging.getLogger(__name__)

_RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_EVENTOS = _RAIZ / "frontend" / "public" / "data" / "eventos_odds_rodada1.json"

URLS_API_EVENTOS = (
    "https://hub.oddsnotifier.io/api/events/football/international-fifa-world-cup",
    "https://hub.oddsnotifier.io/api/events/football/international-world-cup",
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

ODDS_ID_SCAN_MIN: int = int(os.environ.get("ODDS_ID_SCAN_MIN", "66456900"))
ODDS_ID_SCAN_MAX: int = int(os.environ.get("ODDS_ID_SCAN_MAX", "66458500"))


def permitir_varredura_ids() -> bool:
    return os.environ.get("ODDS_ALLOW_ID_SCAN", "").strip().lower() in ("1", "true", "yes")


def _fetch_eventos_api() -> list[dict]:
    for url_api in URLS_API_EVENTOS:
        for tentativa in range(4):
            try:
                req = urllib.request.Request(
                    url_api,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "application/json",
                        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                    },
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    bruto = json.loads(resp.read().decode("utf-8"))
                if isinstance(bruto, list):
                    lista = [e for e in bruto if isinstance(e, dict)]
                elif isinstance(bruto, dict):
                    lista = []
                    for chave in ("events", "data", "fixtures"):
                        bloco = bruto.get(chave)
                        if isinstance(bloco, list):
                            lista = [e for e in bloco if isinstance(e, dict)]
                            break
                else:
                    lista = []
                if lista:
                    logger.info(
                        "API eventos (%s): %d fixtures.",
                        url_api.rsplit("/", 1)[-1],
                        len(lista),
                    )
                    return lista
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and tentativa < 3:
                    espera = 12 * (tentativa + 1)
                    logger.warning("API eventos 429 — aguardando %ds...", espera)
                    time.sleep(espera)
                    continue
                logger.warning("API eventos HTTP %s (%s)", exc.code, url_api)
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                logger.warning("API eventos indisponivel (%s): %s", url_api, exc)
                break
    return []


def normalizar_evento_api(ev: dict) -> dict | None:
    eid = ev.get("id") or ev.get("oddsEventId") or ev.get("eventId")
    if eid is None:
        return None
    home = ev.get("home") or ev.get("homeTeam") or ev.get("homeName") or ""
    away = ev.get("away") or ev.get("awayTeam") or ev.get("awayName") or ""
    if isinstance(home, dict):
        home = home.get("name", "")
    if isinstance(away, dict):
        away = away.get("name", "")
    if not home or not away:
        return None
    return {
        "id": int(eid),
        "home": str(home),
        "away": str(away),
        "date": ev.get("date") or ev.get("startTime") or ev.get("utc") or "",
        "home_id": ev.get("homeId"),
        "away_id": ev.get("awayId"),
        "fixture_id": ev.get("fixture_id") or ev.get("fixtureId"),
    }


def carregar_cache_arquivo() -> tuple[dict[tuple[str, str], int], dict[str, int], list[dict]]:
    """Retorna (por_confronto, por_fixture_id, eventos_brutos)."""
    por_confronto: dict[tuple[str, str], int] = {}
    por_fixture: dict[str, int] = {}
    eventos: list[dict] = []

    if not CAMINHO_EVENTOS.is_file():
        return por_confronto, por_fixture, eventos

    try:
        bruto = json.loads(CAMINHO_EVENTOS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return por_confronto, por_fixture, eventos

    for ev in bruto.get("eventos", bruto if isinstance(bruto, list) else []):
        if not isinstance(ev, dict) or "id" not in ev:
            continue
        eventos.append(ev)
        eid = int(ev["id"])
        por_confronto[chave_confronto(ev.get("home", ""), ev.get("away", ""))] = eid
        fid = ev.get("fixture_id")
        if fid is not None:
            por_fixture[str(fid)] = eid

    return por_confronto, por_fixture, eventos


def listar_eventos_api_normalizados() -> list[dict]:
    saida: list[dict] = []
    for bruto in _fetch_eventos_api():
        ev = normalizar_evento_api(bruto)
        if ev:
            saida.append(ev)
    return saida


def construir_indice_eventos(*, usar_api: bool = True) -> tuple[dict[tuple[str, str], int], dict[str, int]]:
    por_confronto, por_fixture, _ = carregar_cache_arquivo()

    if usar_api:
        for ev in listar_eventos_api_normalizados():
            por_confronto[chave_confronto(ev["home"], ev["away"])] = int(ev["id"])
            fid = ev.get("fixture_id")
            if fid is not None:
                por_fixture[str(fid)] = int(ev["id"])

    return por_confronto, por_fixture


def _data_fixture(fx: dict) -> date | None:
    bruto = fx.get("date") or fx.get("data") or ""
    if isinstance(bruto, str) and "T" in bruto:
        bruto = bruto[:10]
    return parse_data_calendario(str(bruto)[:10] if bruto else "")


def _match_fixture_fuzzy(fx: dict, eventos: list[dict]) -> dict | None:
    """
    Fallback: um time do calendário FotMob + data próxima (±2d) no OddsNotifier.
    Cobre bracket desatualizado (ex.: Suíça×Irã → Suíça×Argélia na API).
    """
    home = normalizar_selecao(fx.get("home", ""))
    away = normalizar_selecao(fx.get("away", ""))
    data_fx = _data_fixture(fx)
    if not home or not data_fx:
        return None

    candidatos: list[tuple[int, int, dict]] = []
    for ev in eventos:
        eh = normalizar_selecao(ev.get("home", ""))
        ea = normalizar_selecao(ev.get("away", ""))
        data_ev = parse_data_calendario((ev.get("date") or "")[:10])
        if not data_ev:
            continue
        dias = abs((data_ev - data_fx).days)
        if dias > 2:
            continue
        if home in (eh, ea):
            candidatos.append((dias, int(ev["id"]), ev))
        elif away in (eh, ea):
            candidatos.append((dias + 1, int(ev["id"]), ev))

    if not candidatos:
        return None
    candidatos.sort(key=lambda item: (item[0], item[1]))
    melhor_dias = candidatos[0][0]
    no_melhor = [ev for d, _, ev in candidatos if d == melhor_dias]
    if len(no_melhor) == 1:
        return no_melhor[0]
    return None


def mapear_fixtures(
    fixtures: list[dict],
    por_confronto: dict[tuple[str, str], int],
    por_fixture: dict[str, int],
    *,
    eventos_api: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Associa oddsEventId a cada fixture do calendário.
    Retorna (mapeados, faltando).
    """
    mapeados: list[dict] = []
    faltando: list[dict] = []
    api_eventos = eventos_api if eventos_api is not None else listar_eventos_api_normalizados()

    for fx in fixtures:
        if fx.get("id"):
            mapeados.append({**fx, "id": int(fx["id"])})
            continue

        fid = fx.get("fixture_id") or fx.get("match_id")
        if fid is not None and str(fid) in por_fixture:
            mapeados.append({**fx, "id": int(por_fixture[str(fid)])})
            continue

        chave = chave_confronto(fx.get("home", ""), fx.get("away", ""))
        eid = por_confronto.get(chave)
        if eid:
            mapeados.append({**fx, "id": eid})
            continue

        fuzzy = _match_fixture_fuzzy(fx, api_eventos)
        if fuzzy:
            mapeados.append({
                **fx,
                "id": int(fuzzy["id"]),
                "home": fx.get("home") or fuzzy.get("home", ""),
                "away": fx.get("away") or fuzzy.get("away", ""),
                "date": fuzzy.get("date") or fx.get("date"),
            })
        else:
            faltando.append(fx)

    return mapeados, faltando


def reconciliar_adversarios_mercado_odds(
    mercado: list[dict],
    meta_por_selecao: dict[str, dict],
    *,
    apenas_playoffs: bool = True,
) -> int:
    """
    Alinha ADV/data do mercado ao OddsNotifier quando o bracket FotMob diverge.
  Fonte de verdade para odds de apostas.
    """
    eventos = listar_eventos_api_normalizados()
    if not eventos:
        return 0

    ref = referencia_hoje()
    alterados = 0
    vistos: set[str] = set()

    for j in mercado:
        if apenas_playoffs and j.get("ativo_playoffs") is False:
            continue
        selecao = (j.get("selecao") or "").upper()
        if not selecao or selecao in vistos:
            continue

        prox_data = parse_data_calendario((j.get("proximo_adversario_data") or "").strip())
        prox_sigla = (j.get("proximo_adversario_sigla") or "").strip().upper()

        candidatos: list[tuple[int, date, str, dict]] = []
        for ev in eventos:
            eh = normalizar_selecao(ev.get("home", ""))
            ea = normalizar_selecao(ev.get("away", ""))
            if selecao not in (eh, ea):
                continue
            ev_date = parse_data_calendario((ev.get("date") or "")[:10])
            if not ev_date or ev_date < ref:
                continue
            adv_nome = ea if selecao == eh else eh
            adv_meta = meta_por_selecao.get(adv_nome)
            if not adv_meta:
                continue
            adv_sigla = (adv_meta.get("sigla") or "").upper()
            dias = abs((ev_date - prox_data).days) if prox_data else 0
            candidatos.append((dias, ev_date, adv_sigla, adv_meta))

        if not candidatos:
            continue
        candidatos.sort(key=lambda item: (item[0], item[1]))
        _, nova_data, nova_sigla, adv_meta = candidatos[0]

        if prox_sigla == nova_sigla and j.get("proximo_adversario_data") == nova_data.isoformat():
            vistos.add(selecao)
            continue

        for jog in mercado:
            if (jog.get("selecao") or "").upper() != selecao:
                continue
            if jog.get("ativo_playoffs") is False and apenas_playoffs:
                continue
            jog["proximo_adversario_sigla"] = nova_sigla
            jog["proximo_adversario_escudo"] = adv_meta.get("url_escudo")
            jog["proximo_adversario_data"] = nova_data.isoformat()
            alterados += 1
        vistos.add(selecao)

    if alterados:
        logger.info("ADV reconciliados com OddsNotifier: %d jogadores.", alterados)
    return alterados


def salvar_cache_eventos(eventos: list[dict], rodada: int) -> None:
    CAMINHO_EVENTOS.parent.mkdir(parents=True, exist_ok=True)
    existentes: list[dict] = []
    if CAMINHO_EVENTOS.is_file():
        try:
            bruto = json.loads(CAMINHO_EVENTOS.read_text(encoding="utf-8"))
            existentes = [
                e for e in (bruto.get("eventos") or [])
                if isinstance(e, dict) and "id" in e
            ]
        except (json.JSONDecodeError, OSError):
            existentes = []

    por_id: dict[int, dict] = {int(e["id"]): e for e in existentes}
    for ev in eventos:
        if "id" not in ev:
            continue
        por_id[int(ev["id"])] = {
            "id": int(ev["id"]),
            "home": ev.get("home", ""),
            "away": ev.get("away", ""),
            "date": ev.get("date", ""),
            "fixture_id": ev.get("fixture_id") or ev.get("match_id"),
        }

    payload = {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "rodada": rodada,
        "eventos": sorted(por_id.values(), key=lambda e: e.get("date", str(e["id"]))),
    }
    with CAMINHO_EVENTOS.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Cache eventos salvo: %d partidas -> %s", len(por_id), CAMINHO_EVENTOS)


def varredura_ids_playwright(
    pagina: Any,
    faltando: list[dict],
    cache_confronto: dict[tuple[str, str], int],
    *,
    nome_evento_fn: Any,
    times_do_nome_fn: Any,
    url_evento_fn: Any,
    timeout_ms: int = 35000,
) -> dict[tuple[str, str], int]:
    """Fallback lento: varre faixa de IDs no hub (requer Playwright)."""
    if not faltando or not permitir_varredura_ids():
        if faltando and not permitir_varredura_ids():
            logger.info(
                "Varredura de IDs desativada (%d partidas sem mapeamento). "
                "Defina ODDS_ALLOW_ID_SCAN=1 para habilitar.",
                len(faltando),
            )
        return {}

    logger.info("Varredura de IDs para %d partidas...", len(faltando))
    chaves_faltando = {chave_confronto(f["home"], f["away"]) for f in faltando}
    novos: dict[tuple[str, str], int] = {}

    for eid in range(ODDS_ID_SCAN_MIN, ODDS_ID_SCAN_MAX):
        if not chaves_faltando:
            break
        if eid in cache_confronto.values():
            continue
        try:
            pagina.goto(url_evento_fn(eid), timeout=timeout_ms, wait_until="domcontentloaded")
            pagina.wait_for_timeout(1200)
            titulo = pagina.title()
            m = re.search(r"^(.+?) Odds \|", titulo)
            nome = m.group(1).strip() if m and " vs " in m.group(1) else None
            if not nome:
                nome = nome_evento_fn(pagina, eid)
        except Exception:
            continue
        if not nome:
            continue
        times = times_do_nome_fn(nome)
        if not times:
            continue
        chave = chave_confronto(times[0], times[1])
        if chave in chaves_faltando:
            novos[chave] = eid
            chaves_faltando.discard(chave)
            logger.info("  mapeado %d -> %s", eid, nome)

    return novos
