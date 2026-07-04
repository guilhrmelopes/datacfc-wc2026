"""Calendário da Copa — grupos, horários e status via FotMob."""

from __future__ import annotations

import gzip
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers.fotmob_mapa import FOTMOB_PARA_SELECAO, fotmob_para_selecao

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


def _segmentos_nome_fotmob(nome: str) -> list[str]:
    if not nome:
        return []
    if "/" in nome:
        return [parte.strip() for parte in nome.split("/") if parte.strip()]
    return [nome.strip()]


def _resolver_selecao_fotmob(nome: str) -> tuple[str | None, str | None]:
    """Primeiro segmento mapeável (ex.: 'Germany/3ABCDF' → GERMANY, 'Germany')."""
    for segmento in _segmentos_nome_fotmob(nome):
        selecao = fotmob_para_selecao(segmento)
        if selecao:
            return selecao, segmento
    return None, None


def _is_placeholder_fotmob(nome: str, tbd_flag: bool = False) -> bool:
    if tbd_flag:
        return True
    if not nome:
        return True
    if nome.startswith(("Winner", "Loser")):
        return True
    if "/" in nome:
        return True
    if _resolver_selecao_fotmob(nome)[0]:
        return False
    if len(nome) >= 2 and nome[0].isdigit() and "/" not in nome:
        return True
    return fotmob_para_selecao(nome) is None and nome not in FOTMOB_PARA_SELECAO


def _url_escudo_fotmob(team_id: int | None) -> str | None:
    if not team_id:
        return None
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{int(team_id)}.png"


def _normalizar_participante_mata_mata(
    matchup: dict,
    lado: str,
    meta_por_selecao: dict[str, dict],
    meta_por_team_id: dict[int, dict],
    meta_por_sigla: dict[str, dict],
    *,
    stage: str,
    partida: dict | None = None,
) -> dict:
    prefixo = "home" if lado == "home" else "away"
    nome = matchup.get(f"{prefixo}Team", "")
    sigla_api = matchup.get(f"{prefixo}TeamShortName", "")
    team_id = matchup.get(f"{prefixo}TeamId")
    tbd_flag = bool(matchup.get(f"tbdTeam{1 if lado == 'home' else 2}"))

    status = (partida or {}).get("status") or {}
    finalizada = bool(status.get("finished"))
    em_andamento = bool(status.get("started")) and not finalizada
    fase_inicial = stage == "1/16"
    confronto_definido = fase_inicial or finalizada or em_andamento

    bloco_partida = (partida or {}).get(prefixo) or {}
    nome_efetivo = bloco_partida.get("name") or nome
    team_id_efetivo = bloco_partida.get("id") or team_id
    sigla_partida = bloco_partida.get("shortName")

    placeholder = _is_placeholder_fotmob(nome_efetivo, tbd_flag and fase_inicial)

    if not confronto_definido and placeholder:
        rotulo = sigla_api or nome_efetivo or "TBD"
        return {
            "rotulo": rotulo,
            "nome_fotmob": nome_efetivo or nome,
            "selecao": None,
            "sigla": rotulo,
            "url_escudo": None,
            "tbd": True,
            "team_id": team_id_efetivo,
        }

    selecao, _ = _resolver_selecao_fotmob(nome_efetivo)
    if not selecao:
        selecao = fotmob_para_selecao(nome_efetivo)

    meta = None
    if selecao:
        meta = meta_por_selecao.get(selecao)
    elif team_id_efetivo is not None:
        meta = meta_por_team_id.get(int(team_id_efetivo))

    sigla_exibicao = (meta or {}).get("sigla") if not placeholder else None
    if not sigla_exibicao:
        sigla_exibicao = sigla_partida or sigla_api or nome_efetivo

    if not meta and sigla_exibicao and sigla_exibicao not in ("TBD",):
        meta = meta_por_sigla.get(sigla_exibicao)
        if meta and not selecao:
            selecao = meta.get("selecao")

    escudo = None
    if meta and meta.get("url_escudo"):
        escudo = meta["url_escudo"]
    elif not placeholder and team_id_efetivo is not None:
        escudo = _url_escudo_fotmob(int(team_id_efetivo))

    return {
        "rotulo": sigla_api or nome_efetivo,
        "nome_fotmob": nome_efetivo,
        "selecao": selecao if not placeholder else None,
        "sigla": sigla_exibicao,
        "url_escudo": escudo,
        "tbd": placeholder,
        "team_id": team_id_efetivo,
    }


def _resolver_vencedor_confronto(
    matchup: dict,
    partida: dict,
    home_bloco: dict,
    away_bloco: dict,
    finalizada: bool,
) -> tuple[bool, bool]:
    """Vitória no tempo normal, prorrogação ou pênaltis (FotMob: aggregatedWinner = team id)."""
    if not finalizada:
        return False, False

    if home_bloco.get("winner") is True:
        return True, False
    if away_bloco.get("winner") is True:
        return False, True

    home_id = home_bloco.get("id") or matchup.get("homeTeamId")
    away_id = away_bloco.get("id") or matchup.get("awayTeamId")
    vencedor = matchup.get("aggregatedWinner")
    if vencedor is None:
        vencedor = matchup.get("winner")

    if vencedor == "home":
        return True, False
    if vencedor == "away":
        return False, True

    if vencedor is not None and home_id is not None and away_id is not None:
        try:
            vid = int(vencedor)
            if vid == int(home_id):
                return True, False
            if vid == int(away_id):
                return False, True
        except (TypeError, ValueError):
            pass

    agg = matchup.get("aggregatedResult") or {}
    pm = home_bloco.get("score")
    if pm is None:
        pm = agg.get("homeScore")
    pv = away_bloco.get("score")
    if pv is None:
        pv = agg.get("awayScore")
    if pm is not None and pv is not None and pm != pv:
        return pm > pv, pv > pm

    return False, False


def _normalizar_confronto_mata_mata(
    matchup: dict,
    meta_por_selecao: dict[str, dict],
    meta_por_team_id: dict[int, dict],
    meta_por_sigla: dict[str, dict],
) -> dict:
    partidas = matchup.get("matches") or []
    partida = partidas[0] if partidas else {}
    status = partida.get("status") or {}
    utc_time = status.get("utcTime") or ""
    data, hora = _utc_para_hora_brasil(utc_time) if utc_time else ("", "")

    home_bloco = partida.get("home") or {}
    away_bloco = partida.get("away") or {}
    agg = matchup.get("aggregatedResult") or {}

    finalizada = bool(status.get("finished"))
    em_andamento = bool(status.get("started")) and not finalizada
    mostrar_placar = finalizada or em_andamento

    placar_mandante = None
    placar_visitante = None
    if mostrar_placar:
        placar_mandante = home_bloco.get("score")
        if placar_mandante is None:
            placar_mandante = agg.get("homeScore")
        placar_visitante = away_bloco.get("score")
        if placar_visitante is None:
            placar_visitante = agg.get("awayScore")

    mandante_venceu, visitante_venceu = _resolver_vencedor_confronto(
        matchup, partida, home_bloco, away_bloco, finalizada
    )

    return {
        "draw_order": matchup.get("drawOrder"),
        "stage": matchup.get("stage"),
        "match_id": str(partida.get("matchId") or ""),
        "mandante": _normalizar_participante_mata_mata(
            matchup,
            "home",
            meta_por_selecao,
            meta_por_team_id,
            meta_por_sigla,
            stage=matchup.get("stage") or "",
            partida=partida,
        ),
        "visitante": _normalizar_participante_mata_mata(
            matchup,
            "away",
            meta_por_selecao,
            meta_por_team_id,
            meta_por_sigla,
            stage=matchup.get("stage") or "",
            partida=partida,
        ),
        "placar_mandante": placar_mandante,
        "placar_visitante": placar_visitante,
        "mandante_venceu": mandante_venceu,
        "visitante_venceu": visitante_venceu,
        "finalizada": finalizada,
        "em_andamento": em_andamento,
        "data": data,
        "hora": hora,
        "utc_time": utc_time,
    }


def validar_mata_mata(payload: dict) -> None:
    """Garante estrutura mínima do chaveamento antes de publicar no dashboard."""
    fases = payload.get("fases") or []
    if not fases:
        raise ValueError("Mata-mata sem fases.")

    por_stage = {f.get("stage"): f for f in fases if f.get("stage")}
    r32 = por_stage.get("1/16", {}).get("confrontos") or []
    if len(r32) != 16:
        raise ValueError(f"Esperadas 16 partidas na 1/16; recebidas {len(r32)}.")

    for stage, esperado in (("1/8", 8), ("1/4", 4), ("1/2", 2)):
        confrontos = por_stage.get(stage, {}).get("confrontos") or []
        if len(confrontos) != esperado:
            raise ValueError(f"Esperadas {esperado} partidas em {stage}; recebidas {len(confrontos)}.")

    if not payload.get("final"):
        raise ValueError("Confronto da final ausente no mata-mata.")


def extrair_mata_mata_fotmob(selecoes: list[dict] | None = None) -> dict:
    """Chaveamento mata-mata resolvido (playoff.rounds) a partir da API FotMob."""
    payload = _fetch_json(FOTMOB_LEAGUE_URL)
    playoff = payload.get("playoff") or {}
    rounds = playoff.get("rounds") or []
    if not rounds:
        named = (playoff.get("namedKnockouts") or [{}])[0]
        rounds = named.get("rounds") or []

    meta_por_selecao = {s["selecao"]: s for s in (selecoes or []) if s.get("selecao")}
    meta_por_sigla = {s["sigla"]: s for s in (selecoes or []) if s.get("sigla")}
    meta_por_team_id: dict[int, dict] = {}
    for selecao in selecoes or []:
        team_id = selecao.get("selecao_id")
        if team_id is not None:
            meta_por_team_id[int(team_id)] = selecao

    fases: list[dict] = []
    confronto_final: dict | None = None

    for bloco in rounds:
        stage = bloco.get("stage") or ""
        matchups = sorted(
            bloco.get("matchups") or [],
            key=lambda m: (m.get("drawOrder") if m.get("drawOrder", -1) >= 0 else 999, m.get("drawOrder") or 0),
        )
        confrontos = [
            _normalizar_confronto_mata_mata(m, meta_por_selecao, meta_por_team_id, meta_por_sigla)
            for m in matchups
        ]
        if stage == "final" and confrontos:
            confronto_final = confrontos[0]
        else:
            fases.append({"stage": stage, "confrontos": confrontos})

    bronze_raw = playoff.get("bronzeFinal")
    disputa_bronze = None
    if isinstance(bronze_raw, dict) and bronze_raw.get("matches"):
        disputa_bronze = _normalizar_confronto_mata_mata(
            bronze_raw, meta_por_selecao, meta_por_team_id, meta_por_sigla
        )

    return {
        "modo": playoff.get("name") or "As it stands",
        "fonte": "playoff.rounds",
        "fases": fases,
        "final": confronto_final,
        "disputa_bronze": disputa_bronze,
    }


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
