"""Extração FotMob — partida, scouts e pontuação Cartola."""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoring.cartola import (
    BUCKETS,
    Bucket,
    ScoutsPartida,
    calcular_pontos,
)

FOTMOB_MATCH_URL = "https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
FOTMOB_LEAGUE_URL = "https://www.fotmob.com/api/data/leagues?id=77"
SEASON_STATS_BASE = "https://data.fotmob.com/stats/77/season/24254"

from scrapers.fotmob_mapa import SIGLA_PARA_FOTMOB_STATS

SIGLA_POR_FOTMOB_TEAM_ID: dict[int, str] = {
    6710: "MEX",
    6316: "AFS",
}

NOME_SELECAO_POR_SIGLA = SIGLA_PARA_FOTMOB_STATS


@dataclass
class JogadorPartida:
    fotmob_id: int
    nome: str
    sigla: str
    bucket: Bucket
    scouts: ScoutsPartida
    pontos: float
    atleta_id: int | None = None
    xg: float = 0.0
    xa: float = 0.0


@dataclass
class ResultadoPartida:
    match_id: str
    sigla_mandante: str
    sigla_visitante: str
    gols_mandante: int
    gols_visitante: int
    jogadores: list[JogadorPartida]


def _fetch_json(url: str) -> Any:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers=headers),
        timeout=30,
    ).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto.lower())
    return " ".join(texto.split())


def _tokens(texto: str) -> list[str]:
    return normalizar_texto(texto).split()


# Expansão de tokens equivalentes (abreviações / apelidos comuns no FotMob vs Cartola).
_SINONIMOS_TOKEN: dict[str, str] = {
    "jr": "junior",
    "junior": "jr",
    "vini": "vinicius",
    "vinicius": "vini",
}


def _tokens_expandidos(texto: str) -> set[str]:
    tokens = set(_tokens(texto))
    for token in list(tokens):
        par = _SINONIMOS_TOKEN.get(token)
        if par:
            tokens.add(par)
    return tokens


# Nome FotMob normalizado → atleta_id Cartola (casos onde fuzzy/token falha).
_ALIAS_FOTMOB_ATLETA: dict[str, int] = {
    "yassine bounou": 80951,
    "bounou": 80951,
    "patrick beach": 151039,
    "patrick thomas beach": 151039,
}


def _score_fuzzy_nome(a: str, b: str) -> int:
    from difflib import SequenceMatcher

    na, nb = normalizar_texto(a), normalizar_texto(b)
    if not na or not nb:
        return 0
    sort_ratio = int(SequenceMatcher(None, na, nb).ratio() * 100)
    set_a, set_b = _tokens_expandidos(a), _tokens_expandidos(b)
    if set_a and set_b:
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        set_ratio = int((inter / union) * 100) if union else 0
    else:
        set_ratio = 0
    return max(sort_ratio, set_ratio)


def carregar_mercado_por_sigla(caminho: Path, siglas: set[str]) -> dict[str, list[dict]]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    por_sigla: dict[str, list[dict]] = {s: [] for s in siglas}
    for jogador in dados:
        sigla = jogador.get("sigla")
        if sigla in siglas:
            por_sigla[sigla].append(jogador)
    return por_sigla


def associar_jogador_mercado(
    nome_fotmob: str,
    mercado: list[dict],
    *,
    is_goleiro: bool = False,
    excluir_ids: set[int] | None = None,
) -> dict | None:
    candidatos = mercado
    if is_goleiro:
        candidatos = [j for j in mercado if j.get("bucket_posicao") == "GOL"] or mercado
    if excluir_ids:
        candidatos = [j for j in candidatos if int(j.get("atleta_id") or 0) not in excluir_ids]

    chave_alias = normalizar_texto(nome_fotmob)
    alvo_id = _ALIAS_FOTMOB_ATLETA.get(chave_alias)
    if alvo_id:
        for jogador in candidatos:
            if int(jogador.get("atleta_id") or 0) == alvo_id:
                return jogador

    nome_norm = normalizar_texto(nome_fotmob)
    tokens_fotmob = _tokens_expandidos(nome_fotmob)

    melhor: tuple[int, int, dict] | None = None
    for jogador in candidatos:
        apelido = jogador.get("apelido", "")
        ap_norm = normalizar_texto(apelido)
        tokens_ap = _tokens_expandidos(apelido)

        score = 0
        if ap_norm and ap_norm in nome_norm:
            score = 100 + len(ap_norm)
        elif tokens_ap and tokens_ap <= tokens_fotmob:
            score = 80 + len(tokens_ap)
        elif tokens_ap:
            inter = tokens_ap & tokens_fotmob
            if inter:
                score = 50 + len(inter) * 10

        sobrenome_fotmob = _tokens(nome_fotmob)[-1] if _tokens(nome_fotmob) else ""
        if len(_tokens(apelido)) == 1 and sobrenome_fotmob == _tokens(apelido)[0]:
            score = max(score, 70)

        fuzzy = _score_fuzzy_nome(nome_fotmob, apelido)
        if fuzzy >= 85:
            score = max(score, fuzzy)

        if score <= 0:
            continue

        # Desempate: quem já estreou na Copa (Cartola) vs reserva sem minutos.
        jogos_copa = int(jogador.get("copa_jogos_num") or 0)
        chave = (score, jogos_copa)
        if melhor is None or chave > (melhor[0], melhor[1]):
            melhor = (score, jogos_copa, jogador)

    return melhor[2] if melhor else None


def _mapa_nomes_lineup(lineup: dict) -> dict[int, str]:
    """FotMob playerStats usa nomes curtos; o lineup traz nomes completos."""
    nomes: dict[int, str] = {}
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for grupo in ("starters", "subs", "unavailable"):
            for pl in team.get(grupo) or []:
                pid = pl.get("id")
                nome = pl.get("name")
                if pid and nome:
                    nomes[int(pid)] = str(nome)
    return nomes


def _nome_para_matching(player: dict, nomes_lineup: dict[int, str]) -> str:
    nome_stats = str(player.get("name") or "")
    pid = int(player.get("id") or 0)
    nome_lineup = nomes_lineup.get(pid, "")
    if nome_lineup and len(normalizar_texto(nome_lineup)) > len(normalizar_texto(nome_stats)):
        return nome_lineup
    return nome_stats or nome_lineup


def _stat_int(player: dict, label: str) -> int:
    val = _stat_raw(player, label)
    if val is None:
        return 0
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0


def _stat_float(player: dict, *labels: str) -> float:
    for label in labels:
        val = _stat_raw(player, label)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def _stat_raw(player: dict, label: str):
    for block in player.get("stats", []):
        for title, data in block.get("stats", {}).items():
            if title == label:
                return data.get("stat", {}).get("value")
    return None


def _eventos_lineup(lineup: dict, nome: str) -> list[dict]:
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for grupo in ("starters", "subs", "unavailable"):
            for pl in team.get(grupo) or []:
                if pl.get("name") == nome:
                    return (pl.get("performance") or {}).get("events") or []
    return []


def _contar_shotmap(shotmap: list[dict]) -> tuple[int, int, int, int]:
    """Retorna FT, FD, FF, GC a partir do shotmap FotMob."""
    ft = fd = ff = gc = 0
    for chute in shotmap or []:
        tipo = chute.get("eventType", "")
        if chute.get("isOwnGoal"):
            gc += 1
        elif tipo == "Post":
            ft += 1
        elif tipo == "AttemptSaved":
            fd += 1
        elif tipo == "Miss":
            ff += 1
    return ft, fd, ff, gc


def _contar_cartoes(eventos: list[dict]) -> tuple[int, int]:
    ca = cv = 0
    for ev in eventos:
        tipo = ev.get("type", "")
        if tipo == "yellowCard":
            ca += 1
        elif tipo == "redCard":
            cv += 1
    return ca, cv


def extrair_scouts_jogador(
    player: dict,
    eventos: list[dict],
    bucket: Bucket,
    time_sofreu_gol: bool,
) -> ScoutsPartida:
    minutos = _stat_int(player, "Minutes played")
    ft_map, fd_map, ff_map, gc_map = _contar_shotmap(player.get("shotmap") or [])
    ca, cv = _contar_cartoes(eventos)

    ft_stat = _stat_int(player, "Hit woodwork")
    ff_stat = _stat_int(player, "Shots off target")

    scouts = ScoutsPartida(
        minutos=minutos,
        G=_stat_int(player, "Goals"),
        A=_stat_int(player, "Assists"),
        FT=max(ft_map, ft_stat),
        FD=fd_map,
        FF=max(ff_map, ff_stat),
        FS=_stat_int(player, "Was fouled"),
        I=_stat_int(player, "Offsides"),
        DS=_stat_int(player, "Tackles"),
        DE=_stat_int(player, "Saves"),
        GS=_stat_int(player, "Goals conceded"),
        FC=_stat_int(player, "Fouls committed"),
        GC=gc_map,
        CA=ca,
        CV=cv,
        INT=_stat_int(player, "Interceptions"),
        C=_stat_int(player, "Clearances"),
        BR=_stat_int(player, "Recoveries"),
        GE=_stat_float(player, "Goals prevented"),
        GCC=_stat_int(player, "Big chances created"),
    )

    if minutos > 0 and not time_sofreu_gol and bucket in {"GOL", "LAT", "ZAG"}:
        scouts.SG = 1

    return scouts


def processar_partida(
    match_id: str,
    caminho_mercado: Path,
    sigla_mandante: str,
    sigla_visitante: str,
) -> ResultadoPartida:
    md = _fetch_json(FOTMOB_MATCH_URL.format(match_id=match_id))
    content = md.get("content") or {}
    player_stats = content.get("playerStats") or {}
    lineup = content.get("lineup") or {}

    geral = md.get("general") or {}
    home = geral.get("homeTeam") or {}
    away = geral.get("awayTeam") or {}
    home_id = int(home.get("id", 0))
    away_id = int(away.get("id", 0))

    placar = _extrair_placar(md, home_id, away_id)
    gols_m = placar[home_id]
    gols_v = placar[away_id]

    siglas = {sigla_mandante, sigla_visitante}
    mercado_por_sigla = carregar_mercado_por_sigla(caminho_mercado, siglas)
    nomes_lineup = _mapa_nomes_lineup(lineup)
    usados_por_sigla: dict[str, set[int]] = {s: set() for s in siglas}

    jogadores: list[JogadorPartida] = []

    for player in player_stats.values():
        team_id = int(player.get("teamId", 0))
        if team_id == home_id:
            sigla = sigla_mandante
            gols_sofridos = gols_v
        elif team_id == away_id:
            sigla = sigla_visitante
            gols_sofridos = gols_m
        else:
            continue

        time_sofreu = gols_sofridos > 0

        minutos = _stat_int(player, "Minutes played")
        if minutos <= 0:
            continue

        nome_match = _nome_para_matching(player, nomes_lineup)
        mercado = associar_jogador_mercado(
            nome_match,
            mercado_por_sigla[sigla],
            is_goleiro=bool(player.get("isGoalkeeper")),
            excluir_ids=usados_por_sigla[sigla],
        )
        if mercado is None:
            continue

        atleta_id = int(mercado.get("atleta_id") or 0)
        if atleta_id:
            usados_por_sigla[sigla].add(atleta_id)

        bucket = mercado["bucket_posicao"]
        if bucket not in BUCKETS:
            continue

        eventos = _eventos_lineup(lineup, player["name"])
        scouts = extrair_scouts_jogador(player, eventos, bucket, time_sofreu)
        pontos = calcular_pontos(scouts, bucket)
        xg = _stat_float(player, "Expected goals (xG)", "xG")
        xa = _stat_float(player, "Expected assists (xA)", "xA")

        jogadores.append(
            JogadorPartida(
                fotmob_id=int(player["id"]),
                nome=player["name"],
                sigla=sigla,
                bucket=bucket,
                scouts=scouts,
                pontos=pontos,
                atleta_id=mercado.get("atleta_id"),
                xg=xg,
                xa=xa,
            )
        )

    return ResultadoPartida(
        match_id=match_id,
        sigla_mandante=sigla_mandante,
        sigla_visitante=sigla_visitante,
        gols_mandante=gols_m,
        gols_visitante=gols_v,
        jogadores=jogadores,
    )


def _extrair_placar(md: dict, home_id: int, away_id: int) -> dict[int, int]:
    header = md.get("header") or {}
    score_str = (header.get("status") or {}).get("scoreStr") or ""
    if "-" in score_str:
        partes = [p.strip() for p in score_str.split("-")]
        if len(partes) == 2:
            try:
                return {home_id: int(partes[0]), away_id: int(partes[1])}
            except ValueError:
                pass
    raise ValueError(f"Placar indisponível no matchDetails (home={home_id}, away={away_id})")


def agrupar_pontos_por_bucket(jogadores: list[JogadorPartida]) -> dict[str, dict[Bucket, list[float]]]:
    out: dict[str, dict[Bucket, list[float]]] = {}
    for j in jogadores:
        out.setdefault(j.sigla, {b: [] for b in BUCKETS})
        out[j.sigla][j.bucket].append(j.pontos)
    return out


def buscar_metricas_coletivas_time(fotmob_team_name: str) -> dict[str, float | None]:
    """Métricas de temporada WC a partir dos JSONs de stats FotMob (grupos + KO).

    Inclui ``J`` = MatchesPlayed reportado pelo FotMob (maior valor visto nos feeds).
    """
    campos = [
        "goals_team_match",
        "goals_conceded_team_match",
        "possession_percentage_team",
        "clean_sheet_team",
        "expected_goals_team",
        "expected_goals_conceded_team",
        "ontarget_scoring_att_team",
        "big_chance_team",
        "touches_in_opp_box_team",
        "total_tackle_team",
        "poss_won_att_3rd_team",
        "saves_team",
        "fk_foul_lost_team",
        "total_yel_card_team",
        "total_red_card_team",
    ]
    metricas: dict[str, float | None] = {c: None for c in campos}
    matches_played = 0

    for campo in campos:
        url = f"{SEASON_STATS_BASE}/{campo}.json"
        payload = _fetch_json(url)
        for row in payload.get("TopLists", [{}])[0].get("StatList", []):
            nome = row.get("TeamName") or row.get("ParticipantName")
            if nome != fotmob_team_name:
                continue
            metricas[campo] = float(row.get("StatValue", 0))
            try:
                mp = int(row.get("MatchesPlayed") or 0)
            except (TypeError, ValueError):
                mp = 0
            if mp > matches_played:
                matches_played = mp
            break

    if matches_played > 0:
        metricas["J"] = float(matches_played)
    return metricas
