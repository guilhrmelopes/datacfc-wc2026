"""Valida cobertura mínima de odds_jogadores.json antes de commit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_TOTAL = 500
MIN_G = 200
MIN_A = 200
MIN_GA = 400
MIN_SG = 400
MIN_VIGENTES_PCT = 0.85

POS_LINHA = frozenset({2, 3, 4, 5})
POS_SG = frozenset({1, 2, 3})

_RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"
CAMINHO_MERCADO = _RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"


def validar(caminho: Path | None = None) -> tuple[int, int, int, int, int]:
    path = caminho or CAMINHO
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    odds = data.get("odds", {})
    total = len(odds)
    g = sum(1 for v in odds.values() if v.get("g_pct"))
    a = sum(1 for v in odds.values() if v.get("a_pct"))
    ga = sum(1 for v in odds.values() if v.get("ga_pct"))
    sg = sum(1 for v in odds.values() if v.get("sg_pct"))
    return total, g, a, ga, sg


def _entrada_vigente(jog: dict, entrada: dict) -> bool:
    prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
    if not prox:
        return bool(
            entrada.get("ga_pct")
            or entrada.get("g_pct")
            or entrada.get("a_pct")
            or entrada.get("sg_pct")
        )
    odds_adv = (entrada.get("adversario_sigla") or "").strip().upper()
    if odds_adv != prox:
        return False
    pos = int(jog.get("posicao_id") or 0)
    if pos in POS_LINHA:
        return bool(entrada.get("ga_pct") or entrada.get("g_pct") or entrada.get("a_pct"))
    if pos in POS_SG:
        return bool(entrada.get("sg_pct"))
    return False


def validar_odds_vigentes(
    caminho_odds: Path | None = None,
    caminho_mercado: Path | None = None,
) -> tuple[int, int, int]:
    """
    Jogadores com ADV no mercado (qualquer status) precisam de odds alinhadas
    ao próximo adversário — GA/G/A para linha, SG para GOL/LAT/ZAG.
    """
    path_odds = caminho_odds or CAMINHO
    path_mercado = caminho_mercado or CAMINHO_MERCADO
    if not path_odds.is_file() or not path_mercado.is_file():
        return 0, 0, 0

    odds = json.loads(path_odds.read_text(encoding="utf-8")).get("odds", {})
    mercado = json.loads(path_mercado.read_text(encoding="utf-8"))

    alvo = 0
    vigentes = 0
    sem_odd = 0

    for jog in mercado:
        prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        if not prox:
            continue
        pos = int(jog.get("posicao_id") or 0)
        if pos not in POS_LINHA and pos not in POS_SG:
            continue
        alvo += 1
        entrada = odds.get(str(jog.get("atleta_id")))
        if not isinstance(entrada, dict):
            sem_odd += 1
            continue
        if _entrada_vigente(jog, entrada):
            vigentes += 1

    return alvo, vigentes, sem_odd


def main() -> None:
    total, g, a, ga, sg = validar()
    alvo, vigentes, sem_odd = validar_odds_vigentes()
    pct_vig = (vigentes / alvo * 100) if alvo else 100.0

    print(f"total={total} g={g} a={a} ga={ga} sg={sg}")
    print(f"vigentes={vigentes}/{alvo} ({pct_vig:.0f}%) sem_odd={sem_odd}")

    if (
        total < MIN_TOTAL
        or g < MIN_G
        or a < MIN_A
        or ga < MIN_GA
        or sg < MIN_SG
    ):
        print("Cobertura insuficiente — abortando commit.")
        sys.exit(1)

    if alvo > 0 and vigentes / alvo < MIN_VIGENTES_PCT:
        print(
            f"Odds vigentes abaixo de {MIN_VIGENTES_PCT:.0%} "
            f"para jogadores com ADV ({vigentes}/{alvo}). "
            "Abortando commit."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
