"""
Scraper de odds de jogadores — hub.oddsnotifier.io × Cartola WC 2026.

Arquitetura (corrigida após diagnóstico):
  Os dados de odds NÃO estão em /api/odds/{eventId}.
  Estão embutidos no HTML inicial como RSC (__next_f) — React Server Components.
  O browser carrega os scripts inline, e após clicar "Player" → "Anytime Goalscorer"
  o DOM expõe os dados. Mas os dados já estão no __next_f mesmo sem clicar.

Fluxo:
  [1] Carrega jogadores_mercado.json → índice por selecao
  [2] Busca eventos via API (fallback: lista fixa se API indisponível):
      a. Playwright navega → /football/international-world-cup/{eventId}
      b. Clica "Player" → "Anytime Goalscorer" (ativa RSC completo)
      c. Extrai todos os <script> __next_f do DOM
      d. Parseia RSC para mercados "Anytime Goalscorer" e "Player To Assist"
      e. Pega melhor odd por jogador entre todas as casas
  [3] Matching POR EQUIPE: fuzzy restrito às equipes do jogo
  [4] Salva odds_jogadores.json com atleta_id como chave

Anti-ban: delays 20-40s, headless configurável via ODDSNOTIFIER_HEADLESS
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Page
from thefuzz import fuzz

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
CAMINHO_MERCADO: Path = _RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_GRUPOS:  Path = _RAIZ / "frontend" / "public" / "data" / "grupos_wc2026.json"
CAMINHO_EVENTOS: Path = _RAIZ / "frontend" / "public" / "data" / "eventos_odds_rodada1.json"
CAMINHO_SAIDA:   Path = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"

# ──────────────────────────────────── Config ──────────────────────────────────

POSICOES_LINHA: frozenset[int] = frozenset({2, 3, 4, 5})

MERCADOS_RSC: dict[str, str] = {
    "Anytime Goalscorer": "g",
    "Player To Assist":   "a",
}

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

MAX_EVENTOS: int = int(os.environ.get("ODDS_MAX_EVENTOS", "24"))
RODADA_ALVO: int = int(os.environ.get("ODDS_RODADA", "1"))
TIMEOUT_PAGINA: int = 35_000

DELAY_MIN: float = float(os.environ.get("ODDS_DELAY_MIN", "12"))
DELAY_MAX: float = float(os.environ.get("ODDS_DELAY_MAX", "22"))

# Threshold fuzzy matching
THRESHOLD_AUTO:   int = 85
THRESHOLD_REVIEW: int = 72

# Mapa de nomes exatos do oddsnotifier → apelido no Cartola (para casos borderline)
# Formato: nome_normalizado_oddsnotifier → atleta_id no Cartola
ALIAS_JOGADORES: dict[str, int] = {
    "lira e":           128559,   # Érik Lira (LIRA E. → score 77%)
    "chavez garcia m":  146414,   # Mateo Chávez García
    "mora zambrano g":  141486,   # Gilberto Mora Zambrano
    "reyes romero":     132767,   # Israel Reyes Romero
}

# Mapa oddsnotifier → seleção Cartola (campo upper)
ALIAS_TIMES: dict[str, str] = {
    "KOREA REPUBLIC":          "SOUTH KOREA",
    "SOUTH KOREA":             "SOUTH KOREA",
    "CZECH REPUBLIC":          "CZECHIA",
    "CZECHIA":                 "CZECHIA",
    "BOSNIA & HERZ.":          "BOSNIA AND HERZEGOVINA",
    "BOSNIA AND HERZEGOVINA":  "BOSNIA AND HERZEGOVINA",
    "USA":                     "UNITED STATES",
    "UNITED STATES":           "UNITED STATES",
    "TURKIYE":                 "TURKIYE",
    "TÜRKIYE":                 "TURKIYE",
    "CAPE VERDE ISLANDS":      "CAPE VERDE",
    "CAPE VERDE":              "CAPE VERDE",
    "CURACAO":                 "CURACAO",
    "CURAÇAO":                 "CURACAO",
    "COTE D'IVOIRE":           "IVORY COAST",
    "CÔTE D'IVOIRE":           "IVORY COAST",
    "CONGO DR":                "DR CONGO",
    "IR IRAN":                 "IRAN",
    "IRAN":                    "IRAN",
    "IRAQ":                    "IRAQ",
}

# Faixa de IDs oddsnotifier para descoberta automática (World Cup 2026)
ODDS_ID_SCAN_MIN: int = 66456900
ODDS_ID_SCAN_MAX: int = 66457150

# ══════════════════════════════════════════════════════════════════════════════
# [0] EVENTOS — fixtures WC2026 + mapeamento oddsEventId
# ══════════════════════════════════════════════════════════════════════════════

URL_WC2026 = "https://hub.oddsnotifier.io/world-cup-2026"
URL_API_EVENTOS = "https://hub.oddsnotifier.io/api/events/football/international-world-cup"


def _url_evento(event_id: int) -> str:
    return f"https://hub.oddsnotifier.io/football/international-world-cup/{event_id}"


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


def _carregar_confrontos_rodada(rodada: int) -> list[dict]:
    if not CAMINHO_GRUPOS.exists():
        logger.error("grupos_wc2026.json nao encontrado")
        return []
    with CAMINHO_GRUPOS.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [c for c in dados.get("confrontos", []) if c.get("rodada") == rodada]


def _fixtures_rodada_do_rsc(rsc: str, rodada: int) -> list[dict]:
    fixtures = _extrair_json_array(rsc, "fixtures")
    if not fixtures:
        return []
    confrontos = _carregar_confrontos_rodada(rodada)
    chaves = {(c["mandante"], c["visitante"]) for c in confrontos}
    resultado: list[dict] = []
    for fx in fixtures:
        if not isinstance(fx, dict):
            continue
        home, away = fx.get("home", ""), fx.get("away", "")
        if _chave_confronto(home, away) in chaves:
            resultado.append({
                "fixture_id": fx.get("id"),
                "home": home,
                "away": away,
                "date": fx.get("date", ""),
                "grupo": fx.get("group", ""),
            })
    return resultado


def _carregar_cache_eventos() -> dict[tuple[str, str], int]:
    if not CAMINHO_EVENTOS.exists():
        return {}
    try:
        with CAMINHO_EVENTOS.open(encoding="utf-8") as f:
            bruto = json.load(f)
        cache: dict[tuple[str, str], int] = {}
        for ev in bruto.get("eventos", bruto if isinstance(bruto, list) else []):
            if not isinstance(ev, dict) or "id" not in ev:
                continue
            cache[_chave_confronto(ev.get("home", ""), ev.get("away", ""))] = int(ev["id"])
        return cache
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _salvar_cache_eventos(eventos: list[dict]) -> None:
    CAMINHO_EVENTOS.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "rodada": RODADA_ALVO,
        "eventos": eventos,
    }
    with CAMINHO_EVENTOS.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Cache eventos salvo: %d partidas -> %s", len(eventos), CAMINHO_EVENTOS)


def _mapear_ids_eventos(pagina: Page, fixtures: list[dict], cache: dict[tuple[str, str], int]) -> list[dict]:
    """
    Associa cada fixture da rodada ao oddsEventId (66456xxx).
    Usa cache versionado + varredura na faixa conhecida quando necessário.
    """
    faltando: list[dict] = []
    mapeados: list[dict] = []

    for fx in fixtures:
        chave = _chave_confronto(fx["home"], fx["away"])
        eid = cache.get(chave)
        if eid:
            mapeados.append({**fx, "id": eid})
        else:
            faltando.append(fx)

    if not faltando:
        return mapeados

    logger.info("Descobrindo oddsEventId para %d partidas...", len(faltando))
    chaves_faltando = {_chave_confronto(f["home"], f["away"]) for f in faltando}
    novos: dict[tuple[str, str], int] = {}

    for eid in range(ODDS_ID_SCAN_MIN, ODDS_ID_SCAN_MAX):
        if not chaves_faltando:
            break
        if eid in cache.values():
            continue
        nome = _nome_evento_pagina(pagina, eid)
        if not nome:
            continue
        times = _times_do_nome_evento(nome)
        if not times:
            continue
        chave = _chave_confronto(times[0], times[1])
        if chave in chaves_faltando:
            novos[chave] = eid
            chaves_faltando.discard(chave)
            logger.info("  mapeado %d -> %s", eid, nome)

    for fx in faltando:
        chave = _chave_confronto(fx["home"], fx["away"])
        eid = novos.get(chave) or cache.get(chave)
        if eid:
            mapeados.append({**fx, "id": eid})
        else:
            logger.warning("Sem oddsEventId: %s vs %s", fx["home"], fx["away"])

    mapeados.sort(key=lambda e: e.get("date", ""))
    if mapeados:
        _salvar_cache_eventos([
            {"id": e["id"], "home": e["home"], "away": e["away"],
             "date": e.get("date", ""), "fixture_id": e.get("fixture_id")}
            for e in mapeados
        ])
    return mapeados[:MAX_EVENTOS]


def buscar_eventos(pagina: Page, rsc_wc2026: str = "") -> list[dict]:
    """
    Fonte primária: fixtures da página world-cup-2026 cruzadas com grupos_wc2026.
    Fallback mínimo: cache eventos_odds_rodada1.json.
    """
    fixtures = _fixtures_rodada_do_rsc(rsc_wc2026, RODADA_ALVO) if rsc_wc2026 else []
    cache = _carregar_cache_eventos()

    if fixtures:
        logger.info("Fixtures rodada %d no RSC: %d jogos", RODADA_ALVO, len(fixtures))
        eventos = _mapear_ids_eventos(pagina, fixtures, cache)
        if eventos:
            return eventos

    if cache:
        confrontos = _carregar_confrontos_rodada(RODADA_ALVO)
        chaves = {(c["mandante"], c["visitante"]) for c in confrontos}
        eventos = []
        for chave, eid in cache.items():
            if chave in chaves:
                eventos.append({"id": eid, "home": chave[0], "away": chave[1], "date": ""})
        if eventos:
            logger.info("Eventos via cache: %d partidas", len(eventos))
            return sorted(eventos, key=lambda e: e.get("date", str(e["id"])))[:MAX_EVENTOS]

    logger.error("Nenhum evento encontrado para rodada %d.", RODADA_ALVO)
    return []


# ══════════════════════════════════════════════════════════════════════════════
# [1] BANCO DE JOGADORES
# ══════════════════════════════════════════════════════════════════════════════


def _norm(texto: str) -> str:
    forma = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in forma if not unicodedata.combining(c)).lower().strip()


def _mapear_selecao(nome: str) -> str:
    forma = unicodedata.normalize("NFKD", nome)
    ascii_n = "".join(c for c in forma if not unicodedata.combining(c)).upper().strip()
    return ALIAS_TIMES.get(ascii_n, ascii_n)


def carregar_jogadores(caminho: Path) -> list[dict]:
    if not caminho.exists():
        logger.error("jogadores_mercado.json nao encontrado: %s", caminho)
        return []
    with caminho.open(encoding="utf-8") as f:
        dados: list[dict] = json.load(f)
    linha = [j for j in dados if j.get("posicao_id") in POSICOES_LINHA]
    logger.info("Banco: %d total, %d de linha", len(dados), len(linha))
    return linha


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


def extrair_odds_rsc(rsc_conteudo: str) -> dict[str, dict[str, tuple[float, str]]]:
    """
    Parseia o bloco "bookmakers":{ "Bet365":[{markets}...], ... } no RSC.
    Retorna melhor odd por jogador em goalscorer (g) e assist (a).
    """
    resultado: dict[str, dict[str, tuple[float, str]]] = {"g": {}, "a": {}}
    bookmakers = _extrair_json_object(rsc_conteudo, "bookmakers")
    if not bookmakers:
        logger.debug("Bloco bookmakers nao encontrado — fallback regex.")
        return _extrair_odds_rsc_regex(rsc_conteudo)

    for bk_name, mercados in bookmakers.items():
        if not isinstance(mercados, list):
            continue
        for mercado in mercados:
            if not isinstance(mercado, dict):
                continue
            sufixo = MERCADOS_RSC.get(mercado.get("name", ""))
            if sufixo is None:
                continue
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
                resultado[sufixo][label] = _melhor_odd(
                    resultado[sufixo].get(label), odds_val, str(bk_name)
                )

    logger.info("RSC parseado: %d goalscorer, %d assist", len(resultado["g"]), len(resultado["a"]))
    return resultado


def _extrair_odds_rsc_regex(rsc_conteudo: str) -> dict[str, dict[str, tuple[float, str]]]:
    """Fallback legado quando bookmakers JSON não está disponível."""
    resultado: dict[str, dict[str, tuple[float, str]]] = {"g": {}, "a": {}}
    pat_bk_mkt = re.compile(
        r'"([^"]{2,40})"\s*:\s*\[(?:[^\[\]]|\[[^\]]*\])*?"name"\s*:\s*"(Anytime Goalscorer|Player To Assist)"'
        r'\s*,\s*"updatedAt"\s*:\s*"[^"]+"\s*,\s*"odds"\s*:\s*(\[[^\]]+\])',
        re.DOTALL,
    )
    for match in pat_bk_mkt.finditer(rsc_conteudo):
        bk_name, nome_mercado, odds_raw = match.group(1), match.group(2), match.group(3)
        sufixo = MERCADOS_RSC[nome_mercado]
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
# [4] MATCHING POR EQUIPE
# ══════════════════════════════════════════════════════════════════════════════


def _score_fuzzy(a: str, b: str) -> int:
    na, nb = _norm(a), _norm(b)
    sort_r = fuzz.token_sort_ratio(na, nb)
    set_r  = fuzz.token_set_ratio(na, nb)
    # partial_ratio é muito agressivo para nomes compostos/abreviados;
    # só usamos se o resultado das outras métricas já for razoável
    partial = fuzz.partial_ratio(na, nb)
    base = max(sort_r, set_r)
    # Aplica partial_ratio apenas como bônus moderado
    return int(base * 0.7 + partial * 0.3) if base >= 50 else base


def casar_jogador_na_equipe(
    nome_bk: str,
    pool: list[dict],
) -> tuple[dict | None, int, list[tuple[int, dict]]]:
    # 1. Verificação de alias explícito (100% confiança)
    chave = _norm(nome_bk)
    if chave in ALIAS_JOGADORES:
        alvo_id = ALIAS_JOGADORES[chave]
        for j in pool:
            if j.get("atleta_id") == alvo_id:
                return j, 100, [(100, j)]

    # 2. Fuzzy matching
    scores = [(max(_score_fuzzy(nome_bk, j.get("apelido", "")),
                   _score_fuzzy(nome_bk, j.get("nome", ""))), j)
              for j in pool]
    scores.sort(key=lambda x: x[0], reverse=True)
    top3 = scores[:3]
    if not top3:
        return None, 0, []
    melhor_score, melhor_j = top3[0]
    if melhor_score >= THRESHOLD_REVIEW:
        return melhor_j, melhor_score, top3
    return None, melhor_score, top3


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


def _navegar_clicar_player(pagina: Page) -> None:
    """Player → Anytime Goalscorer + Player To Assist para RSC completo."""
    for seletor in ["button:has-text('Player')", "a:has-text('Player')",
                    "[role='tab']:has-text('Player')"]:
        try:
            el = pagina.locator(seletor).first
            if el.is_visible(timeout=3000):
                el.click(timeout=3000)
                pagina.wait_for_timeout(random.randint(1500, 2500))
                break
        except Exception:
            pass

    for label in ("Anytime Goalscorer", "Player To Assist"):
        for seletor in [f"button:has-text('{label}')", f"a:has-text('{label}')",
                        f"[role='tab']:has-text('{label}')"]:
            try:
                el = pagina.locator(seletor).first
                if el.is_visible(timeout=2500):
                    el.click(timeout=3000)
                    pagina.wait_for_timeout(random.randint(1200, 2000))
                    break
            except Exception:
                pass


def processar_evento(
    evento: dict,
    pagina: Page,
    jogadores: list[dict],
    resultado: dict[str, dict],
    relatorio: Relatorio,
    rsc_acumulado: list[str],
) -> int:
    eid = evento["id"]
    home, away = evento.get("home", "?"), evento.get("away", "?")
    desc = f"{home} vs {away}"

    logger.info("Processando: %s (id=%d)", desc, eid)

    # Limpa o acumulador de RSC para este evento
    tamanho_antes = len(rsc_acumulado)

    url = _url_evento(eid)
    try:
        pagina.goto(url, timeout=TIMEOUT_PAGINA, wait_until="domcontentloaded")
    except Exception as e:
        logger.warning("Navegacao falhou para %s: %s", desc, e)
        return 0

    pagina.wait_for_timeout(random.randint(4000, 7000))
    _navegar_clicar_player(pagina)

    # Aguarda o RSC de odds chegar (via ?_rsc= responses)
    # O click dispara o fetch; precisamos esperar a resposta
    for _ in range(6):  # até ~18s
        pagina.wait_for_timeout(3000)
        novos = rsc_acumulado[tamanho_antes:]
        total_novos = sum(len(c) for c in novos)
        if total_novos > 50_000:  # recebeu dados substanciais
            logger.info("RSC via network: %d chunks, %d chars", len(novos), total_novos)
            break
    else:
        logger.debug("RSC network incompleto, tentando via DOM...")

    # Une: RSC da rede + scripts inline do DOM
    rsc_rede = "\n".join(rsc_acumulado[tamanho_antes:])
    rsc_dom  = _rsc_de_pagina(pagina)
    rsc      = rsc_rede + "\n" + rsc_dom

    if not rsc.strip():
        logger.warning("RSC vazio para %s — nenhum dado extraido.", desc)
        return 0

    logger.info("RSC total: %d chars (rede=%d, dom=%d)", len(rsc), len(rsc_rede), len(rsc_dom))

    # Parseia odds
    odds_bruto = extrair_odds_rsc(rsc)
    odds_g = consolidar_nomes_odds(odds_bruto["g"])
    odds_a = consolidar_nomes_odds(odds_bruto["a"])

    if not odds_g and not odds_a:
        logger.warning("Nenhuma odd extraida para %s.", desc)
        return 0

    logger.info("  %s: %d goalscorer, %d assist", desc, len(odds_g), len(odds_a))

    # Pools de jogadores das duas equipes
    pool_home = jogadores_da_equipe(jogadores, _mapear_selecao(home))
    pool_away = jogadores_da_equipe(jogadores, _mapear_selecao(away))

    logger.info("  Pools: %s=%d | %s=%d",
                _mapear_selecao(home), len(pool_home),
                _mapear_selecao(away), len(pool_away))

    # Reúne todos os nomes dos jogadores (union de goalscorer + assist)
    todos_nomes = set(odds_g) | set(odds_a)
    adicionados = 0

    for nome_bk in sorted(todos_nomes):
        # Decide qual pool usar baseando-se em qual tem melhor match
        melhor_j: dict | None = None
        melhor_score = 0
        melhor_top3: list = []

        for pool in (pool_home, pool_away):
            if not pool:
                continue
            j, s, t3 = casar_jogador_na_equipe(nome_bk, pool)
            if j is not None and s > melhor_score:
                melhor_j, melhor_score, melhor_top3 = j, s, t3

        if melhor_j is None:
            relatorio.no_match(nome_bk, melhor_score, melhor_top3, desc)
            continue

        relatorio.match(nome_bk, melhor_j, melhor_score, desc)

        atleta_id_str = str(melhor_j["atleta_id"])
        existente = resultado.get(atleta_id_str)
        if existente and existente.get("event_id") != eid:
            continue

        entrada: dict[str, Any] = {"event_id": eid}

        if nome_bk in odds_g:
            g_odd, g_bk = odds_g[nome_bk]
            entrada["g_pct"]  = _prob(g_odd)
            entrada["casa_g"] = g_bk
            entrada["odds_g"] = g_odd
        else:
            entrada["g_pct"]  = None
            entrada["casa_g"] = None
            entrada["odds_g"] = None

        if nome_bk in odds_a:
            a_odd, a_bk = odds_a[nome_bk]
            entrada["a_pct"]  = _prob(a_odd)
            entrada["casa_a"] = a_bk
            entrada["odds_a"] = a_odd
        else:
            entrada["a_pct"]  = None
            entrada["casa_a"] = None
            entrada["odds_a"] = None

        resultado[atleta_id_str] = entrada
        adicionados += 1

    logger.info("  %d atletas adicionados.", adicionados)
    return adicionados


# ══════════════════════════════════════════════════════════════════════════════
# [7] ORQUESTRADOR
# ══════════════════════════════════════════════════════════════════════════════


def _headless() -> bool:
    return os.environ.get("ODDSNOTIFIER_HEADLESS", "true").strip().lower() not in ("0", "false", "no", "off")


def executar() -> None:
    logger.info("=== Scraper Odds WC2026 iniciado ===")

    jogadores = carregar_jogadores(CAMINHO_MERCADO)
    if not jogadores:
        return

    # Rescrape completo da rodada (sem merge de execuções anteriores)
    resultado: dict[str, dict] = {}

    relatorio = Relatorio()
    total_add = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=_headless(),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1440,900",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            "window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };"
            "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });"
        )
        pagina = ctx.new_page()

        # Intercepta respostas ?_rsc= (RSC flight chunks via HTTP)
        rsc_acumulado: list[str] = []

        def _capturar_rsc(resp) -> None:
            if "oddsnotifier" not in resp.url:
                return
            ct = resp.headers.get("content-type", "")
            if "x-component" not in ct:
                return
            try:
                texto = resp.text()
                if texto:
                    rsc_acumulado.append(texto)
                    logger.debug("RSC resp %d chars: %s", len(texto), resp.url[:80])
            except Exception:
                pass

        pagina.on("response", _capturar_rsc)

        try:
            # Warm-up + fixtures WC2026
            logger.info("Warm-up: %s", URL_WC2026)
            pagina.goto(URL_WC2026, timeout=30_000, wait_until="domcontentloaded")
            pagina.wait_for_timeout(random.randint(5000, 8000))
            rsc_wc2026 = _rsc_de_pagina(pagina) + "\n".join(rsc_acumulado)

            eventos = buscar_eventos(pagina, rsc_wc2026)
            if not eventos:
                logger.error("Abortando: nenhum evento para rodada %d.", RODADA_ALVO)
                return
            for idx, evento in enumerate(eventos, start=1):
                logger.info("[%d/%d] %s vs %s", idx, len(eventos),
                            evento["home"], evento["away"])
                n = processar_evento(evento, pagina, jogadores, resultado, relatorio, rsc_acumulado)
                total_add += n

                if idx < len(eventos):
                    delay = random.uniform(DELAY_MIN, DELAY_MAX)
                    logger.info("Aguardando %.0fs...", delay)
                    time.sleep(delay)

        finally:
            try:
                ctx.close()
                browser.close()
            except Exception:
                pass

    logger.info("Scraping concluido: %d atletas total", len(resultado))

    relatorio.imprimir()
    _salvar(resultado)


def _salvar(odds: dict[str, dict]) -> None:
    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "atualizado_em": datetime.now(tz=timezone.utc).isoformat(),
        "total_jogadores": len(odds),
        "odds": odds,
    }
    with CAMINHO_SAIDA.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    logger.info("Salvo: %d atletas -> %s", len(odds), CAMINHO_SAIDA)


if __name__ == "__main__":
    executar()
