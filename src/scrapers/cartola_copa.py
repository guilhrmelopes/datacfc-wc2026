"""Scraper da API oficial Cartola FC Copa (/copa/)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.paths import obter_pasta_dados_brutos, obter_pasta_logs

BASE_URL = "https://api.cartola.globo.com"

URL_STATUS = f"{BASE_URL}/copa/mercado/status"
URL_PONTUADOS = f"{BASE_URL}/copa/atletas/pontuados"
URL_MERCADO = f"{BASE_URL}/copa/atletas/mercado"
URL_PARTIDAS = f"{BASE_URL}/copa/partidas"

ENDPOINTS_COPA = (
    URL_STATUS,
    URL_PONTUADOS,
    URL_MERCADO,
    URL_PARTIDAS,
)

INTERVALO_REQUISICOES_S = 1.0
TIMEOUT_S = 30
MAX_TENTATIVAS = 2

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

POSICAO_PARA_BUCKET: dict[int, str] = {
    1: "GOL",
    2: "LAT",
    3: "ZAG",
    4: "MEI",
    5: "ATA",
}


@dataclass
class DadosCartolaCopa:
    status: dict[str, Any]
    pontuados: dict[str, Any]
    mercado: dict[str, Any]
    partidas: dict[str, Any]
    obtido_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    avisos: list[str] = field(default_factory=list)


def configurar_logger() -> logging.Logger:
    pasta_logs = obter_pasta_logs()
    pasta_logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("cartola_copa")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler_arquivo = logging.FileHandler(
        pasta_logs / "cartola_copa.log",
        encoding="utf-8",
    )
    handler_arquivo.setFormatter(formato)
    handler_console = logging.StreamHandler()
    handler_console.setFormatter(formato)
    logger.addHandler(handler_arquivo)
    logger.addHandler(handler_console)
    return logger


class _RateLimiter:
    def __init__(self, intervalo: float) -> None:
        self.intervalo = intervalo
        self._ultima = 0.0

    def aguardar(self) -> None:
        agora = time.monotonic()
        delta = agora - self._ultima
        if self._ultima and delta < self.intervalo:
            time.sleep(self.intervalo - delta)
        self._ultima = time.monotonic()


_limiter = _RateLimiter(INTERVALO_REQUISICOES_S)


def _fetch_json(url: str, logger: logging.Logger) -> dict[str, Any]:
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        _limiter.aguardar()
        req = urllib.request.Request(url, headers=CABECALHOS)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                payload = json.loads(resp.read())
            if not isinstance(payload, dict):
                raise ValueError(f"Resposta inesperada de {url}")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as erro:
            if tentativa >= MAX_TENTATIVAS:
                logger.error("Falha ao buscar %s: %s", url, erro)
                raise
            logger.warning("Tentativa %s/%s falhou para %s: %s", tentativa, MAX_TENTATIVAS, url, erro)
            time.sleep(INTERVALO_REQUISICOES_S)
    raise RuntimeError(f"Não foi possível obter {url}")


def payload_tem_selecoes(payload: dict[str, Any], *, min_clubes: int = 40) -> bool:
    clubes = payload.get("clubes") or {}
    if len(clubes) < min_clubes:
        return False
    abrevs = {
        str(info.get("abreviacao", "")).upper()
        for info in clubes.values()
        if isinstance(info, dict)
    }
    return bool(abrevs)


def contar_atletas(payload: dict[str, Any]) -> int:
    atletas = payload.get("atletas")
    if isinstance(atletas, list):
        return len(atletas)
    if isinstance(atletas, dict):
        return len(atletas)
    return 0


def persistir_cache(payloads: dict[str, Any], pasta: Path | None = None) -> Path:
    destino = pasta or obter_pasta_dados_brutos()
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / "cartola_copa_latest.json"
    caminho.write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return caminho


def buscar_dados_cartola_copa(
    *,
    persistir: bool = True,
    logger: logging.Logger | None = None,
) -> DadosCartolaCopa:
    """Busca apenas endpoints /copa/ com seleções (sem Brasileirão)."""
    log = logger or configurar_logger()
    avisos: list[str] = []

    log.info("Cartola Copa — iniciando raspagem (intervalo %.1fs)", INTERVALO_REQUISICOES_S)

    status = _fetch_json(URL_STATUS, log)
    pontuados = _fetch_json(URL_PONTUADOS, log)
    mercado = _fetch_json(URL_MERCADO, log)
    partidas = _fetch_json(URL_PARTIDAS, log)

    if not payload_tem_selecoes(partidas):
        avisos.append("/copa/partidas não retornou clubes de seleções.")
    if not payload_tem_selecoes(pontuados, min_clubes=8):
        avisos.append("/copa/atletas/pontuados sem seleções suficientes.")
    if not payload_tem_selecoes(mercado):
        avisos.append("/copa/atletas/mercado sem seleções.")

    dados = DadosCartolaCopa(
        status=status,
        pontuados=pontuados,
        mercado=mercado,
        partidas=partidas,
        avisos=avisos,
    )

    log.info(
        "Cartola Copa — rodada %s | pontuados %s | mercado %s | partidas %s | encerradas %s",
        status.get("rodada_atual"),
        len((pontuados.get("atletas") or {})),
        contar_atletas(mercado),
        len(partidas.get("partidas") or []),
        sum(
            1
            for p in (partidas.get("partidas") or [])
            if p.get("status_transmissao_tr") == "ENCERRADA"
        ),
    )
    for msg in avisos:
        log.warning(msg)

    if persistir:
        caminho = persistir_cache(
            {
                "obtido_em": dados.obtido_em,
                "endpoints": list(ENDPOINTS_COPA),
                "status": status,
                "pontuados": pontuados,
                "mercado": mercado,
                "partidas": partidas,
                "avisos": avisos,
            }
        )
        log.info("Cache salvo em %s", caminho)

    return dados


def main() -> None:
    dados = buscar_dados_cartola_copa()
    print(
        json.dumps(
            {
                "rodada_atual": dados.status.get("rodada_atual"),
                "status_mercado": dados.status.get("status_mercado"),
                "bola_rolando": dados.status.get("bola_rolando"),
                "pontuados": len(dados.pontuados.get("atletas") or {}),
                "mercado_selecoes": contar_atletas(dados.mercado),
                "partidas": len(dados.partidas.get("partidas") or []),
                "avisos": dados.avisos,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
