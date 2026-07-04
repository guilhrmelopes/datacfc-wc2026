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

DATA_TRANSICAO_PLAYOFFS = date(2026, 6, 25)
DATA_INICIO_PLAYOFFS = date(2026, 6, 28)


def _iter_linhas_classificacao(classificacao: dict):
    for chave, linhas in classificacao.items():
        if chave == "melhores_terceiros" or not isinstance(linhas, list):
            continue
        for linha in linhas:
            if isinstance(linha, dict) and linha.get("selecao"):
                yield linha


def selecoes_com_rodada3_finalizada(partidas_grupo: list) -> set[str]:
    """Seleções cujo jogo da rodada 3 de grupos já encerrou."""
    com_r3: set[str] = set()
    for p in partidas_grupo:
        if isinstance(p, PartidaCalendario):
            rodada, finalizada = p.rodada, p.finalizada
            mandante, visitante = p.mandante, p.visitante
        else:
            rodada = int(p.get("rodada") or 0)
            finalizada = bool(p.get("finalizada"))
            mandante, visitante = p.get("mandante"), p.get("visitante")
        if rodada != 3 or not finalizada:
            continue
        if mandante:
            com_r3.add(mandante)
        if visitante:
            com_r3.add(visitante)
    return com_r3


def selecoes_ativas_aquecimento(
    classificacao: dict,
    partidas_grupo: list,
) -> set[str]:
    """
    Filtro do mercado Cartola no aquecimento (R3 em andamento / mercado fechado):
    - oculta seleções que ainda não jogaram a rodada 3;
    - oculta eliminados (4º após R3; não classificados quando todos os grupos encerraram).
    """
    rodada3_ok = selecoes_com_rodada3_finalizada(partidas_grupo)
    todas_grupos = _todas_partidas_grupo_finalizadas(partidas_grupo)
    classificadas = selecoes_classificadas_playoffs(classificacao)
    ativas: set[str] = set()

    for linha in _iter_linhas_classificacao(classificacao):
        selecao = linha["selecao"]
        if selecao not in rodada3_ok:
            continue
        pos = int(linha.get("posicao") or 0)
        if todas_grupos:
            if selecao in classificadas:
                ativas.add(selecao)
        elif pos <= 3:
            ativas.add(selecao)

    return ativas


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


def _iter_confrontos_mata_mata(mata_mata: dict):
    for fase in mata_mata.get("fases") or []:
        stage = fase.get("stage") or ""
        for confronto in fase.get("confrontos") or []:
            yield stage, confronto
    for stage, key in (("final", "final"), ("bronze", "disputa_bronze")):
        bloco = mata_mata.get(key)
        if isinstance(bloco, dict):
            yield stage, bloco


def _confrontos_fase(mata_mata: dict, stage: str) -> list[dict]:
    for f in mata_mata.get("fases") or []:
        if f.get("stage") == stage:
            return list(f.get("confrontos") or [])
    return []


def selecoes_eliminadas_ko(mata_mata: dict) -> set[str]:
    """Seleções derrotadas em qualquer fase KO já finalizada."""
    eliminadas: set[str] = set()
    vivas_pendentes: set[str] = set()

    # Mapeia prospectivamente todas as seleções que possuem partidas não finalizadas
    for _stage, confronto in _iter_confrontos_mata_mata(mata_mata):
        if not confronto.get("finalizada"):
            for time_bloco in (confronto.get("mandante"), confronto.get("visitante")):
                if time_bloco and not time_bloco.get("tbd") and time_bloco.get("selecao"):
                    vivas_pendentes.add(time_bloco["selecao"])

    # Determina as eliminações por placar ou por ausência na chave subsequente
    for stage, confronto in _iter_confrontos_mata_mata(mata_mata):
        if not confronto.get("finalizada"):
            continue

        mandante = confronto.get("mandante") or {}
        visitante = confronto.get("visitante") or {}
        nome_m = mandante.get("selecao")
        nome_v = visitante.get("selecao")

        if not nome_m or not nome_v:
            continue

        venceu_m = confronto.get("mandante_venceu")
        venceu_v = confronto.get("visitante_venceu")
        pm = confronto.get("placar_mandante")
        pv = confronto.get("placar_visitante")

        # Validação primária (vitória direta)
        if venceu_m and not venceu_v:
            eliminadas.add(nome_v)
        elif venceu_v and not venceu_m:
            eliminadas.add(nome_m)
        elif pm is not None and pv is not None and pm != pv:
            if pm > pv:
                eliminadas.add(nome_v)
            else:
                eliminadas.add(nome_m)
        else:
            # Validação secundária estrutural (empates em pênaltis sem flag na API)
            # Se a seleção não possuir partida pendente no torneio em andamento, está eliminada.
            if vivas_pendentes:
                if nome_m not in vivas_pendentes:
                    eliminadas.add(nome_m)
                if nome_v not in vivas_pendentes:
                    eliminadas.add(nome_v)

    return eliminadas


def selecoes_vivas_ko(mata_mata: dict, classificadas: set[str]) -> set[str]:
    """Classificados que ainda não perderam no mata-mata."""
    return classificadas - selecoes_eliminadas_ko(mata_mata)


def selecoes_classificadas_oitavas(mata_mata: dict) -> set[str]:
    """Seleções já posicionadas no chaveamento das oitavas (1/8)."""
    classificadas: set[str] = set()
    for confronto in _confrontos_fase(mata_mata, "1/8"):
        for bloco in (confronto.get("mandante"), confronto.get("visitante")):
            if bloco and not bloco.get("tbd") and bloco.get("selecao"):
                classificadas.add(bloco["selecao"])
    return classificadas


def selecoes_ativas_hub_playoffs(mata_mata: dict, classificadas: set[str]) -> set[str]:
    """
    Seleções com jogadores no HUB durante o mata-mata.
    Nas oitavas, restringe às equipes já no chaveamento 1/8 (exclui 1/16 em andamento).
    """
    vivas = selecoes_vivas_ko(mata_mata, classificadas)
    oitavas = selecoes_classificadas_oitavas(mata_mata)
    if oitavas:
        return vivas & oitavas
    return vivas


def transicao_r16_ativa(mata_mata: dict) -> bool:
    """16 avos em andamento: algum jogo finalizado, fase ainda aberta."""
    r16 = _confrontos_fase(mata_mata, "1/16")
    if not r16:
        return False
    finalizados = sum(1 for c in r16 if c.get("finalizada"))
    return 0 < finalizados < len(r16)


def transicao_playoffs_ativa(
    partidas_grupo: list,
    hoje: date | None = None,
    *,
    rodada_cartola: int | None = None,
) -> bool:
    """
    Aquecimento (25/06+ ou R3 Cartola): ADV/odds KO e mercado enxuto —
    só seleções com R3 jogada e ainda vivas na disputa.
    """
    ref = hoje or date.today()
    if ref >= DATA_TRANSICAO_PLAYOFFS:
        return True
    if rodada_cartola is not None and rodada_cartola >= 3:
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
