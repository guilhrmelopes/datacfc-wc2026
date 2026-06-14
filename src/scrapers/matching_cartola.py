"""
Matching de nomes externos (OddsNotifier, FotMob, etc.) → jogadores Cartola.

Estratégia em camadas (sem aliases hardcoded por jogador):
  1. Normalização Unicode + tokens expandidos (jr/junior, vini/vinicius)
  2. Substring / subset de tokens / interseção parcial
  3. Sobrenome isolado e formato "Inicial Sobrenome"
  4. Fuzzy (SequenceMatcher + Jaccard de tokens) ≥ 85
  5. Atribuição um-a-um por score máximo (evita duplicar atleta_id)
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Expansão bidirecional de abreviações comuns.
_SINONIMOS_TOKEN: dict[str, str] = {
    "jr": "junior",
    "junior": "jr",
    "vini": "vinicius",
    "vinicius": "vini",
    "gabigol": "gabriel",
    "gabriel": "gabigol",
}

_PAT_SUFIXO_MERCADO = re.compile(
    r"\s*\((Score\s+Or\s+Assist|Score|Assist)\)\s*(?:\(\d+\))?\s*$",
    re.IGNORECASE,
)
_PAT_SUFIXO_NUM = re.compile(r"\s*\(\d+\)\s*$")

MIN_SCORE_ATRIBUICAO = 70
MIN_SCORE_LACUNA = 60


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto.lower())
    return " ".join(texto.split())


def _tokens(texto: str) -> list[str]:
    return normalizar_texto(texto).split()


def _tokens_expandidos(texto: str) -> set[str]:
    tokens = set(_tokens(texto))
    for token in list(tokens):
        par = _SINONIMOS_TOKEN.get(token)
        if par:
            tokens.add(par)
    partes = _tokens(texto)
    prefixos = {"al", "el", "de", "da", "del", "van", "von", "bin", "ibn"}
    if len(partes) >= 2 and partes[0] in prefixos:
        tokens.add(f"{partes[0]} {partes[1]}")
    if len(partes) >= 3 and partes[0] in prefixos:
        tokens.add(f"{partes[0]} {partes[1]} {partes[2]}")
    return tokens


def limpar_nome_fonte(nome: str) -> str:
    """Remove sufixos OddsNotifier: (Score), (Assist), (Score Or Assist), (1)."""
    bruto = (nome or "").strip()
    bruto = _PAT_SUFIXO_MERCADO.sub("", bruto)
    bruto = _PAT_SUFIXO_NUM.sub("", bruto)
    return bruto.strip()


def _score_fuzzy_nome(a: str, b: str) -> int:
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


def pontuar_match(nome_fonte: str, jogador: dict) -> int:
    """Melhor score entre apelido e nome completo do Cartola."""
    nome_limpo = limpar_nome_fonte(nome_fonte)
    nome_completo = (jogador.get("nome") or jogador.get("apelido") or "").strip()
    melhor = 0
    for campo in ("apelido", "nome"):
        alvo = jogador.get(campo) or ""
        if alvo:
            melhor = max(melhor, _pontuar_par(nome_limpo, alvo, nome_completo))
    return melhor


def _bonus_inicial_sobrenome(nome_fonte: str, nome_cartola: str, nome_completo: str) -> int:
    """
    Desambigua "L. Martínez" / "Martínez L" quando há homônimos no elenco.
    Retorna bônus/penalidade aplicado ao score base.
    """
    tokens_f = _tokens(limpar_nome_fonte(nome_fonte))
    if len(tokens_f) != 2:
        return 0

    a, b = tokens_f[0], tokens_f[1]
    if len(a) == 1 and len(b) > 1:
        inicial, sobrenome = a, b
    elif len(b) == 1 and len(a) > 1:
        inicial, sobrenome = b, a
    else:
        return 0

    ap_norm = normalizar_texto(nome_cartola)
    nome_tokens = _tokens(nome_completo)
    sob_norm = normalizar_texto(sobrenome)

    if sob_norm not in ap_norm and sob_norm not in nome_tokens:
        return -40

    primeiros: list[str] = []
    for tok in nome_tokens:
        if tok:
            primeiros.append(tok[0])
    # Apelido composto: "Lautaro Martínez" → inicial do primeiro nome
    if len(nome_tokens) >= 2 and sob_norm == nome_tokens[-1]:
        if nome_tokens[0][0] == inicial:
            return 20
        return -25
    if primeiros and inicial in primeiros:
        return 20
    if primeiros and inicial not in primeiros:
        return -25
    return 0


def _pontuar_par(nome_fonte: str, nome_cartola: str, nome_completo: str = "") -> int:
    nome_norm = normalizar_texto(nome_fonte)
    ap_norm = normalizar_texto(nome_cartola)
    tokens_fonte = _tokens_expandidos(nome_fonte)
    tokens_cartola = _tokens_expandidos(nome_cartola)

    score = 0
    if ap_norm and ap_norm in nome_norm:
        score = 100 + len(ap_norm)
    elif tokens_cartola and tokens_cartola <= tokens_fonte:
        score = 80 + len(tokens_cartola)
    elif tokens_cartola:
        inter = tokens_cartola & tokens_fonte
        if inter:
            score = 50 + len(inter) * 10

    # Ordem invertida: "Santos Danilo" vs apelido "Danilo Santos"
    if tokens_cartola and tokens_cartola <= set(nome_norm.split()):
        score = max(score, 75 + len(tokens_cartola))

    tokens_f = _tokens(nome_fonte)
    tokens_c = _tokens(nome_cartola)
    if tokens_c and len(tokens_c) == 1 and tokens_f and tokens_f[-1] == tokens_c[0]:
        score = max(score, 72)
    if tokens_f and len(tokens_f) == 1 and tokens_c and tokens_f[0] in tokens_c:
        score = max(score, 72)

    # "A Robertson" / "Robertson A" vs apelido "Robertson"
    if len(tokens_f) == 2:
        a, b = tokens_f[0], tokens_f[1]
        if len(a) == 1 and (b in tokens_cartola or b == ap_norm):
            score = max(score, 88)
        if len(b) == 1 and (a in tokens_cartola or a == ap_norm):
            score = max(score, 88)

    fuzzy = _score_fuzzy_nome(nome_fonte, nome_cartola)
    if fuzzy >= 85:
        score = max(score, fuzzy)
    elif fuzzy >= 78 and score >= 45:
        score = max(score, fuzzy)

    score += _bonus_inicial_sobrenome(nome_fonte, nome_cartola, nome_completo)
    return max(score, 0)


def atribuir_nomes_a_jogadores(
    nomes: list[str],
    candidatos: list[dict],
    *,
    excluir_ids: set[int] | None = None,
    min_score: int = MIN_SCORE_ATRIBUICAO,
) -> dict[str, tuple[dict, int]]:
    """
    Atribuição um-a-um: cada nome de odds → no máximo um atleta_id.
    Desempate: score, depois copa_jogos_num (quem já estreou na Copa).
    """
    excl = excluir_ids or set()
    pares: list[tuple[int, int, str, dict]] = []

    for nome in nomes:
        for jog in candidatos:
            aid = int(jog.get("atleta_id") or 0)
            if not aid or aid in excl:
                continue
            s = pontuar_match(nome, jog)
            if s >= min_score:
                jogos = int(jog.get("copa_jogos_num") or 0)
                pares.append((s, jogos, nome, jog))

    pares.sort(key=lambda x: (-x[0], -x[1]))

    usados_nomes: set[str] = set()
    usados_ids: set[int] = set()
    resultado: dict[str, tuple[dict, int]] = {}

    for score, _jogos, nome, jog in pares:
        aid = int(jog["atleta_id"])
        if nome in usados_nomes or aid in usados_ids:
            continue
        resultado[nome] = (jog, score)
        usados_nomes.add(nome)
        usados_ids.add(aid)

    return resultado


def melhor_jogador_para_nome(
    nome_fonte: str,
    candidatos: list[dict],
    *,
    excluir_ids: set[int] | None = None,
    min_score: int = MIN_SCORE_ATRIBUICAO,
) -> tuple[dict | None, int]:
    """Retorna o melhor candidato único (sem reservar um-a-um)."""
    excl = excluir_ids or set()
    melhor: tuple[int, int, dict] | None = None
    for jog in candidatos:
        aid = int(jog.get("atleta_id") or 0)
        if not aid or aid in excl:
            continue
        score = pontuar_match(nome_fonte, jog)
        if score < min_score:
            continue
        jogos = int(jog.get("copa_jogos_num") or 0)
        chave = (score, jogos)
        if melhor is None or chave > (melhor[0], melhor[1]):
            melhor = (score, jogos, jog)
    if melhor is None:
        return None, 0
    return melhor[2], melhor[0]
