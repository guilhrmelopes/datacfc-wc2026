"""Utilitários Copa — classificados, calendário e adversário no mata-mata."""

from __future__ import annotations

from datetime import date

from scrapers.fotmob_fixtures import PartidaCalendario

RODADA_POR_FASE: dict[str, int] = {
    "1/16": 4,
    "1/8": 5,
    "1/4": 6,
    "1/2": 7,
    "final": 8,
    "bronze": 8,
}

DATA_TRANSICAO_PLAYOFFS = date(2026, 6, 27)
DATA_INICIO_PLAYOFFS = date(2026, 6, 28)


def _todas_partidas_grupo_finalizadas(partidas_grupo: list) -> bool:
    if not partidas_grupo:
        return False
    return all(
        p.finalizada if isinstance(p, PartidaCalendario) else bool(p.get("finalizada"))
        for p in partidas_grupo
    )


def selecoes_classificadas_playoffs(classificacao: dict) -> set[str]:
    """Top 2 de cada grupo + 8 melhores terceiros."""
    melhores = set(classificacao.get("melhores_terceiros") or [])
    classificadas: set[str] = set()
    for chave, linhas in classificacao.items():
        if chave == "melhores_terceiros" or not isinstance(linhas, list):
            continue
        for linha in linhas:
            if not isinstance(linha, dict):
                continue
            selecao = linha.get("selecao")
            if not selecao:
                continue
            pos = int(linha.get("posicao") or 0)
            if pos in (1, 2):
                classificadas.add(selecao)
            elif pos == 3 and selecao in melhores:
                classificadas.add(selecao)
    return classificadas


def transicao_playoffs_ativa(
    partidas_grupo: list,
    hoje: date | None = None,
) -> bool:
    """
    Aquecimento (27/06+): ADV e odds do mata-mata para confrontos já definidos,
    sem ocultar seleções eliminadas no mercado.
    """
    ref = hoje or date.today()
    if ref >= DATA_TRANSICAO_PLAYOFFS:
        return True
    return _todas_partidas_grupo_finalizadas(partidas_grupo)


def fase_playoffs_ativa(
    partidas_grupo: list,
    hoje: date | None = None,
) -> bool:
    """Modo completo: oculta eliminados e usa só calendário KO."""
    ref = hoje or date.today()
    if ref >= DATA_INICIO_PLAYOFFS:
        return True
    return _todas_partidas_grupo_finalizadas(partidas_grupo)


def resolver_proximo_confronto(
    selecao_nome: str,
    confrontos: list[dict],
    *,
    playoffs_completos: bool,
    transicao_gradual: bool,
    classificadas: set[str] | None,
) -> dict | None:
    confrontos_ko = [c for c in confrontos if c.get("fase")]
    confrontos_grupo = [c for c in confrontos if not c.get("fase")]

    if playoffs_completos:
        if classificadas is not None and selecao_nome not in classificadas:
            return None
        return proximo_confronto_selecao(selecao_nome, confrontos_ko)

    prox_grupo = proximo_confronto_selecao(selecao_nome, confrontos_grupo)
    if prox_grupo:
        return prox_grupo

    if transicao_gradual:
        prox_ko = proximo_confronto_selecao(selecao_nome, confrontos_ko)
        if prox_ko:
            return prox_ko

    return proximo_confronto_selecao(selecao_nome, confrontos)


def confrontos_json_mata_mata(mata_mata: dict) -> list[dict]:
    """Confrontos resolvidos (dois times definidos) para o calendário unificado."""
    saida: list[dict] = []

    def _append(confronto: dict, stage: str) -> None:
        mandante = confronto.get("mandante") or {}
        visitante = confronto.get("visitante") or {}
        nome_m = mandante.get("selecao")
        nome_v = visitante.get("selecao")
        if not nome_m or not nome_v:
            return
        placar = None
        if confronto.get("finalizada"):
            pm = confronto.get("placar_mandante")
            pv = confronto.get("placar_visitante")
            if pm is not None and pv is not None:
                placar = f"{pm}-{pv}"
        saida.append(
            {
                "grupo": "KO",
                "fase": stage,
                "rodada": RODADA_POR_FASE.get(stage, 4),
                "mandante": nome_m,
                "visitante": nome_v,
                "data": confronto.get("data") or "",
                "hora": confronto.get("hora") or "",
                "utc": confronto.get("utc_time") or "",
                "match_id": confronto.get("match_id") or "",
                "finalizada": bool(confronto.get("finalizada")),
                "placar": placar,
            }
        )

    for fase in mata_mata.get("fases") or []:
        stage = fase.get("stage") or ""
        for confronto in fase.get("confrontos") or []:
            _append(confronto, stage)

    final = mata_mata.get("final")
    if isinstance(final, dict):
        _append(final, "final")

    bronze = mata_mata.get("disputa_bronze")
    if isinstance(bronze, dict):
        _append(bronze, "bronze")

    saida.sort(key=lambda c: (c.get("data", ""), c.get("hora", ""), c.get("match_id", "")))
    return saida


def proximo_confronto_selecao(
    selecao_nome: str,
    confrontos: list[dict],
) -> dict | None:
    candidatos = [
        c
        for c in confrontos
        if not c.get("finalizada")
        and selecao_nome in (c.get("mandante"), c.get("visitante"))
    ]
    candidatos.sort(
        key=lambda c: (
            c.get("data", ""),
            c.get("hora", ""),
            str(c.get("match_id", "")),
        )
    )
    return candidatos[0] if candidatos else None
