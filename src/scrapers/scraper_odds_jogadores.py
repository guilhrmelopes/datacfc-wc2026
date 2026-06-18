"""
Scraper de odds de jogadores — hub.oddsnotifier.io × Cartola WC 2026.

Arquitetura:
  • Janela: hoje (America/Sao_Paulo) + 7 dias — calendário grupos_wc2026.json
  • Armazenamento por evento: odds_eventos_armazenados.json
  • Compilação: odds_jogadores.json (confronto atual por seleção)
  • Hub: international-fifa-world-cup (+ fallback international-world-cup)

Mercados: PTSOA (G/A/GA), Anytime Goalscorer, Team Total (SG%).
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Page

from scrapers.captura_odds_api import (
    extrair_odds_de_payload,
    extrair_sg_de_payload,
    payload_para_texto,
)
from utils.interceptacao_rede_oddsnotifier import ArmazenamentoCapturaOdds
from scrapers.mapeamento_odds import registrar_alias_aprendido
from scrapers.matching_cartola import (
    MIN_SCORE_ATRIBUICAO,
    MIN_SCORE_LACUNA,
    atribuir_nomes_a_jogadores,
    limpar_nome_fonte,
    melhor_jogador_para_nome,
)
from scrapers.mapeamento_selecoes_odds import chave_confronto as _chave_confronto
from scrapers.mapeamento_selecoes_odds import normalizar_selecao as _mapear_selecao
from scrapers.resolucao_eventos_odds import (
    construir_indice_eventos,
    mapear_fixtures,
    salvar_cache_eventos as _salvar_cache_eventos_resolucao,
    varredura_ids_playwright,
)
from scrapers.odds_armazenamento import (
    carregar_armazenamento,
    compilar_dashboard,
    confrontos_na_janela,
    enriquecer_confronto,
    expurgar_passados,
    janela_dias,
    mapa_sigla_por_selecao,
    montar_registro_evento,
    referencia_hoje,
    salvar_armazenamento,
)

# ─────────────────────────────────── Logging ─────────────────────────────────

import os
import sys

# Força UTF-8 na saída do terminal (Windows cp1252 incompatível com alguns chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────── Caminhos ─────────────────────────────────

_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "src"))
from pipeline.timestamp_dashboard import marcar_dashboard_atualizado  # noqa: E402

CAMINHO_MERCADO: Path = _RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_GRUPOS:  Path = _RAIZ / "frontend" / "public" / "data" / "grupos_wc2026.json"
CAMINHO_EVENTOS: Path = _RAIZ / "frontend" / "public" / "data" / "eventos_odds_rodada1.json"
CAMINHO_ESTADO:  Path = _RAIZ / "frontend" / "public" / "data" / "copa_estado.json"
CAMINHO_SAIDA:   Path = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"

MIN_JOGADORES_SALVAR = 500

POSICOES_LINHA: frozenset[int] = frozenset({2, 3, 4, 5})
POSICOES_SG: frozenset[int] = frozenset({1, 2, 3})  # GOL, LAT, ZAG

MERCADO_PLAYER_PAI = "Player To Score or Assist"
MERCADO_ANYTIME_GOALSCORER = "Anytime Goalscorer"

MERCADOS_RSC: dict[str, str] = {
    "Player To Score or Assist": "ga",  # fallback se label sem sufixo
    "Anytime Goalscorer": "g",
    "Player To Score": "g",
    "Player To Assist": "a",
}

# Sub-filtros dentro de Player To Score or Assist (hub: Score / Assist / Score Or Assist)
MERCADOS_PLAYER_SUB_UI: list[tuple[str, str]] = [
    ("Score", "g"),
    ("Assist", "a"),
    ("Score Or Assist", "ga"),
]

# Legado — não usar como mercados de topo; mantido só para compatibilidade interna
MERCADOS_PLAYER_UI: list[tuple[str, str]] = MERCADOS_PLAYER_SUB_UI

MKT_TEAM_TOTAL_HOME = "Team Total Home"
MKT_TEAM_TOTAL_AWAY = "Team Total Away"
HDP_CLEAN_SHEET = 0.5

# Nomes de mercados conhecidos (para não confundir com nomes de bookmakers)
NOMES_MERCADOS_CONHECIDOS: frozenset[str] = frozenset({
    "ML", "Moneyline", "1x2", "Spread", "Totals", "Totals HT", "Spread HT",
    "Team Total Home", "Team Total Away", "Team Total Home HT", "Team Total Away HT",
    "Corners Totals", "Corners Spread", "Corners Totals HT", "Corners Spread HT",
    "Bookings Totals", "Bookings Spread", "Cards Totals", "Cards Spread",
    "Player Shots", "Player Shots on Target", "Player Tackles", "Player To Be Fouled",
    "Player To Score or Assist", "Anytime Goalscorer", "Player To Assist",
    "First Goalscorer", "Last Goalscorer", "First Assist",
    "Asian Handicap", "Draw No Bet",
})

# Bookmakers tier 1 (menor margem)
BOOKMAKERS_T1: list[str] = ["pinnacle", "betfair exchange", "betfair", "1xbet"]
BOOKMAKERS_T2: list[str] = ["bet365", "betano", "unibet", "william hill", "bwin",
                             "betway", "888sport", "betclic", "kambi", "ladbrokes",
                             "leovegas", "betmgm", "sisal", "paddy power"]

MAX_EVENTOS: int = int(os.environ.get("ODDS_MAX_EVENTOS", "40"))
RODADA_ALVO: int = int(os.environ.get("ODDS_RODADA", "1"))
_RODADA_ATUAL: int = RODADA_ALVO
IS_CI: bool = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
CI_WAIT_MULT: float = float(os.environ.get("ODDS_CI_WAIT_MULT", "2.0" if IS_CI else "1.0"))
TIMEOUT_PAGINA: int = int(os.environ.get("ODDS_TIMEOUT_MS", "55000" if IS_CI else "35000"))
ODDS_MERGE: bool = os.environ.get("ODDS_MERGE", "1").strip().lower() not in ("0", "false", "no", "off")

DELAY_MIN: float = float(os.environ.get("ODDS_DELAY_MIN", "14" if IS_CI else "12"))
DELAY_MAX: float = float(os.environ.get("ODDS_DELAY_MAX", "24" if IS_CI else "22"))

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
"""


def _wait_ms(base_ms: int) -> int:
    return int(base_ms * CI_WAIT_MULT)

# Threshold legado — matching em matching_cartola.py
THRESHOLD_AUTO:   int = 85
THRESHOLD_REVIEW: int = MIN_SCORE_ATRIBUICAO

# Mapa oddsnotifier → seleção Cartola: ver mapeamento_selecoes_odds.py

# Faixa de IDs oddsnotifier para descoberta automática (somente com ODDS_ALLOW_ID_SCAN=1)
ODDS_ID_SCAN_MIN: int = int(os.environ.get("ODDS_ID_SCAN_MIN", "66456900"))
ODDS_ID_SCAN_MAX: int = int(os.environ.get("ODDS_ID_SCAN_MAX", "66458500"))

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# ══════════════════════════════════════════════════════════════════════════════
# [0] EVENTOS — fixtures WC2026 + mapeamento oddsEventId
# ══════════════════════════════════════════════════════════════════════════════

URL_WC2026 = "https://hub.oddsnotifier.io/world-cup-2026"
URL_HUB_FIFA = "https://hub.oddsnotifier.io/football/international-fifa-world-cup"
URLS_API_EVENTOS = (
    "https://hub.oddsnotifier.io/api/events/football/international-fifa-world-cup",
    "https://hub.oddsnotifier.io/api/events/football/international-world-cup",
)


def _url_evento(event_id: int) -> str:
    return f"{URL_HUB_FIFA}/{event_id}"


def _extrair_json_array(rsc: str, chave: str) -> list | None:
    """Extrai array JSON após '"chave":[' via balanceamento de colchetes."""
    m = re.search(rf'"{re.escape(chave)}"\s*:\s*\[', rsc)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for i in range(start, len(rsc)):
        if rsc[i] == "[":
            depth += 1
        elif rsc[i] == "]":
            depth -= 1
            if depth == 0:
                raw = rsc[start:i + 1]
                raw = re.sub(r'"oddsEventId"\s*:\s*"\$undefined"', "null", raw)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
    return None


def _extrair_json_object(rsc: str, chave: str) -> dict | None:
    """Extrai objeto JSON após '"chave":{' via balanceamento de chaves."""
    m = re.search(rf'"{re.escape(chave)}"\s*:\s*\{{', rsc)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    for i in range(start, len(rsc)):
        if rsc[i] == "{":
            depth += 1
        elif rsc[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(rsc[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _nome_evento_pagina(pagina: Page, event_id: int) -> str | None:
    """Lê 'Home vs Away' do título ou JSON-LD da página do evento."""
    url = _url_evento(event_id)
    try:
        pagina.goto(url, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
        pagina.wait_for_timeout(1200)
        titulo = pagina.title()
        m = re.search(r"^(.+?) Odds \|", titulo)
        if m and " vs " in m.group(1):
            return m.group(1).strip()
        ld = pagina.evaluate("""() => {
            for (const s of document.querySelectorAll('script[type=\"application/ld+json\"]')) {
                try {
                    const j = JSON.parse(s.textContent);
                    const items = Array.isArray(j) ? j : [j];
                    for (const item of items) {
                        if (item['@type'] === 'SportsEvent' && item.name) return item.name;
                    }
                } catch (_) {}
            }
            return null;
        }""")
        if ld and " vs " in ld:
            return ld.strip()
    except Exception as e:
        logger.debug("Falha ao ler evento %d: %s", event_id, e)
    return None


def _times_do_nome_evento(nome: str) -> tuple[str, str] | None:
    if " vs " not in nome:
        return None
    home, away = nome.split(" vs ", 1)
    return home.strip(), away.strip()


def _chave_confronto(home: str, away: str) -> tuple[str, str]:
    return (_mapear_selecao(home.upper()), _mapear_selecao(away.upper()))


def _rodada_efetiva() -> int:
    env = os.environ.get("ODDS_RODADA", "").strip()
    if env.isdigit():
        return int(env)
    if CAMINHO_ESTADO.is_file():
        try:
            estado = json.loads(CAMINHO_ESTADO.read_text(encoding="utf-8"))
            rodada = int(estado.get("rodada_cartola_atual") or 0)
            if rodada > 0:
                return rodada
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return RODADA_ALVO


def _mapas_sigla(jogadores: list[dict]) -> dict[str, str]:
    """Seleção Cartola (upper) → sigla."""
    out: dict[str, str] = {}
    for j in jogadores:
        sel = (j.get("selecao") or "").upper()
        sig = (j.get("sigla") or "").upper()
        if sel and sig:
            out[sel] = sig
    return out


def _confrontos_proximo_adversario(jogadores: list[dict]) -> list[dict]:
    """Calendário: partidas cujo ADV bate com proximo_adversario_sigla (jogadores que já atuaram)."""
    if not CAMINHO_GRUPOS.exists():
        return []
    with CAMINHO_GRUPOS.open(encoding="utf-8") as f:
        dados = json.load(f)
    confrontos = dados.get("confrontos") or []
    selecao_sigla = _mapas_sigla(jogadores)

    pares: set[tuple[str, str]] = set()
    for j in jogadores:
        if int(j.get("copa_jogos_num") or 0) <= 0:
            continue
        adv = (j.get("proximo_adversario_sigla") or "").upper()
        sig = (j.get("sigla") or "").upper()
        if adv and sig:
            pares.add(tuple(sorted((sig, adv))))

    if not pares:
        return []

    resultado: list[dict] = []
    for c in confrontos:
        if c.get("finalizada"):
            continue
        sig_m = selecao_sigla.get((c.get("mandante") or "").upper())
        sig_v = selecao_sigla.get((c.get("visitante") or "").upper())
        if not sig_m or not sig_v:
            continue
        if tuple(sorted((sig_m, sig_v))) in pares:
            resultado.append(c)
    return resultado


def _fixtures_de_confrontos(confrontos: list[dict]) -> list[dict]:
    fixtures: list[dict] = []
    for c in confrontos:
        fixtures.append({
            "fixture_id": c.get("match_id"),
            "match_id": c.get("match_id"),
            "home": c.get("mandante", ""),
            "away": c.get("visitante", ""),
            "date": c.get("utc") or c.get("data", ""),
            "grupo": c.get("grupo", ""),
        })
    return fixtures


def _adversario_sigla_jogador(
    jogador: dict,
    sel_home: str,
    sel_away: str,
    selecao_sigla: dict[str, str],
) -> str | None:
    time = (jogador.get("selecao") or "").upper()
    if time == sel_home:
        return selecao_sigla.get(sel_away)
    if time == sel_away:
        return selecao_sigla.get(sel_home)
    return None


def _deve_atualizar_odds(jogador: dict, adversario_sigla: str | None) -> bool:
    """
    Só sobrescreve odds se o evento corresponde ao ADV do jogador no mercado.
    Quem ainda não estreou mantém odds da rodada atual; quem já jogou só atualiza
    quando o confronto raspado é o próximo adversário.
    """
    prox = (jogador.get("proximo_adversario_sigla") or "").upper()
    adv = (adversario_sigla or "").upper()
    if not prox:
        return True
    if not adv:
        return False
    return prox == adv


def _rodada_odds_alvo(jogadores: list[dict]) -> int:
    """Rodada a raspar por completo quando há jogadores aguardando próximo jogo."""
    confrontos_prox = _confrontos_proximo_adversario(jogadores)
    if confrontos_prox:
        return max(int(c.get("rodada") or 1) for c in confrontos_prox)
    return _rodada_efetiva()


def buscar_eventos_rodada_completa(
    pagina: Page,
    rodada: int,
    rsc_wc2026: str = "",
) -> list[dict]:
    """Todos os confrontos de uma rodada no OddsNotifier."""
    fixtures_rsc = _fixtures_rodada_do_rsc(rsc_wc2026, rodada) if rsc_wc2026 else []
    if fixtures_rsc:
        fixtures = fixtures_rsc
    else:
        fixtures = _fixtures_de_confrontos(_carregar_confrontos_rodada(rodada))
    if not fixtures:
        logger.warning("Nenhum fixture calendario para rodada %d.", rodada)
        return []
    cache = _carregar_cache_eventos()
    eventos = _mapear_ids_eventos(pagina, fixtures, cache, rsc_wc2026)
    logger.info(
        "Rodada %d completa: %d eventos mapeados (%d no calendario)",
        rodada,
        len(eventos),
        len(fixtures),
    )
    return eventos


def buscar_eventos_proximo_adversario(
    pagina: Page,
    jogadores: list[dict],
    rsc_wc2026: str = "",
) -> list[dict]:
    confrontos = _confrontos_proximo_adversario(jogadores)
    if not confrontos:
        return []

    cache = _carregar_cache_eventos()
    eventos: list[dict] = []
    rodadas = sorted({int(c["rodada"]) for c in confrontos if c.get("rodada")})

    for rodada in rodadas:
        chaves = {
            _chave_confronto(c["mandante"], c["visitante"])
            for c in confrontos
            if int(c.get("rodada") or 0) == rodada
        }
        fixtures_rsc = _fixtures_rodada_do_rsc(rsc_wc2026, rodada) if rsc_wc2026 else []
        fixtures = [
            f for f in fixtures_rsc
            if _chave_confronto(f["home"], f["away"]) in chaves
        ]
        if not fixtures:
            fixtures = _fixtures_de_confrontos([
                c for c in confrontos if int(c.get("rodada") or 0) == rodada
            ])
        if fixtures:
            eventos.extend(_mapear_ids_eventos(pagina, fixtures, cache, rsc_wc2026))

    if eventos:
        logger.info(
            "Eventos proximo adversario: %d partidas (%d no calendario)",
            len(eventos),
            len(confrontos),
        )
    return eventos


def buscar_eventos_janela(
    pagina: Page,
    confrontos: list[dict],
    selecao_sigla: dict[str, str],
    rsc_wc2026: str = "",
) -> list[dict]:
    """Mapeia confrontos do calendário (janela de datas) → oddsEventId no hub."""
    if not confrontos:
        return []

    enriquecidos = [enriquecer_confronto(c, selecao_sigla) for c in confrontos]
    por_chave = {
        _chave_confronto(c["mandante"], c["visitante"]): c
        for c in enriquecidos
    }
    fixtures = _fixtures_de_confrontos(enriquecidos)
    cache = _carregar_cache_eventos()
    mapeados = _mapear_ids_eventos(pagina, fixtures, cache, rsc_wc2026)

    eventos: list[dict] = []
    for ev in mapeados:
        chave = _chave_confronto(ev.get("home", ""), ev.get("away", ""))
        conf = por_chave.get(chave)
        if not conf:
            continue
        eventos.append({
            **ev,
            "data": conf.get("data") or ev.get("date", ""),
            "hora": conf.get("hora", ""),
            "rodada": conf.get("rodada"),
            "grupo": conf.get("grupo", ""),
            "confronto": conf,
        })

    logger.info(
        "Janela calendario: %d confrontos -> %d eventos mapeados.",
        len(confrontos),
        len(eventos),
    )
    return eventos[:MAX_EVENTOS]


def _carregar_confrontos_rodada(rodada: int) -> list[dict]:
    if not CAMINHO_GRUPOS.exists():
        logger.error("grupos_wc2026.json nao encontrado")
        return []
    with CAMINHO_GRUPOS.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [c for c in dados.get("confrontos", []) if c.get("rodada") == rodada]


def _fixtures_rodada_do_rsc(rsc: str, rodada: int) -> list[dict]:
    confrontos = _carregar_confrontos_rodada(rodada)
    chaves = {_chave_confronto(c["mandante"], c["visitante"]) for c in confrontos}
    resultado: list[dict] = []

    for ev in _extrair_fixtures_odds_do_rsc(rsc):
        if _chave_confronto(ev["home"], ev["away"]) not in chaves:
            continue
        resultado.append({**ev, "grupo": ""})

    if resultado:
        return resultado

    fixtures = _extrair_json_array(rsc, "fixtures")
    if not fixtures:
        return []
    for fx in fixtures:
        if not isinstance(fx, dict):
            continue
        home, away = fx.get("home", ""), fx.get("away", "")
        if _chave_confronto(home, away) not in chaves:
            continue
        odds_event_id = fx.get("oddsEventId")
        eid: int | None = None
        if odds_event_id not in (None, "null", "$undefined", ""):
            try:
                eid = int(odds_event_id)
            except (TypeError, ValueError):
                eid = None
        resultado.append({
            "fixture_id": fx.get("id"),
            "home": home,
            "away": away,
            "date": fx.get("date", ""),
            "grupo": fx.get("group", ""),
            "id": eid,
        })
    return resultado


_PAT_FIXTURE_ODDS = re.compile(
    r'"id"\s*:\s*(\d+)\s*,\s*"oddsEventId"\s*:\s*(\d+)\s*,\s*"home"\s*:\s*"([^"]+)"\s*,\s*"away"\s*:\s*"([^"]+)"'
)


def _extrair_fixtures_odds_do_rsc(rsc: str) -> list[dict]:
    """Parseia blocos fixture com oddsEventId embutidos no RSC (world-cup-2026)."""
    eventos: list[dict] = []
    vistos: set[int] = set()
    for match in _PAT_FIXTURE_ODDS.finditer(rsc):
        fixture_id, eid, home, away = match.groups()
        eid_int = int(eid)
        if eid_int in vistos:
            continue
        vistos.add(eid_int)
        eventos.append({
            "id": eid_int,
            "home": home,
            "away": away,
            "fixture_id": int(fixture_id),
            "date": "",
        })
    if eventos:
        logger.info("Fixtures com oddsEventId no RSC: %d.", len(eventos))
    return eventos


def _cache_eventos_do_rsc(rsc: str) -> dict[tuple[str, str], int]:
    """Extrai oddsEventId embutido nos fixtures do RSC (world-cup-2026)."""
    cache: dict[tuple[str, str], int] = {}

    for ev in _extrair_fixtures_odds_do_rsc(rsc):
        cache[_chave_confronto(ev["home"], ev["away"])] = int(ev["id"])

    fixtures = _extrair_json_array(rsc, "fixtures")
    if fixtures:
        for fx in fixtures:
            if not isinstance(fx, dict):
                continue
            odds_event_id = fx.get("oddsEventId")
            if odds_event_id in (None, "null", "$undefined", ""):
                continue
            try:
                eid = int(odds_event_id)
            except (TypeError, ValueError):
                continue
            home, away = fx.get("home", ""), fx.get("away", "")
            if not home or not away:
                continue
            cache[_chave_confronto(home, away)] = eid

    if cache:
        logger.info("Cache via RSC fixtures: %d eventos.", len(cache))
    return cache


def _carregar_eventos_arquivo() -> list[dict]:
    """Lista versionada de eventos da rodada (fonte primária no CI)."""
    if not CAMINHO_EVENTOS.exists():
        return []
    try:
        with CAMINHO_EVENTOS.open(encoding="utf-8") as f:
            bruto = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    arquivo_rodada = int(bruto.get("rodada") or _RODADA_ATUAL)
    if arquivo_rodada != _RODADA_ATUAL:
        return []

    eventos: list[dict] = []
    for ev in bruto.get("eventos", []):
        if not isinstance(ev, dict) or "id" not in ev:
            continue
        eventos.append({
            "id": int(ev["id"]),
            "home": ev.get("home", ""),
            "away": ev.get("away", ""),
            "date": ev.get("date", ""),
            "fixture_id": ev.get("fixture_id"),
        })
    eventos.sort(key=lambda e: e.get("date", str(e["id"])))
    return eventos[:MAX_EVENTOS]


def _carregar_odds_existentes() -> dict[str, dict]:
    if not CAMINHO_SAIDA.is_file():
        return {}
    try:
        with CAMINHO_SAIDA.open(encoding="utf-8") as f:
            bruto = json.load(f)
        odds = bruto.get("odds", {})
        return {str(k): v for k, v in odds.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _purge_evento_odds(resultado: dict[str, dict], eid: int) -> None:
    for aid in [k for k, v in resultado.items() if v.get("event_id") == eid]:
        del resultado[aid]


def _eventos_da_api_bruta() -> list[dict]:
    """Lista eventos WC2026 via API pública (fifa-world-cup → fallback world-cup)."""
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
                    logger.info("API eventos (%s): %d fixtures.", url_api.rsplit("/", 1)[-1], len(lista))
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


def _normalizar_evento_api(ev: dict) -> dict | None:
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
        "fixture_id": ev.get("fixture_id") or ev.get("fixtureId"),
    }


def _cache_eventos_da_api() -> dict[tuple[str, str], int]:
    """Índice home×away → oddsEventId via API (evita varredura lenta por ID)."""
    cache: dict[tuple[str, str], int] = {}
    for bruto in _eventos_da_api_bruta():
        ev = _normalizar_evento_api(bruto)
        if not ev:
            continue
        chave = _chave_confronto(ev["home"], ev["away"])
        cache[chave] = int(ev["id"])
    if cache:
        logger.info("Cache via API: %d eventos mapeados.", len(cache))
    return cache


def _carregar_cache_eventos() -> dict[tuple[str, str], int]:
    por_confronto, _ = construir_indice_eventos()
    return por_confronto


def _mapear_ids_eventos(
    pagina: Page,
    fixtures: list[dict],
    cache: dict[tuple[str, str], int],
    rsc: str = "",
) -> list[dict]:
    """
    Associa cada fixture ao oddsEventId via API + cache (sem varredura por padrão).
    """
    if rsc:
        cache = {**cache, **_cache_eventos_do_rsc(rsc)}

    por_confronto, por_fixture = construir_indice_eventos()
    por_confronto = {**por_confronto, **cache}

    mapeados, faltando = mapear_fixtures(fixtures, por_confronto, por_fixture)

    if faltando:
        novos = varredura_ids_playwright(
            pagina,
            faltando,
            por_confronto,
            nome_evento_fn=_nome_evento_pagina,
            times_do_nome_fn=_times_do_nome_evento,
            url_evento_fn=_url_evento,
            timeout_ms=TIMEOUT_PAGINA,
        )
        por_confronto.update(novos)
        remapeados, ainda_faltando = mapear_fixtures(faltando, por_confronto, por_fixture)
        mapeados.extend(remapeados)
        for fx in ainda_faltando:
            logger.warning("Sem oddsEventId: %s vs %s", fx.get("home"), fx.get("away"))

    mapeados.sort(key=lambda e: e.get("date", ""))
    if mapeados:
        _salvar_cache_eventos_resolucao(
            [
                {
                    "id": e["id"],
                    "home": e.get("home", ""),
                    "away": e.get("away", ""),
                    "date": e.get("date", ""),
                    "fixture_id": e.get("fixture_id"),
                }
                for e in mapeados
            ],
            _RODADA_ATUAL,
        )
    return mapeados[:MAX_EVENTOS]


def buscar_eventos(pagina: Page, rsc_wc2026: str = "") -> list[dict]:
    """
    Fonte primária: eventos_odds_rodada1.json (confiável no CI).
    Fallback: fixtures world-cup-2026 + cache de IDs.
    """
    eventos_arquivo = _carregar_eventos_arquivo()
    if len(eventos_arquivo) >= min(MAX_EVENTOS, 20):
        logger.info("Eventos via arquivo versionado: %d partidas", len(eventos_arquivo))
        return eventos_arquivo

    fixtures = _fixtures_rodada_do_rsc(rsc_wc2026, _RODADA_ATUAL) if rsc_wc2026 else []
    cache = _carregar_cache_eventos()

    if fixtures:
        logger.info("Fixtures rodada %d no RSC: %d jogos", _RODADA_ATUAL, len(fixtures))
        eventos = _mapear_ids_eventos(pagina, fixtures, cache, rsc_wc2026)
        if eventos:
            return eventos

    if eventos_arquivo:
        logger.info("Eventos via arquivo (parcial): %d partidas", len(eventos_arquivo))
        return eventos_arquivo

    if cache:
        confrontos = _carregar_confrontos_rodada(_RODADA_ATUAL)
        chaves = {(c["mandante"], c["visitante"]) for c in confrontos}
        eventos = []
        for ev in _carregar_eventos_arquivo() or []:
            chave = _chave_confronto(ev.get("home", ""), ev.get("away", ""))
            if chave in chaves:
                eventos.append(ev)
        if not eventos:
            for chave, eid in cache.items():
                if chave in chaves:
                    eventos.append({
                        "id": eid,
                        "home": chave[0],
                        "away": chave[1],
                        "date": "",
                    })
        if eventos:
            logger.info("Eventos via cache: %d partidas", len(eventos))
            return sorted(eventos, key=lambda e: e.get("date", str(e["id"])))[:MAX_EVENTOS]

    logger.error("Nenhum evento encontrado para rodada %d.", _RODADA_ATUAL)
    return []


# ══════════════════════════════════════════════════════════════════════════════
# [1] BANCO DE JOGADORES
# ══════════════════════════════════════════════════════════════════════════════


def _norm(texto: str) -> str:
    forma = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in forma if not unicodedata.combining(c)).lower().strip()


def carregar_jogadores(caminho: Path) -> list[dict]:
    """Jogadores de linha (ZAG/LAT/MEI/ATA) — usados no matching GA."""
    if not caminho.exists():
        logger.error("jogadores_mercado.json nao encontrado: %s", caminho)
        return []
    with caminho.open(encoding="utf-8") as f:
        dados: list[dict] = json.load(f)
    linha = [j for j in dados if j.get("posicao_id") in POSICOES_LINHA]
    logger.info("Banco: %d total, %d de linha", len(dados), len(linha))
    return linha


def carregar_todos_jogadores(caminho: Path) -> list[dict]:
    """Elenco completo (inclui GOL) — usado para SG em defensores."""
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def pool_defensores(jogadores: list[dict], selecao_upper: str) -> list[dict]:
    return [
        j for j in jogadores
        if j.get("selecao", "").upper() == selecao_upper
        and j.get("posicao_id") in POSICOES_SG
    ]


def jogadores_da_equipe(jogadores: list[dict], selecao_upper: str) -> list[dict]:
    return [j for j in jogadores if j.get("selecao", "").upper() == selecao_upper]


# ══════════════════════════════════════════════════════════════════════════════
# [2] PARSER RSC
# ══════════════════════════════════════════════════════════════════════════════

_PAT_LABEL_OVER = re.compile(
    r'"label"\s*:\s*"([^"]+)"\s*,\s*"hdp"\s*:\s*[0-9.]+\s*,\s*"over"\s*:\s*"([0-9.]+)"'
)
_PAT_MARKET_BLOCK = re.compile(
    r'"name"\s*:\s*"([^"]{2,80})"\s*,\s*"updatedAt"\s*:\s*"[^"]+"\s*,\s*"odds"\s*:\s*(\[[^\]]{10,}?\])',
    re.DOTALL,
)


def _bookmaker_tier(nome: str) -> int:
    n = _norm(nome)
    if any(t in n for t in BOOKMAKERS_T1):
        return 1
    if any(t in n for t in BOOKMAKERS_T2):
        return 2
    return 3


def _melhor_odd(
    atual: tuple[float, str] | None,
    nova_odd: float,
    nova_bk: str,
) -> tuple[float, str]:
    """Prefere maior odd; empate favorece bookmaker tier menor."""
    if atual is None:
        return nova_odd, nova_bk
    if nova_odd > atual[0] + 0.001:
        return nova_odd, nova_bk
    if abs(nova_odd - atual[0]) <= 0.001 and _bookmaker_tier(nova_bk) < _bookmaker_tier(atual[1]):
        return nova_odd, nova_bk
    return atual


_PAT_LABEL_PTSOA = re.compile(
    r"^(.+?)\s*\((Score\s+[Oo]r\s+[Aa]ssist|Score|Assist)\)\s*(?:\(\d+\))?\s*$",
    re.IGNORECASE,
)


def _classificar_label_ptsoa(label: str) -> tuple[str, str] | None:
    """
    Player To Score or Assist no hub usa labels como:
      'Patrik Schick (Score) (1)' -> g
      'Patrik Schick (Assist) (2)' -> a
      'Patrik Schick (Score Or Assist) (1)' -> ga
    """
    bruto = (label or "").strip()
    if not bruto:
        return None
    m = _PAT_LABEL_PTSOA.match(bruto)
    if not m:
        return None
    nome = m.group(1).strip()
    tipo = m.group(2).lower().replace("  ", " ")
    if "or assist" in tipo:
        return nome, "ga"
    if tipo == "assist":
        return nome, "a"
    if tipo == "score":
        return nome, "g"
    return None


def _registrar_odd_jogador(
    resultado: dict[str, dict[str, tuple[float, str]]],
    sufixo: str,
    nome: str,
    odds_val: float,
    bk_name: str,
) -> None:
    resultado[sufixo][nome] = _melhor_odd(
        resultado[sufixo].get(nome), odds_val, bk_name,
    )


def extrair_odds_rsc(
    rsc_conteudo: str,
    sufixo_alvo: str | None = None,
) -> dict[str, dict[str, tuple[float, str]]]:
    """
    Parseia o bloco "bookmakers" no RSC.
    sufixo_alvo: se informado (g/a/ga), ignora labels de outros mercados.
    """
    resultado: dict[str, dict[str, tuple[float, str]]] = {"g": {}, "a": {}, "ga": {}}
    bookmakers = _extrair_json_object(rsc_conteudo, "bookmakers")
    if not bookmakers:
        logger.debug("Bloco bookmakers nao encontrado — fallback regex.")
        legado = _extrair_odds_rsc_regex(rsc_conteudo, sufixo_alvo=sufixo_alvo)
        for mercado in ("g", "a", "ga"):
            if sufixo_alvo and mercado != sufixo_alvo:
                continue
            for nome, par in legado.get(mercado, {}).items():
                _registrar_odd_jogador(resultado, mercado, nome, par[0], par[1])
        return resultado

    for bk_name, mercados in bookmakers.items():
        if not isinstance(mercados, list):
            continue
        for mercado in mercados:
            if not isinstance(mercado, dict):
                continue
            nome_mercado = mercado.get("name", "")

            for item in mercado.get("odds") or []:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                over = item.get("over")
                if not label or over is None:
                    continue
                try:
                    odds_val = float(over)
                except (TypeError, ValueError):
                    continue
                if odds_val <= 1.0:
                    continue

                if nome_mercado == MERCADO_PLAYER_PAI:
                    classificado = _classificar_label_ptsoa(str(label))
                    if classificado:
                        nome_jog, sufixo = classificado
                        if sufixo_alvo and sufixo != sufixo_alvo:
                            continue
                        _registrar_odd_jogador(
                            resultado, sufixo, nome_jog, odds_val, str(bk_name),
                        )
                        continue
                    if sufixo_alvo and sufixo_alvo != "ga":
                        continue
                    sufixo = "ga"
                    chave = str(label)
                else:
                    sufixo = MERCADOS_RSC.get(nome_mercado)
                    if sufixo is None:
                        continue
                    chave = str(label)

                _registrar_odd_jogador(
                    resultado, sufixo, chave, odds_val, str(bk_name),
                )

    logger.info(
        "RSC parseado: %d marcar | %d assistir | %d marcar ou assistir",
        len(resultado["g"]),
        len(resultado["a"]),
        len(resultado["ga"]),
    )
    return resultado


def _parse_odd_under(val: Any) -> float | None:
    if val is None or val in ("N/A", "-", ""):
        return None
    try:
        odd = float(val)
    except (TypeError, ValueError):
        return None
    return odd if odd > 1.0 else None


def extrair_sg_times(rsc_conteudo: str) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    """
    Probabilidade de clean sheet por time via Team Total Under 0.5:
      • mandante não sofre  → Team Total Away under 0.5
      • visitante não sofre → Team Total Home under 0.5
    Retorna (sg_home, sg_away) como (odd_decimal, bookmaker).
    """
    bookmakers = _extrair_json_object(rsc_conteudo, "bookmakers")
    if not bookmakers:
        return None, None

    sg_home: tuple[float, str] | None = None
    sg_away: tuple[float, str] | None = None

    for bk_name, mercados in bookmakers.items():
        if not isinstance(mercados, list):
            continue
        for mercado in mercados:
            if not isinstance(mercado, dict):
                continue
            nome = mercado.get("name")
            if nome not in (MKT_TEAM_TOTAL_HOME, MKT_TEAM_TOTAL_AWAY):
                continue
            for item in mercado.get("odds") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("hdp") != HDP_CLEAN_SHEET:
                    continue
                odd_under = _parse_odd_under(item.get("under"))
                if odd_under is None:
                    continue
                if nome == MKT_TEAM_TOTAL_AWAY:
                    sg_home = _melhor_odd(sg_home, odd_under, str(bk_name))
                else:
                    sg_away = _melhor_odd(sg_away, odd_under, str(bk_name))

    if sg_home or sg_away:
        logger.info(
            "SG parseado: home=%s away=%s",
            f"{sg_home[0]:.2f}@{sg_home[1]}" if sg_home else "—",
            f"{sg_away[0]:.2f}@{sg_away[1]}" if sg_away else "—",
        )
    return sg_home, sg_away


def _aplicar_sg_evento(
    resultado: dict[str, dict],
    eid: int,
    pool_home: list[dict],
    pool_away: list[dict],
    sg_home: tuple[float, str] | None,
    sg_away: tuple[float, str] | None,
    sel_home: str,
    sel_away: str,
    selecao_sigla: dict[str, str],
    *,
    modo_armazenamento: bool = False,
    rodada_evento: int | None = None,
) -> int:
    """Preenche sg_pct para GOL/LAT/ZAG de cada equipe (probabilidade do time)."""
    aplicados = 0
    for pool, sg_data in ((pool_home, sg_home), (pool_away, sg_away)):
        if not sg_data or not pool:
            continue
        odd, bk = sg_data
        for jog in pool:
            if jog.get("posicao_id") not in POSICOES_SG:
                continue
            adv = _adversario_sigla_jogador(jog, sel_home, sel_away, selecao_sigla)
            if not modo_armazenamento and not _deve_atualizar_odds(jog, adv):
                continue
            aid = str(jog["atleta_id"])
            if aid not in resultado:
                resultado[aid] = {"event_id": eid}
            else:
                resultado[aid]["event_id"] = eid
            resultado[aid]["sg_pct"] = _prob(odd)
            resultado[aid]["casa_sg"] = bk
            resultado[aid]["odds_sg"] = odd
            adv_final = adv if modo_armazenamento else _adv_para_entrada(jog, adv)
            if adv_final:
                resultado[aid]["adversario_sigla"] = adv_final
            rodada_gravar = rodada_evento if rodada_evento is not None else _RODADA_ATUAL
            resultado[aid]["rodada"] = rodada_gravar
            aplicados += 1
    return aplicados


def _extrair_odds_rsc_regex(
    rsc_conteudo: str,
    sufixo_alvo: str | None = None,
) -> dict[str, dict[str, tuple[float, str]]]:
    """Fallback legado quando bookmakers JSON não está disponível."""
    resultado: dict[str, dict[str, tuple[float, str]]] = {"g": {}, "a": {}, "ga": {}}
    mercados_regex: list[tuple[str, str]] = [
        ("Player To Score or Assist", "ga"),
        (MERCADO_ANYTIME_GOALSCORER, "g"),
    ]
    for nome_mercado, sufixo in mercados_regex:
        if sufixo_alvo and sufixo != sufixo_alvo:
            continue
        pat_bk_mkt = re.compile(
            rf'"([^"]{{2,40}})"\s*:\s*\[(?:[^\[\]]|\[[^\]]*\])*?"name"\s*:\s*"{re.escape(nome_mercado)}"'
            r'\s*,\s*"updatedAt"\s*:\s*"[^"]+"\s*,\s*"odds"\s*:\s*(\[[^\]]+\])',
            re.DOTALL,
        )
        for match in pat_bk_mkt.finditer(rsc_conteudo):
            bk_name, odds_raw = match.group(1), match.group(2)
            for player_match in _PAT_LABEL_OVER.finditer(odds_raw):
                player_nome = player_match.group(1)
                try:
                    odds_val = float(player_match.group(2))
                except ValueError:
                    continue
                if odds_val <= 1.0:
                    continue
                resultado[sufixo][player_nome] = _melhor_odd(
                    resultado[sufixo].get(player_nome), odds_val, bk_name
                )
    if sufixo_alvo:
        return {sufixo_alvo: resultado.get(sufixo_alvo, {})}
    return resultado


_PAT_NEXTF_PUSH = re.compile(
    r'self\.__next_f\.push\(\[1\s*,\s*"((?:[^"\\]|\\.)*)"\]\)',
    re.DOTALL,
)


def _desescapar_rsc(conteudo_js: str) -> str:
    """
    Extrai e desescapa os chunks RSC dos inline scripts __next_f.
    Os scripts têm formato: self.__next_f.push([1, "...escaped JSON..."])
    Precisamos desescapar para obter o JSON parseável.
    """
    partes: list[str] = []
    for match in _PAT_NEXTF_PUSH.finditer(conteudo_js):
        escaped = match.group(1)
        # Desfaz escaping básico de JSON-string
        unescaped = (
            escaped
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace("\\\\", "\\")
        )
        partes.append(unescaped)
    return "\n".join(partes)


def _rsc_de_pagina(pagina: Page) -> str:
    """
    Extrai RSC da página via inline scripts __next_f (DOM).
    Desescapa o conteúdo JavaScript para obter JSON parseável.
    """
    try:
        chunks: list[str] = pagina.evaluate("""() => {
            return [...document.querySelectorAll('script:not([src])')]
                .map(s => s.textContent)
                .filter(t => t.includes('__next_f'));
        }""")
        if not chunks:
            return ""
        conteudo_bruto = "\n".join(chunks)
        return _desescapar_rsc(conteudo_bruto)
    except Exception as e:
        logger.warning("Falha RSC textContent: %s", e)
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# [3] NORMALIZAÇÃO E DEDUPLICAÇÃO DE NOMES
# ══════════════════════════════════════════════════════════════════════════════


def _normalizar_nome_odds(nome: str) -> str:
    """
    Normaliza nome do bookmaker (remove acentos, lowercase).
    Ex: 'Raúl Jiménez' → 'raul jimenez', 'RAUL JIMENEZ' → 'raul jimenez'
    """
    return _norm(nome)


def consolidar_nomes_odds(
    odds: dict[str, tuple[float, str]]
) -> dict[str, tuple[float, str]]:
    """
    Agrupa entradas com o mesmo nome normalizado, mantendo a melhor odd.
    Ex: "Raul Jimenez", "RAUL JIMENEZ", "Raúl Jiménez" → "raul jimenez" (melhor odd).

    Retorna dicionário com chave normalizada.
    """
    agrupado: dict[str, tuple[float, str, str]] = {}  # norm → (odd, bk, nome_original)
    for nome_orig, (odd_val, bk) in odds.items():
        chave = _normalizar_nome_odds(nome_orig)
        if chave not in agrupado or odd_val > agrupado[chave][0]:
            agrupado[chave] = (odd_val, bk, nome_orig)
    return {nome_orig: (odd_val, bk) for _, (odd_val, bk, nome_orig) in agrupado.items()}


# ══════════════════════════════════════════════════════════════════════════════
# [4] MATCHING POR EQUIPE (matching_cartola.py)
# ══════════════════════════════════════════════════════════════════════════════


def casar_jogador_na_equipe(
    nome_bk: str,
    pool: list[dict],
    excluir_ids: set[int] | None = None,
) -> tuple[dict | None, int, list[tuple[int, dict]]]:
    """Compatibilidade com relatório — delega ao matching compartilhado."""
    jog, score = melhor_jogador_para_nome(
        nome_bk,
        pool,
        excluir_ids=excluir_ids,
        min_score=MIN_SCORE_ATRIBUICAO,
    )
    top3: list[tuple[int, dict]] = []
    if jog:
        top3.append((score, jog))
    return jog, score, top3


def _raspar_mercados_ptsoa(
    pagina: Page,
    rsc_acumulado: list[str],
    tamanho_antes: int,
    desc: str,
) -> dict[str, dict[str, tuple[float, str]]]:
    """
    Raspa G%, A% e GA% em passagens separadas (Score / Assist / Score Or Assist).
    Cada filtro gera RSC próprio — evita misturar mercados no merge acumulado.
    """
    odds_por: dict[str, dict[str, tuple[float, str]]] = {"g": {}, "a": {}, "ga": {}}
    _navegar_clicar_player(pagina)

    for rotulo, sufixo in MERCADOS_PLAYER_SUB_UI:
        if not _clicar_filtro_ptsoa(pagina, rotulo):
            logger.warning("  Filtro %s indisponivel em %s", rotulo, desc)
            continue

        slice_start = len(rsc_acumulado)
        for _ in range(8 if IS_CI else 6):
            pagina.wait_for_timeout(_wait_ms(2500))
            novos = rsc_acumulado[slice_start:]
            if sum(len(c) for c in novos) > 40_000:
                break

        rsc = _coletar_rsc_evento(pagina, rsc_acumulado, slice_start)
        rsc_dom = _rsc_de_pagina(pagina)
        extraido = extrair_odds_rsc(f"{rsc}\n{rsc_dom}", sufixo_alvo=sufixo)
        mercado = extraido.get(sufixo) or {}

        for nome, par in mercado.items():
            odds_por[sufixo][nome] = _melhor_odd(
                odds_por[sufixo].get(nome), par[0], par[1],
            )

        logger.info("  Filtro %s: %d jogadores", rotulo, len(mercado))

    return odds_por


def _navegar_clicar_anytime_goalscorer(pagina: Page) -> bool:
    """
    Abre Player → Anytime Goalscorer.
    Mercado alternativo disponível em partidas distantes quando PTSOA não expõe Score.
    """
    vis_timeout = _wait_ms(6000 if IS_CI else 4000)
    click_timeout = _wait_ms(8000 if IS_CI else 5000)

    try:
        pagina.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass

    clicou_player = False
    for seletor in [
        "button:has-text('Player')",
        "a:has-text('Player')",
        "[role='tab']:has-text('Player')",
    ]:
        try:
            el = pagina.locator(seletor).first
            if el.is_visible(timeout=vis_timeout):
                el.scroll_into_view_if_needed(timeout=vis_timeout)
                el.click(timeout=click_timeout)
                pagina.wait_for_timeout(_wait_ms(2500))
                clicou_player = True
                break
        except Exception:
            continue

    if not clicou_player:
        return False

    if not _clicar_mercado_player(pagina, MERCADO_ANYTIME_GOALSCORER):
        return False

    # Sub-aba interna quando o hub repete o rótulo (Player → AG → AG)
    _clicar_filtro_ptsoa(pagina, MERCADO_ANYTIME_GOALSCORER)
    return True


def _raspar_anytime_goalscorer(
    pagina: Page,
    rsc_acumulado: list[str],
    tamanho_antes: int,
    desc: str,
) -> dict[str, tuple[float, str]]:
    """Raspa G% via Player → Anytime Goalscorer (complemento para partidas distantes)."""
    if not _navegar_clicar_anytime_goalscorer(pagina):
        logger.info("  Anytime Goalscorer indisponivel em %s", desc)
        return {}

    slice_start = len(rsc_acumulado)
    for _ in range(8 if IS_CI else 6):
        pagina.wait_for_timeout(_wait_ms(2500))
        novos = rsc_acumulado[slice_start:]
        if sum(len(c) for c in novos) > 40_000:
            break

    rsc = _coletar_rsc_evento(pagina, rsc_acumulado, slice_start)
    extraido = extrair_odds_rsc(rsc, sufixo_alvo="g")
    mercado = extraido.get("g") or {}
    logger.info("  Anytime Goalscorer: %d jogadores", len(mercado))
    return mercado


def _aplicar_mercado_evento(
    odds_map: dict[str, tuple[float, str]],
    sufixo: str,
    pools: list[list[dict]],
    eid: int,
    sel_home: str,
    sel_away: str,
    selecao_sigla: dict[str, str],
    resultado: dict[str, dict],
    relatorio: Relatorio,
    desc: str,
    *,
    modo_armazenamento: bool = False,
    rodada_evento: int | None = None,
) -> int:
    """Atribui odds do mercado (g/a/ga) ao elenco com matching um-a-um."""
    if not odds_map:
        return 0

    candidatos: list[dict] = []
    for pool in pools:
        candidatos.extend(pool)

    atrib = atribuir_nomes_a_jogadores(
        list(odds_map.keys()),
        candidatos,
        min_score=MIN_SCORE_ATRIBUICAO,
    )
    adicionados = 0
    matched: set[str] = set()

    for nome_bk, (jog, score) in atrib.items():
        adv = _adversario_sigla_jogador(jog, sel_home, sel_away, selecao_sigla)
        if not modo_armazenamento and not _deve_atualizar_odds(jog, adv):
            continue
        relatorio.match(nome_bk, jog, score, desc)
        odd_val, odd_bk = odds_map[nome_bk]
        if _aplicar_pct_jogador(
            resultado, eid, jog, adv, sufixo, odd_val, odd_bk,
            modo_armazenamento=modo_armazenamento,
            rodada_evento=rodada_evento,
        ):
            adicionados += 1
            registrar_alias_aprendido(nome_bk, jog, score)
        matched.add(nome_bk)

    nomes_lacuna = [n for n in odds_map if n not in matched]
    if nomes_lacuna:
        pct_key, _, _ = _chaves_mercado(sufixo)
        sem_campo = [
            j for j in candidatos
            if modo_armazenamento
            or not (resultado.get(str(j["atleta_id"])) or {}).get(pct_key)
        ]
        lacunas = atribuir_nomes_a_jogadores(
            nomes_lacuna,
            sem_campo,
            min_score=MIN_SCORE_LACUNA,
        )
        for nome_bk, (jog, score) in lacunas.items():
            adv = _adversario_sigla_jogador(jog, sel_home, sel_away, selecao_sigla)
            if not modo_armazenamento and not _deve_atualizar_odds(jog, adv):
                continue
            relatorio.match(f"{nome_bk} [lacuna]", jog, score, desc)
            odd_val, odd_bk = odds_map[nome_bk]
            if _aplicar_pct_jogador(
                resultado, eid, jog, adv, sufixo, odd_val, odd_bk,
                modo_armazenamento=modo_armazenamento,
                rodada_evento=rodada_evento,
            ):
                adicionados += 1
                registrar_alias_aprendido(nome_bk, jog, score)
            matched.add(nome_bk)

    for nome_bk in odds_map:
        if nome_bk in matched:
            continue
        _, score, top3 = casar_jogador_na_equipe(nome_bk, candidatos)
        relatorio.no_match(nome_bk, score, top3, desc)

    return adicionados


def _adv_para_entrada(jog: dict, adv: str | None) -> str | None:
    if adv:
        return adv
    prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
    return prox or None


def _chaves_mercado(sufixo: str) -> tuple[str, str, str]:
    pct_key = f"{sufixo}_pct" if sufixo != "ga" else "ga_pct"
    casa_key = f"casa_{sufixo}" if sufixo != "ga" else "casa_ga"
    odds_key = f"odds_{sufixo}" if sufixo != "ga" else "odds_ga"
    return pct_key, casa_key, odds_key


def _aplicar_pct_jogador(
    resultado: dict[str, dict],
    eid: int,
    jog: dict,
    adv: str | None,
    sufixo: str,
    odd_val: float,
    odd_bk: str,
    *,
    modo_armazenamento: bool = False,
    rodada_evento: int | None = None,
) -> bool:
    if not modo_armazenamento and not _deve_atualizar_odds(jog, adv):
        return False
    pct_key, casa_key, odds_key = _chaves_mercado(sufixo)
    aid = str(jog["atleta_id"])
    entrada: dict[str, Any] = resultado.get(aid) or {"event_id": eid}
    if not modo_armazenamento and entrada.get(pct_key):
        return False
    entrada["event_id"] = eid
    rodada_gravar = rodada_evento if rodada_evento is not None else _RODADA_ATUAL
    entrada["rodada"] = rodada_gravar
    adv_final = adv if modo_armazenamento else _adv_para_entrada(jog, adv)
    if adv_final:
        entrada["adversario_sigla"] = adv_final
    entrada[pct_key] = _prob(odd_val)
    entrada[casa_key] = odd_bk
    entrada[odds_key] = odd_val
    resultado[aid] = entrada
    return True


# ══════════════════════════════════════════════════════════════════════════════
# [5] RELATÓRIO
# ══════════════════════════════════════════════════════════════════════════════


class Relatorio:
    def __init__(self) -> None:
        self.matched: list[str] = []
        self.borderline: list[str] = []
        self.unmatched: list[str] = []

    def match(self, nome: str, jog: dict, score: int, desc: str) -> None:
        apelido = jog.get("apelido", "?")
        self.matched.append(f"  [OK {score:3d}%] {nome!r:35} -> {apelido!r} (id={jog['atleta_id']}) [{desc}]")
        if score < THRESHOLD_AUTO:
            self.borderline.append(
                f"  [⚠️ {score:3d}%] {nome!r:35} -> {apelido!r} — score<{THRESHOLD_AUTO}, verifique"
            )

    def no_match(self, nome: str, score: int, top3: list, desc: str) -> None:
        cands = ", ".join(f"{j.get('apelido','?')}({s}%)" for s, j in top3)
        self.unmatched.append(
            f"  [XX {score:3d}%] {nome!r:35} sem match | candidatos: {cands or '—'} [{desc}]"
        )

    def imprimir(self) -> None:
        sep = "=" * 72
        print(f"\n{sep}")
        print(
            f"RELATORIO: {len(self.matched)} matched | "
            f"{len(self.unmatched)} sem match | "
            f"{len(self.borderline)} borderline"
        )
        print(sep)
        if self.borderline:
            print(f"\n[BORDERLINE — revisar] ({len(self.borderline)}):")
            for m in self.borderline:
                print(m)
        if self.unmatched:
            print(f"\n[SEM MATCH] ({len(self.unmatched)}):")
            for m in self.unmatched:
                print(m)
        else:
            print("\nTodos os jogadores foram mapeados com sucesso.")
        print(f"\n[MATCHED] ({len(self.matched)}):")
        for m in self.matched:
            print(m)
        print(sep + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# [6] PROCESSAMENTO DE EVENTO
# ══════════════════════════════════════════════════════════════════════════════


def _prob(odds: float) -> float:
    return round(100.0 / odds, 2) if odds > 1.0 else 0.0


def _clicar_mercado_player(pagina: Page, rotulo: str) -> bool:
    vis_timeout = _wait_ms(6000 if IS_CI else 4000)
    click_timeout = _wait_ms(8000 if IS_CI else 5000)
    for seletor in [
        f"button:has-text('{rotulo}')",
        f"a:has-text('{rotulo}')",
        f"[role='tab']:has-text('{rotulo}')",
        f"text={rotulo}",
    ]:
        try:
            el = pagina.locator(seletor).first
            if el.is_visible(timeout=vis_timeout):
                el.scroll_into_view_if_needed(timeout=vis_timeout)
                el.click(timeout=click_timeout)
                pagina.wait_for_timeout(_wait_ms(2500))
                return True
        except Exception:
            continue
    return False


def _clicar_filtro_ptsoa(pagina: Page, rotulo: str) -> bool:
    """
    Sub-filtro dentro de Player To Score or Assist: 'Score (44)', 'Assist (44)', etc.
    """
    vis_timeout = _wait_ms(6000 if IS_CI else 4000)
    click_timeout = _wait_ms(8000 if IS_CI else 5000)
    padrao = re.compile(rf"^{re.escape(rotulo)}\s*(\(\d+\))?\s*$", re.IGNORECASE)

    try:
        botoes = pagina.locator("button")
        total = min(botoes.count(), 120)
        for idx in range(total):
            try:
                texto = botoes.nth(idx).inner_text(timeout=1500).strip()
            except Exception:
                continue
            linha = texto.split("\n")[0].strip()
            if not padrao.match(linha):
                continue
            btn = botoes.nth(idx)
            if not btn.is_visible(timeout=vis_timeout):
                continue
            btn.scroll_into_view_if_needed(timeout=vis_timeout)
            btn.click(timeout=click_timeout)
            pagina.wait_for_timeout(_wait_ms(2500))
            return True
    except Exception:
        pass

    return _clicar_mercado_player(pagina, rotulo)


def _navegar_clicar_player(pagina: Page) -> None:
    """Abre Player → Player To Score or Assist (sub-filtros são clicados em processar_evento)."""
    vis_timeout = _wait_ms(6000 if IS_CI else 4000)
    click_timeout = _wait_ms(8000 if IS_CI else 5000)

    try:
        pagina.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass

    for seletor in ["button:has-text('Player')", "a:has-text('Player')",
                    "[role='tab']:has-text('Player')"]:
        try:
            el = pagina.locator(seletor).first
            if el.is_visible(timeout=vis_timeout):
                el.scroll_into_view_if_needed(timeout=vis_timeout)
                el.click(timeout=click_timeout)
                pagina.wait_for_timeout(_wait_ms(2500))
                break
        except Exception:
            pass

    if not _clicar_mercado_player(pagina, MERCADO_PLAYER_PAI) and IS_CI:
        try:
            pagina.get_by_text(MERCADO_PLAYER_PAI, exact=False).first.click(
                timeout=click_timeout, force=True,
            )
            pagina.wait_for_timeout(_wait_ms(2500))
        except Exception:
            pass


def _mesclar_odds_rsc(acumulado: dict[str, dict], novo: dict[str, dict]) -> None:
    for mercado in ("g", "a", "ga"):
        for nome, par in novo.get(mercado, {}).items():
            acumulado.setdefault(mercado, {})[nome] = _melhor_odd(
                acumulado.get(mercado, {}).get(nome), par[0], par[1],
            )


def _screenshot_falha(pagina: Page, eid: int) -> None:
    if not IS_CI:
        return
    pasta = _RAIZ / "logs" / "odds_failures"
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        path = pasta / f"evento_{eid}.png"
        pagina.screenshot(path=str(path), full_page=True)
        logger.info("Screenshot salvo: %s", path)
    except Exception as e:
        logger.debug("Screenshot falhou: %s", e)


def _pagina_parece_bloqueada(pagina: Page) -> bool:
    try:
        html = pagina.content().lower()
        titulo = pagina.title().lower()
    except Exception:
        return True
    sinais = ("just a moment", "cloudflare", "cf-challenge", "access denied", "captcha")
    return any(s in html or s in titulo for s in sinais)


def _rsc_tem_bookmakers(rsc: str) -> bool:
    bks = _extrair_json_object(rsc, "bookmakers")
    return bool(bks and len(bks) >= 2)


def _coletar_rsc_evento(
    pagina: Page,
    rsc_acumulado: list[str],
    tamanho_antes: int,
) -> str:
    rsc_rede = "\n".join(rsc_acumulado[tamanho_antes:])
    rsc_dom = _rsc_de_pagina(pagina)
    return rsc_rede + "\n" + rsc_dom


def processar_evento(
    evento: dict,
    pagina: Page,
    jogadores: list[dict],
    jogadores_todos: list[dict],
    resultado: dict[str, dict],
    relatorio: Relatorio,
    rsc_acumulado: list[str],
    *,
    modo_armazenamento: bool = False,
    captura_api: ArmazenamentoCapturaOdds | None = None,
) -> int:
    eid = evento["id"]
    home, away = evento.get("home", "?"), evento.get("away", "?")
    desc = f"{home} vs {away}"
    confronto = evento.get("confronto") or {}
    rodada_evento = evento.get("rodada") or confronto.get("rodada")
    if rodada_evento is not None:
        try:
            rodada_evento = int(rodada_evento)
        except (TypeError, ValueError):
            rodada_evento = None

    logger.info("Processando: %s (id=%d)", desc, eid)

    # Limpa o acumulador de RSC para este evento
    tamanho_antes = len(rsc_acumulado)

    url = _url_evento(eid)
    try:
        pagina.goto(url, timeout=TIMEOUT_PAGINA, wait_until="load")
    except Exception as e:
        logger.warning("Navegacao falhou para %s: %s", desc, e)
        return 0

    pagina.wait_for_timeout(_wait_ms(random.randint(5000, 9000)))

    if _pagina_parece_bloqueada(pagina):
        logger.warning("Pagina bloqueada/antibot em %s — aguardando retry...", desc)
        pagina.wait_for_timeout(_wait_ms(8000))
        try:
            pagina.reload(timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
        except Exception:
            pass
        pagina.wait_for_timeout(_wait_ms(6000))

    _navegar_clicar_player(pagina)

    odds_bruto_acum: dict[str, dict] = {"g": {}, "a": {}, "ga": {}}
    rsc = ""
    max_tentativas = 4 if IS_CI else 3
    for tentativa in range(max_tentativas):
        if tentativa > 0:
            try:
                pagina.reload(timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
            except Exception:
                pagina.goto(url, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
            pagina.wait_for_timeout(_wait_ms(random.randint(7000, 11000)))

        odds_bruto_acum = _raspar_mercados_ptsoa(pagina, rsc_acumulado, tamanho_antes, desc)
        rsc = _coletar_rsc_evento(pagina, rsc_acumulado, tamanho_antes)

        if _rsc_tem_bookmakers(rsc) or any(odds_bruto_acum[m] for m in ("g", "a", "ga")):
            break
        if tentativa < max_tentativas - 1:
            logger.warning(
                "RSC incompleto (%d chars, g=%d a=%d ga=%d), recarregando...",
                len(rsc),
                len(odds_bruto_acum["g"]),
                len(odds_bruto_acum["a"]),
                len(odds_bruto_acum["ga"]),
            )

    g_antes_ag = len(odds_bruto_acum["g"])
    odds_ag = _raspar_anytime_goalscorer(pagina, rsc_acumulado, tamanho_antes, desc)
    if odds_ag:
        _mesclar_odds_rsc(odds_bruto_acum, {"g": odds_ag, "a": {}, "ga": {}})
        rsc_ag = _coletar_rsc_evento(pagina, rsc_acumulado, tamanho_antes)
        if rsc_ag.strip():
            rsc = f"{rsc}\n{rsc_ag}" if rsc.strip() else rsc_ag
        logger.info(
            "  Anytime Goalscorer mesclado: g %d → %d",
            g_antes_ag,
            len(odds_bruto_acum["g"]),
        )

    if captura_api is not None:
        payload_api = captura_api.obter_odds_evento(eid)
        if payload_api:
            api_odds = extrair_odds_de_payload(payload_api, extrair_odds_rsc)
            antes_g, antes_a, antes_ga = (
                len(odds_bruto_acum["g"]),
                len(odds_bruto_acum["a"]),
                len(odds_bruto_acum["ga"]),
            )
            _mesclar_odds_rsc(odds_bruto_acum, api_odds)
            logger.info(
                "  API rede mesclada: g %d→%d a %d→%d ga %d→%d",
                antes_g, len(odds_bruto_acum["g"]),
                antes_a, len(odds_bruto_acum["a"]),
                antes_ga, len(odds_bruto_acum["ga"]),
            )
            bloco_api = payload_para_texto(payload_api)
            rsc = f"{rsc}\n{bloco_api}" if rsc.strip() else bloco_api

    if not rsc.strip() and not any(odds_bruto_acum[m] for m in ("g", "a", "ga")):
        logger.warning("RSC vazio para %s — nenhum dado extraido.", desc)
        _screenshot_falha(pagina, eid)
        return 0

    logger.info("RSC total: %d chars", len(rsc))

    if not any(odds_bruto_acum[m] for m in ("g", "a", "ga")) and rsc.strip():
        _mesclar_odds_rsc(odds_bruto_acum, extrair_odds_rsc(rsc))

    odds_g = consolidar_nomes_odds(odds_bruto_acum["g"])
    odds_a = consolidar_nomes_odds(odds_bruto_acum["a"])
    odds_ga = consolidar_nomes_odds(odds_bruto_acum["ga"])
    sg_home, sg_away = extrair_sg_times(rsc)
    if captura_api is not None and not sg_home and not sg_away:
        payload_api = captura_api.obter_odds_evento(eid)
        if payload_api:
            sg_home, sg_away = extrair_sg_de_payload(payload_api, extrair_sg_times)

    sel_home = _mapear_selecao(home)
    sel_away = _mapear_selecao(away)
    selecao_sigla = _mapas_sigla(jogadores_todos)
    pool_home = jogadores_da_equipe(jogadores, sel_home)
    pool_away = jogadores_da_equipe(jogadores, sel_away)
    pool_home_sg = pool_defensores(jogadores_todos, sel_home)
    pool_away_sg = pool_defensores(jogadores_todos, sel_away)

    logger.info("  Pools linha: %s=%d | %s=%d | SG: %d + %d",
                sel_home, len(pool_home), sel_away, len(pool_away),
                len(pool_home_sg), len(pool_away_sg))

    if not odds_g and not odds_a and not odds_ga and not sg_home and not sg_away:
        logger.warning("Nenhuma odd extraida para %s.", desc)
        _screenshot_falha(pagina, eid)
        return 0

    n_sg = _aplicar_sg_evento(
        resultado, eid, pool_home_sg, pool_away_sg, sg_home, sg_away,
        sel_home, sel_away, selecao_sigla,
        modo_armazenamento=modo_armazenamento,
        rodada_evento=rodada_evento,
    )

    if odds_g or odds_a or odds_ga:
        logger.info(
            "  %s: %d marcar | %d assistir | %d marcar ou assistir",
            desc, len(odds_g), len(odds_a), len(odds_ga),
        )

    adicionados = n_sg
    pools_linha = [pool_home, pool_away]

    for sufixo, odds_map in (
        ("g", odds_g),
        ("a", odds_a),
        ("ga", odds_ga),
    ):
        adicionados += _aplicar_mercado_evento(
            odds_map,
            sufixo,
            pools_linha,
            eid,
            sel_home,
            sel_away,
            selecao_sigla,
            resultado,
            relatorio,
            desc,
            modo_armazenamento=modo_armazenamento,
            rodada_evento=rodada_evento,
        )

    logger.info("  %d atletas (G+A+GA+SG).", adicionados)
    return adicionados


# ══════════════════════════════════════════════════════════════════════════════
# [7] ORQUESTRADOR
# ══════════════════════════════════════════════════════════════════════════════


def _headless() -> bool:
    return os.environ.get("ODDSNOTIFIER_HEADLESS", "true").strip().lower() not in ("0", "false", "no", "off")


def executar() -> None:
    global _RODADA_ATUAL

    if os.environ.get("ODDS_ONLY_COMPILE", "").strip() in ("1", "true", "yes"):
        from scrapers.odds_armazenamento import compilar_e_salvar
        logger.info("Modo compilação apenas (sem scrape).")
        compilar_e_salvar()
        return

    jogadores = carregar_jogadores(CAMINHO_MERCADO)
    jogadores_todos = carregar_todos_jogadores(CAMINHO_MERCADO)
    if not jogadores:
        logger.error("Nenhum jogador em %s — abortando.", CAMINHO_MERCADO)
        sys.exit(1)

    hoje = referencia_hoje()
    dias = janela_dias()
    selecao_sigla = mapa_sigla_por_selecao(jogadores_todos)
    confrontos_janela = confrontos_na_janela(hoje, dias)
    _RODADA_ATUAL = _rodada_odds_alvo(jogadores_todos)

    logger.info(
        "=== Scraper Odds WC2026 (janela %s + %d dias, %d confrontos, CI=%s) ===",
        hoje.isoformat(),
        dias,
        len(confrontos_janela),
        IS_CI,
    )

    armazenamento = carregar_armazenamento()
    expurgar_passados(armazenamento, hoje)
    eventos_store: dict[str, dict] = armazenamento.setdefault("eventos", {})

    relatorio = Relatorio()
    total_add = 0
    eventos_ok: list[int] = []
    eventos_falha: list[dict] = []
    num_eventos = 0
    falhas = 0

    with sync_playwright() as pw:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1440,900",
            "--disable-gpu",
        ]
        if IS_CI:
            launch_args.append("--headless=new")

        browser = pw.chromium.launch(
            headless=_headless(),
            args=launch_args,
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        ctx.add_init_script(STEALTH_INIT_SCRIPT)
        pagina = ctx.new_page()

        rsc_acumulado: list[str] = []
        captura_api = ArmazenamentoCapturaOdds(logger)
        captura_api.vincular_pagina(pagina)

        def _capturar_rsc(resp) -> None:
            if "oddsnotifier" not in resp.url:
                return
            ct = (resp.headers.get("content-type") or "").lower()
            try:
                if "json" in ct:
                    corpo = resp.text()
                    if corpo and "bookmakers" in corpo:
                        rsc_acumulado.append(corpo)
                        return
            except Exception:
                pass
            if "x-component" not in ct and "text/html" not in ct and "javascript" not in ct:
                return
            try:
                texto = resp.text()
                if texto and ("__next_f" in texto or "bookmakers" in texto):
                    rsc_acumulado.append(texto)
                    logger.debug("RSC resp %d chars: %s", len(texto), resp.url[:80])
            except Exception:
                pass

        pagina.on("response", _capturar_rsc)

        try:
            logger.info("Warm-up: %s", URL_HUB_FIFA)
            pagina.goto(URL_HUB_FIFA, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
            pagina.wait_for_timeout(_wait_ms(random.randint(4000, 7000)))
            rsc_wc2026 = _rsc_de_pagina(pagina) + "\n".join(rsc_acumulado)

            eventos = buscar_eventos_janela(
                pagina, confrontos_janela, selecao_sigla, rsc_wc2026,
            )

            if not eventos:
                logger.error(
                    "Abortando: nenhum evento mapeado na janela %s..+%dd.",
                    hoje.isoformat(),
                    dias,
                )
                sys.exit(1)

            for idx, evento in enumerate(eventos, start=1):
                eid = int(evento["id"])
                conf = evento.get("confronto") or {}
                logger.info(
                    "[%d/%d] %s vs %s (data=%s)",
                    idx, len(eventos),
                    evento.get("home", "?"), evento.get("away", "?"),
                    evento.get("data", "?"),
                )

                chave = str(eid)
                odds_evento: dict[str, dict] = {}
                if chave in eventos_store:
                    bruto = eventos_store[chave].get("odds") or {}
                    odds_evento = {str(k): dict(v) for k, v in bruto.items() if isinstance(v, dict)}

                antes = len(odds_evento)
                n = processar_evento(
                    evento, pagina, jogadores, jogadores_todos,
                    odds_evento, relatorio, rsc_acumulado,
                    modo_armazenamento=True,
                    captura_api=captura_api,
                )
                if n > 0:
                    eventos_ok.append(eid)
                    total_add += n
                    eventos_store[chave] = montar_registro_evento(evento, conf, odds_evento)
                    eventos_store[chave]["raspar_em"] = datetime.now(tz=timezone.utc).isoformat()
                else:
                    eventos_falha.append(evento)
                logger.info("  delta atletas neste evento: %+d", len(odds_evento) - antes)

                if idx < len(eventos):
                    delay = random.uniform(DELAY_MIN, DELAY_MAX)
                    logger.info("Aguardando %.0fs...", delay)
                    time.sleep(delay)

            if eventos_falha:
                logger.info("Retry de %d eventos com falha...", len(eventos_falha))
                for evento in eventos_falha:
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                    eid = int(evento["id"])
                    conf = evento.get("confronto") or {}
                    chave = str(eid)
                    odds_evento = {}
                    if chave in eventos_store:
                        bruto = eventos_store[chave].get("odds") or {}
                        odds_evento = {str(k): dict(v) for k, v in bruto.items() if isinstance(v, dict)}
                    n = processar_evento(
                        evento, pagina, jogadores, jogadores_todos,
                        odds_evento, relatorio, rsc_acumulado,
                        modo_armazenamento=True,
                        captura_api=captura_api,
                    )
                    if n > 0:
                        eventos_ok.append(eid)
                        total_add += n
                        eventos_store[chave] = montar_registro_evento(evento, conf, odds_evento)
                        eventos_store[chave]["raspar_em"] = datetime.now(tz=timezone.utc).isoformat()

            num_eventos = len(eventos)
            falhas = num_eventos - len(set(eventos_ok))

        finally:
            try:
                ctx.close()
                browser.close()
            except Exception:
                pass

    expurgar_passados(armazenamento, hoje)
    armazenamento["referencia_data"] = hoje.isoformat()
    armazenamento["janela_dias"] = dias
    armazenamento["atualizado_em"] = datetime.now(tz=timezone.utc).isoformat()
    salvar_armazenamento(armazenamento)

    resultado = compilar_dashboard(armazenamento, jogadores_todos, hoje)
    base_total = len(resultado)

    logger.info(
        "Scraping concluido: %d eventos OK | %d falhas | +%d atletas raspados | dashboard=%d",
        len(set(eventos_ok)),
        falhas,
        total_add,
        base_total,
    )

    relatorio.imprimir()

    if total_add == 0 and base_total < MIN_JOGADORES_SALVAR:
        anterior = 0
        if CAMINHO_SAIDA.is_file():
            try:
                with CAMINHO_SAIDA.open(encoding="utf-8") as f:
                    anterior = len(json.load(f).get("odds", {}))
            except Exception:
                pass
        if anterior >= MIN_JOGADORES_SALVAR:
            logger.warning(
                "Nenhuma odd nova nesta execucao — recompilando armazenamento anterior."
            )
            resultado = compilar_dashboard(armazenamento, jogadores_todos, hoje)
            if len(resultado) >= MIN_JOGADORES_SALVAR:
                _salvar(resultado, referencia_data=hoje.isoformat())
                return
        logger.error("Scrape insuficiente e sem backup valido.")
        sys.exit(1)

    _salvar(resultado, referencia_data=hoje.isoformat())


def _garantir_adversario_vigente(
    resultado: dict[str, dict],
    jogadores: list[dict],
) -> int:
    """
    Preenche adversario_sigla quando o jogador tem ADV no mercado mas a entrada
    ficou sem sigla (merge parcial ou scrape antigo). Independe de status_id.
    """
    corrigidos = 0
    for jog in jogadores:
        prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        if not prox:
            continue
        aid = str(jog.get("atleta_id"))
        entrada = resultado.get(aid)
        if not isinstance(entrada, dict):
            continue
        tem = entrada.get("ga_pct") or entrada.get("g_pct") or entrada.get("a_pct") or entrada.get("sg_pct")
        if not tem:
            continue
        odds_adv = (entrada.get("adversario_sigla") or "").strip().upper()
        if odds_adv == prox:
            continue
        if int(jog.get("copa_jogos_num") or 0) <= 0:
            entrada["adversario_sigla"] = prox
            corrigidos += 1
    if corrigidos:
        logger.info("Adversario vigente corrigido em %d entradas.", corrigidos)
    return corrigidos


def _normalizar_odds_pos_estreia(
    resultado: dict[str, dict],
    jogadores: list[dict],
) -> int:
    """
    Remove mercados de ataque/SG obsoletos quando adversario_sigla != proximo ADV.
    Evita exibir odds da rodada anterior após merge parcial.
    """
    removidos = 0
    for jog in jogadores:
        if int(jog.get("copa_jogos_num") or 0) <= 0:
            continue
        prox = (jog.get("proximo_adversario_sigla") or "").upper()
        if not prox:
            continue
        aid = str(jog.get("atleta_id"))
        entrada = resultado.get(aid)
        if not isinstance(entrada, dict):
            continue
        odds_adv = (entrada.get("adversario_sigla") or "").upper()
        if odds_adv == prox:
            continue
        for chave in (
            "g_pct", "casa_g", "odds_g",
            "a_pct", "casa_a", "odds_a",
            "ga_pct", "casa_ga", "odds_ga",
            "sg_pct", "casa_sg", "odds_sg",
            "adversario_sigla", "rodada",
        ):
            if chave in entrada:
                del entrada[chave]
                removidos += 1
    if removidos:
        logger.info("Normalizacao pos-estreia: %d campos obsoletos removidos.", removidos)
    return removidos


def _resolver_eventos_scrape(
    pagina: Page,
    jogadores_todos: list[dict],
    confrontos_prox: list[dict],
    eventos_arquivo: list[dict],
    skip_warmup: bool,
    rsc_acumulado: list[str],
) -> tuple[list[dict], str]:
    """Define lista de eventos e RSC do hub conforme rodada / próximo adversário."""
    rsc_wc2026 = ""

    if _RODADA_ATUAL > 1 or confrontos_prox:
        logger.info(
            "Modo rodada %d (%d confrontos com jogadores que ja atuaram)",
            _RODADA_ATUAL,
            len(confrontos_prox),
        )
        logger.info("Warm-up: %s", URL_WC2026)
        pagina.goto(URL_WC2026, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
        pagina.wait_for_timeout(_wait_ms(random.randint(5000, 8000)))
        rsc_wc2026 = _rsc_de_pagina(pagina) + "\n".join(rsc_acumulado)

        eventos: list[dict] = []
        if confrontos_prox:
            eventos = buscar_eventos_proximo_adversario(pagina, jogadores_todos, rsc_wc2026)
            if eventos:
                logger.info("Eventos via proximo adversario: %d partidas.", len(eventos))
        if not eventos:
            eventos = buscar_eventos_rodada_completa(pagina, _RODADA_ATUAL, rsc_wc2026)
            if eventos:
                logger.info("Eventos via rodada completa: %d partidas.", len(eventos))
        if not eventos:
            logger.error(
                "Nenhum evento mapeado para rodada %d — odds anteriores preservadas via merge.",
                _RODADA_ATUAL,
            )
        return eventos, rsc_wc2026

    if skip_warmup and eventos_arquivo:
        logger.info("Warm-up omitido — %d eventos do arquivo versionado.", len(eventos_arquivo))
        if IS_CI:
            logger.info("Sessao CI: visita rapida a %s", URL_WC2026)
            try:
                pagina.goto(URL_WC2026, timeout=TIMEOUT_PAGINA, wait_until="load")
                pagina.wait_for_timeout(_wait_ms(6000))
            except Exception as exc:
                logger.warning("Warm-up rapido falhou (continuando): %s", exc)
        return eventos_arquivo, rsc_wc2026

    logger.info("Warm-up: %s", URL_WC2026)
    pagina.goto(URL_WC2026, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
    pagina.wait_for_timeout(_wait_ms(random.randint(5000, 8000)))
    rsc_wc2026 = _rsc_de_pagina(pagina) + "\n".join(rsc_acumulado)
    return buscar_eventos(pagina, rsc_wc2026), rsc_wc2026


def _salvar(odds: dict[str, dict], *, referencia_data: str | None = None) -> None:
    n = len(odds)
    if n < MIN_JOGADORES_SALVAR:
        anterior = 0
        if CAMINHO_SAIDA.is_file():
            try:
                with CAMINHO_SAIDA.open(encoding="utf-8") as f:
                    anterior = len(json.load(f).get("odds", {}))
            except Exception:
                pass
        if anterior >= MIN_JOGADORES_SALVAR:
            logger.error(
                "Scrape insuficiente (%d atletas; minimo %d). "
                "Preservando arquivo anterior (%d atletas).",
                n,
                MIN_JOGADORES_SALVAR,
                anterior,
            )
        else:
            logger.error(
                "Scrape insuficiente (%d atletas; minimo %d) e sem backup valido.",
                n,
                MIN_JOGADORES_SALVAR,
            )
        sys.exit(1)

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ref = referencia_data or referencia_hoje().isoformat()
    payload = {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "referencia_data": ref,
        "total_jogadores": len(odds),
        "odds": odds,
    }
    with CAMINHO_SAIDA.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    marcar_dashboard_atualizado(CAMINHO_ESTADO)
    logger.info("Salvo: %d atletas -> %s", len(odds), CAMINHO_SAIDA)


if __name__ == "__main__":
    executar()
