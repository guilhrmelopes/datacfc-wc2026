"""
Registro de aliases OddsNotifier → atleta_id Cartola.

Arquivo: frontend/public/data/mapeamento_jogadores_odds.json

Resolução (prioridade):
  1. aliases_odds por atleta_id (desambigua homônimos no elenco)
  2. fuzzy / tokens em matching_cartola.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from scrapers.matching_cartola import limpar_nome_fonte, normalizar_texto

logger = logging.getLogger(__name__)

_RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_MAPEAMENTO = _RAIZ / "frontend" / "public" / "data" / "mapeamento_jogadores_odds.json"

SCORE_ALIAS = 100
MIN_SCORE_APRENDER = 95

_cache: dict | None = None


def _vazio() -> dict:
    return {"versao": 1, "por_atleta_id": {}}


def carregar_mapeamento(*, recarregar: bool = False) -> dict:
    global _cache
    if _cache is not None and not recarregar:
        return _cache
    if not CAMINHO_MAPEAMENTO.is_file():
        _cache = _vazio()
        return _cache
    try:
        bruto = json.loads(CAMINHO_MAPEAMENTO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Falha ao ler mapeamento odds: %s", exc)
        _cache = _vazio()
        return _cache
    if not isinstance(bruto, dict):
        _cache = _vazio()
        return _cache
    bruto.setdefault("versao", 1)
    bruto.setdefault("por_atleta_id", {})
    _cache = bruto
    return _cache


def _chave_nome(nome: str) -> str:
    return normalizar_texto(limpar_nome_fonte(nome))


def _aliases_normalizados(entry: dict) -> set[str]:
    out: set[str] = set()
    for bruto in entry.get("aliases_odds") or []:
        if bruto:
            out.add(_chave_nome(str(bruto)))
    return out


def jogador_por_alias(
    nome_fonte: str,
    candidatos: list[dict],
) -> tuple[dict | None, int]:
    """
    Resolve nome via registro por atleta_id, restrito ao pool de candidatos.
    Retorna (jogador, SCORE_ALIAS) ou (None, 0).
    """
    chave = _chave_nome(nome_fonte)
    if not chave or not candidatos:
        return None, 0

    ids_pool = {int(j.get("atleta_id") or 0) for j in candidatos}
    ids_pool.discard(0)
    por_atleta = carregar_mapeamento().get("por_atleta_id") or {}

    matches: list[int] = []
    for aid_str, entry in por_atleta.items():
        if not isinstance(entry, dict):
            continue
        try:
            aid = int(aid_str)
        except (TypeError, ValueError):
            continue
        if aid not in ids_pool:
            continue
        if chave in _aliases_normalizados(entry):
            matches.append(aid)

    if len(matches) != 1:
        return None, 0

    alvo = matches[0]
    for jog in candidatos:
        if int(jog.get("atleta_id") or 0) == alvo:
            return jog, SCORE_ALIAS
    return None, 0


def alias_aponta_para_outro(
    nome_fonte: str,
    atleta_id: int,
    candidatos: list[dict],
) -> bool:
    """True se o alias existe e aponta para outro jogador do pool."""
    jog, score = jogador_por_alias(nome_fonte, candidatos)
    return score == SCORE_ALIAS and int(jog["atleta_id"]) != int(atleta_id)


def registrar_alias_aprendido(
    nome_fonte: str,
    jogador: dict,
    score: int,
    *,
    min_score: int = MIN_SCORE_APRENDER,
) -> bool:
    """
    Persiste alias OddsNotifier → atleta_id quando match confiável.
    Não sobrescreve aliases existentes de outro jogador.
    """
    if score < min_score:
        return False

    nome_limpo = limpar_nome_fonte(nome_fonte).strip()
    if not nome_limpo or len(nome_limpo) < 3:
        return False

    aid = int(jogador.get("atleta_id") or 0)
    if not aid:
        return False

    payload = carregar_mapeamento()
    por_atleta = payload.setdefault("por_atleta_id", {})
    chave = str(aid)
    entry = por_atleta.setdefault(chave, {})
    entry["sigla"] = (jogador.get("sigla") or entry.get("sigla") or "").upper()
    entry["apelido"] = jogador.get("apelido") or entry.get("apelido") or ""

    aliases: list[str] = list(entry.get("aliases_odds") or [])
    norm_existentes = {_chave_nome(a) for a in aliases}

    for outro_id, outro in por_atleta.items():
        if outro_id == chave:
            continue
        if _chave_nome(nome_limpo) in _aliases_normalizados(outro if isinstance(outro, dict) else {}):
            return False

    chave_nova = _chave_nome(nome_limpo)
    if chave_nova in norm_existentes:
        return False

    aliases.append(nome_limpo)
    entry["aliases_odds"] = aliases
    salvar_mapeamento(payload)
    logger.info("Alias aprendido: %r -> atleta_id=%d", nome_limpo, aid)
    return True


def salvar_mapeamento(payload: dict) -> None:
    global _cache
    CAMINHO_MAPEAMENTO.parent.mkdir(parents=True, exist_ok=True)
    with CAMINHO_MAPEAMENTO.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _cache = payload
    logger.info("Mapeamento odds salvo: %d atletas.", len(payload.get("por_atleta_id", {})))
