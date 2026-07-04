"""
Utilitário Playwright para interceptação de respostas de rede do hub.oddsnotifier.io.

Espelha o padrão de interceptacao_rede_sofascore.py: o browser real navega até a
página da partida, o Cloudflare Turnstile é resolvido automaticamente pelo JS do
site, e capturamos a resposta de /api/odds/{eventId} via page.on("response").
"""

import json
import logging
import os
import random
import re
import time
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, Response

# ─────────────────────────────── Constantes de domínio ───────────────────────

DOMINIO_ODDSNOTIFIER = "hub.oddsnotifier.io"
DOMINIOS_HUB_ODDS = frozenset({
    "hub.oddsnotifier.io",
    "www.oddshub.io",
    "oddshub.io",
})
CAMINHO_API_ODDS = "/api/odds/"

# Também capturamos estes sub-endpoints (usados quando se clica em abas específicas)
CAMINHOS_API_EVENTOS_PLAYER: tuple[str, ...] = (
    "/api/events/",  # /api/events/{id}/anytime-goalscorer  etc.
)

# ──────────────────────────── Script de evasão de automação ──────────────────
# Oculta os rastros do Playwright/Chromium que detectores como Cloudflare usam
# para identificar browsers headless automáticos.

SCRIPT_EVASAO_AUTOMACAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', length: 1 },
        { name: 'Chrome PDF Viewer', length: 1 },
        { name: 'Native Client', length: 2 },
    ],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
});
Object.defineProperty(navigator, 'permissions', {
    get: () => ({
        query: () => Promise.resolve({ state: 'granted' }),
    }),
});
"""

USER_AGENT_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ───────────────────────────────── Helpers de URL ─────────────────────────────


def _url_eh_api_odds(url: str) -> bool:
    """
    Retorna True para:
      • /api/odds/{eventId}
      • /api/events/{eventId}/anytime-goalscorer
      • /api/events/{eventId}/player-props
      • /api/events/{eventId}/goalscorer
      • /api/events/{eventId}/assist
    """
    parsed = urlparse(url)
    if parsed.netloc not in DOMINIOS_HUB_ODDS:
        return False
    path = parsed.path
    if re.search(r"/api/odds/\d+$", path):
        return True
    if re.search(r"/api/events/\d+/(anytime-goalscorer|player-props|goalscorer|assist|scorer|players)", path):
        return True
    return False


def _extrair_event_id(url: str) -> str | None:
    """Extrai event_id de /api/odds/{id} ou /api/events/{id}/..."""
    match = re.search(r"/api/odds/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"/api/events/(\d+)/", url)
    return match.group(1) if match else None


def slugificar_nome_time(nome: str) -> str:
    """
    Converte o nome de um time para slug de URL.
    "Saudi Arabia" → "saudi-arabia" | "IR Iran" → "ir-iran"
    """
    slug = nome.lower()
    # Remove caracteres não alfanuméricos (exceto hífens e espaços)
    slug = re.sub(r"[^\w\s-]", "", slug)
    # Colapsa espaços e underscores em hífens
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug


def construir_url_partida(evento: dict) -> str:
    """
    Monta a URL da página da partida no hub.oddsnotifier.io.

    Padrão real (confirmado pelo usuário):
      /{league_slug}/{eventId}
    Exemplo: /football/international-world-cup/66456928
    """
    sport_slug = evento.get("sport", {}).get("slug", "football")
    league_slug = evento.get("league", {}).get("slug", "international-world-cup")
    event_id = evento["id"]
    return (
        f"https://www.oddshub.io"
        f"/{sport_slug}/{league_slug}/{event_id}"
    )


# ──────────────────────────── Armazenamento de capturas ──────────────────────


class ArmazenamentoCapturaOdds:
    """
    Listener de respostas de rede que armazena payloads JSON do endpoint de odds.

    Uso:
        armazenamento = ArmazenamentoCapturaOdds(logger)
        armazenamento.vincular_pagina(pagina)
        # ... navegar ...
        dados = armazenamento.obter_odds_evento(event_id)
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._payloads: dict[str, Any] = {}
        self._urls_capturadas: list[str] = []

    def vincular_pagina(self, pagina: Page) -> None:
        """Registra o handler de resposta na página Playwright."""
        pagina.on("response", self._processar_resposta)

    def _processar_resposta(self, resposta: Response) -> None:
        if not _url_eh_api_odds(resposta.url):
            return
        if resposta.status != 200:
            self._logger.debug(
                "Odds endpoint retornou HTTP %d para %s", resposta.status, resposta.url
            )
            return
        tipo_conteudo = (resposta.headers.get("content-type") or "").lower()
        if "json" not in tipo_conteudo:
            return

        event_id = _extrair_event_id(resposta.url)
        if event_id is None:
            return

        try:
            corpo = resposta.json()
        except Exception:
            try:
                corpo = json.loads(resposta.body())
            except Exception as erro:
                self._logger.debug(
                    "Falha ao parsear JSON de odds (event_id=%s): %s", event_id, erro
                )
                return

        anterior = self._payloads.get(event_id)
        if isinstance(anterior, dict) and isinstance(corpo, dict):
            mesclado = {**anterior, **corpo}
            if "bookmakers" in anterior and "bookmakers" in corpo:
                bks = dict(anterior.get("bookmakers") or {})
                bks.update(corpo.get("bookmakers") or {})
                mesclado["bookmakers"] = bks
            corpo = mesclado

        self._payloads[event_id] = corpo
        self._urls_capturadas.append(resposta.url)
        self._logger.info(
            "✓ Odds capturadas: event_id=%s (%d registros top-level)",
            event_id,
            len(corpo) if isinstance(corpo, (list, dict)) else 0,
        )

    def obter_odds_evento(self, event_id: int | str) -> Any | None:
        """Retorna o payload capturado para um event_id, ou None se não capturado."""
        return self._payloads.get(str(event_id))

    def quantidade_capturas(self) -> int:
        return len(self._urls_capturadas)


# ───────────────────────────── Criação do browser ─────────────────────────────


def navegador_deve_ser_headless() -> bool:
    """
    Por padrão usa headless=True (adequado para GitHub Actions).
    Defina ODDSNOTIFIER_HEADLESS=false para inspecionar localmente.
    """
    valor = os.environ.get("ODDSNOTIFIER_HEADLESS", "true").strip().lower()
    return valor not in ("0", "false", "no", "off")


def criar_navegador_chromium(
    playwright: Playwright,
) -> tuple[Browser, BrowserContext, Page]:
    """
    Instancia Chromium com flags anti-detecção e inicializa o script de evasão.

    O browser é configurado para simular um Windows 10 + Chrome 131 real,
    com locale pt-BR e timezone de São Paulo para reduzir fingerprint anômalo.
    """
    opcoes: dict[str, Any] = {
        "headless": navegador_deve_ser_headless(),
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-infobars",
            "--disable-gpu",
            "--window-size=1440,900",
        ],
    }

    navegador = playwright.chromium.launch(**opcoes)
    contexto = navegador.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        user_agent=USER_AGENT_CHROME,
        viewport={"width": 1440, "height": 900},
        extra_http_headers={
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    contexto.add_init_script(SCRIPT_EVASAO_AUTOMACAO)
    pagina = contexto.new_page()
    return navegador, contexto, pagina


# ─────────────────────────────── Helpers de navegação ────────────────────────


def espera_aleatoria(
    minimo_segundos: float = 3.0,
    maximo_segundos: float = 8.0,
) -> None:
    """Delay aleatório para simular comportamento humano entre navegações."""
    time.sleep(random.uniform(minimo_segundos, maximo_segundos))


def _tentar_clicar_aba_player(pagina: Page) -> bool:
    """
    Replica o fluxo manual do usuário para carregar as odds de jogadores:

      1. Clica em "Player"  (aba de categoria na página da partida)
      2. Clica em "Anytime Goalscorer" (sub-aba) — dispara /api/odds/{eventId}

    "Markets" é apenas um label de seção (não clicável).
    Retorna True se os dois cliques foram realizados.
    """
    # ── Passo 1: clicar em "Player" ──────────────────────────────────────────
    clicou_player = False
    for seletor_player in [
        "button:has-text('Player')",
        "a:has-text('Player')",
        "[role='tab']:has-text('Player')",
        "li:has-text('Player')",
        "span:has-text('Player')",
    ]:
        try:
            el = pagina.locator(seletor_player).first
            if el.count() > 0 and el.is_visible(timeout=2000):
                el.click(timeout=3000)
                pagina.wait_for_timeout(random.randint(1200, 2500))
                clicou_player = True
                break
        except Exception:
            continue

    if not clicou_player:
        return False

    # ── Passo 2: clicar em "Anytime Goalscorer" ──────────────────────────────
    for seletor_goal in [
        "button:has-text('Anytime Goalscorer')",
        "a:has-text('Anytime Goalscorer')",
        "[role='tab']:has-text('Anytime Goalscorer')",
        "li:has-text('Anytime Goalscorer')",
        "span:has-text('Anytime Goalscorer')",
        # fallback: apenas "Anytime"
        "button:has-text('Anytime')",
        "a:has-text('Anytime')",
    ]:
        try:
            el = pagina.locator(seletor_goal).first
            if el.count() > 0 and el.is_visible(timeout=2000):
                el.click(timeout=3000)
                pagina.wait_for_timeout(random.randint(1500, 3000))
                return True
        except Exception:
            continue

    # Clicou em Player mas não encontrou Anytime Goalscorer —
    # ainda assim pode ter disparado a chamada de API
    return True


def aguardar_odds_capturadas(
    pagina: Page,
    armazenamento: ArmazenamentoCapturaOdds,
    event_id: int,
    timeout_segundos: float = 45.0,
    intervalo_ms: int = 600,
) -> bool:
    """
    Aguarda as odds do evento serem capturadas pelo listener de rede.

    Fluxo (baseado no fluxo manual confirmado pelo usuário):
      1. Espera inicial de ~5s para a página carregar os elementos
      2. Clica em "Player" → depois "Anytime Goalscorer"
         → dispara /api/odds/{eventId}
      3. Aguarda até 8s pela resposta da API
      4. Se não capturou, tenta de novo (até esgotar timeout total)
    """
    inicio = time.monotonic()
    ciclos = 0
    tentativas_clique = 0
    MAX_TENTATIVAS_CLIQUE = 3

    while time.monotonic() - inicio < timeout_segundos:
        if armazenamento.obter_odds_evento(event_id) is not None:
            return True

        ciclos += 1
        pagina.wait_for_timeout(intervalo_ms)

        # Espera 5s para a página inicializar antes do primeiro clique
        tempo_decorrido = time.monotonic() - inicio
        if tempo_decorrido > 5 and tentativas_clique < MAX_TENTATIVAS_CLIQUE:
            # Intervalo mínimo de 10s entre tentativas de clique
            if tentativas_clique == 0 or tempo_decorrido > 5 + tentativas_clique * 12:
                clicou = _tentar_clicar_aba_player(pagina)
                tentativas_clique += 1
                if clicou:
                    # Aguarda resposta da API após clique
                    pagina.wait_for_timeout(8000)
                    if armazenamento.obter_odds_evento(event_id) is not None:
                        return True

        # Scroll periódico para simular leitura e ativar lazy-load
        if ciclos % 10 == 0:
            try:
                pagina.mouse.wheel(0, random.randint(200, 500))
                pagina.wait_for_timeout(random.randint(300, 600))
            except Exception:
                pass

    return False


def navegar_pagina_aquecimento(pagina: Page, logger: logging.Logger) -> None:
    """
    Navega à página da competição antes de acessar partidas individuais.

    Isso resolve o Cloudflare Turnstile inicial e estabelece cookies de sessão
    que serão reaproveitados nas navegações subsequentes dentro do mesmo contexto.
    """
    url_competicao = "https://hub.oddsnotifier.io/football/international-world-cup"
    logger.info("Aquecimento: navegando para %s", url_competicao)
    try:
        pagina.goto(url_competicao, timeout=30_000, wait_until="domcontentloaded")
        # Espera a página renderizar e o Turnstile processar
        pagina.wait_for_timeout(random.randint(5_000, 9_000))
        # Scroll leve para simular leitura
        pagina.mouse.wheel(0, random.randint(400, 800))
        pagina.wait_for_timeout(random.randint(2_000, 4_000))
        logger.info("Aquecimento concluído.")
    except Exception as erro:
        logger.warning("Aquecimento falhou (não crítico): %s", erro)
