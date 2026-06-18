"""Pipeline único: calendário, classificação, partidas, cedido/conquistado e mercado."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scrapers.fotmob_copa import (
    buscar_metricas_coletivas_time,
)
from pipeline.cartola_copa_sync import aplicar_dados_cartola, rebuild_extras_fotmob, reprocessar_cedido_cartola
from scrapers.cartola_copa import buscar_dados_cartola_copa
from scrapers.fotmob_fixtures import (
    PartidaCalendario,
    extrair_classificacao_grupos,
    extrair_melhores_terceiros_fotmob,
    listar_partidas_grupos,
)
from scrapers.fotmob_mapa import SIGLA_PARA_FOTMOB_STATS

COPA_ESTADO_INICIAL = {
    "rodada_cartola_atual": 1,
    "partidas_processadas": [],
    "atualizado_em": None,
}

METRICAS_COPA_VAZIAS = {
    "goals_team_match": None,
    "goals_conceded_team_match": None,
    "possession_percentage_team": None,
    "clean_sheet_team": None,
    "expected_goals_team": None,
    "expected_goals_conceded_team": None,
    "ontarget_scoring_att_team": None,
    "big_chance_team": None,
    "touches_in_opp_box_team": None,
    "total_tackle_team": None,
    "poss_won_att_3rd_team": None,
    "saves_team": None,
    "fk_foul_lost_team": None,
    "total_yel_card_team": None,
    "total_red_card_team": None,
    "J": None,
}

def _carregar_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def _salvar_json(caminho: Path, dados) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carregar_ou_criar_estado(caminho: Path) -> dict:
    if caminho.is_file():
        return _carregar_json(caminho)
    return dict(COPA_ESTADO_INICIAL)


def _mapa_selecoes(selecoes: list[dict]) -> dict[str, dict]:
    return {s["selecao"]: s for s in selecoes}


def _sigla_por_selecao(selecoes: list[dict]) -> dict[str, str]:
    return {s["selecao"]: s["sigla"] for s in selecoes}


def _jogos_por_sigla_classificacao(classificacao: dict) -> dict[str, int]:
    jogos: dict[str, int] = {}
    for chave, valor in classificacao.items():
        if chave == "melhores_terceiros" or not isinstance(valor, list):
            continue
        for linha in valor:
            if not isinstance(linha, dict):
                continue
            sigla = linha.get("sigla")
            if sigla:
                jogos[sigla] = int(linha.get("J") or 0)
    return jogos


def sincronizar_calendario(
    partidas: list[PartidaCalendario],
    caminho_grupos: Path,
    caminho_selecoes: Path,
) -> None:
    grupos = _carregar_json(caminho_grupos)
    confrontos_json = []
    for p in partidas:
        confrontos_json.append(
            {
                "grupo": p.grupo,
                "rodada": p.rodada,
                "mandante": p.mandante,
                "visitante": p.visitante,
                "data": p.data,
                "hora": p.hora,
                "utc": p.utc_time,
                "match_id": p.match_id,
                "finalizada": p.finalizada,
                "placar": p.placar,
            }
        )
    grupos["confrontos"] = confrontos_json
    _salvar_json(caminho_grupos, grupos)

    selecoes = _carregar_json(caminho_selecoes)
    mapa = _mapa_selecoes(selecoes)

    for selecao_nome, registro in mapa.items():
        grupo = registro.get("grupo")
        if not grupo:
            continue

        estadios_antigos: dict[tuple[str, str], str] = {}
        for c in registro.get("confrontos_agendados") or []:
            estadios_antigos[(c.get("adversario", ""), c.get("data", ""))] = c.get("estadio", "")

        confrontos_time = []
        for p in partidas:
            if p.grupo != grupo:
                continue
            if p.mandante != selecao_nome and p.visitante != selecao_nome:
                continue
            adversario = p.visitante if p.mandante == selecao_nome else p.mandante
            adv = mapa.get(adversario)
            if not adv:
                continue
            confrontos_time.append(
                {
                    "adversario": adversario,
                    "adversario_sigla": adv["sigla"],
                    "adversario_clube_id": adv.get("clube_id"),
                    "adversario_escudo": adv.get("url_escudo"),
                    "grupo_adversario": grupo,
                    "data": p.data,
                    "hora": p.hora,
                    "estadio": estadios_antigos.get((adversario, p.data), ""),
                    "rodada": p.rodada,
                    "match_id": p.match_id,
                }
            )
        confrontos_time.sort(key=lambda c: (c["data"], c["hora"]))
        registro["confrontos_agendados"] = confrontos_time

    _salvar_json(caminho_selecoes, selecoes)


def atualizar_classificacao(caminho: Path, caminho_selecoes: Path) -> None:
    fotmob_tabelas = extrair_classificacao_grupos()
    melhores_terceiros = extrair_melhores_terceiros_fotmob()
    atual = _carregar_json(caminho)
    selecoes = _carregar_json(caminho_selecoes)
    meta = {s["selecao"]: s for s in selecoes}

    payload: dict = {"melhores_terceiros": melhores_terceiros}

    for grupo, linhas_fotmob in fotmob_tabelas.items():
        linhas_antigas = {l["selecao"]: l for l in atual.get(grupo, []) if isinstance(l, dict)}
        novas = []
        for linha in linhas_fotmob:
            antiga = linhas_antigas.get(linha["selecao"], {})
            meta_sel = meta.get(linha["selecao"], {})
            novas.append(
                {
                    **linha,
                    "sigla": meta_sel.get("sigla") or antiga.get("sigla"),
                    "url_escudo": meta_sel.get("url_escudo") or antiga.get("url_escudo"),
                }
            )
        payload[grupo] = novas

    _salvar_json(caminho, payload)


def _rodada_efetiva(partidas: list[PartidaCalendario], estado: dict) -> int:
    rodada = int(estado.get("rodada_cartola_atual") or 1)
    while rodada < 3:
        da_rodada = [p for p in partidas if p.rodada == rodada]
        if not da_rodada:
            break
        if all(p.finalizada for p in da_rodada):
            rodada += 1
        else:
            break
    return min(rodada, 3)


def atualizar_proximo_adversario(
    partidas: list[PartidaCalendario],
    caminho_mercado: Path,
) -> None:
    """Define o próximo adversário de cada seleção (primeira partida de grupo ainda não finalizada)."""
    mercado = _carregar_json(caminho_mercado)
    selecoes_meta = {
        j["selecao"]: j
        for j in mercado
        if j.get("selecao")
    }

    for selecao_nome, meta in selecoes_meta.items():
        grupo = meta.get("grupo")
        if not grupo:
            continue
        candidatos = [
            p
            for p in partidas
            if p.grupo == grupo
            and not p.finalizada
            and selecao_nome in (p.mandante, p.visitante)
        ]
        candidatos.sort(key=lambda p: (p.rodada, p.data, p.hora))
        proximo = candidatos[0] if candidatos else None

        for j in mercado:
            if j.get("selecao") != selecao_nome:
                continue
            if proximo is None:
                j["proximo_adversario_sigla"] = None
                j["proximo_adversario_escudo"] = None
                j["proximo_adversario_data"] = None
                continue
            adv_nome = proximo.visitante if proximo.mandante == selecao_nome else proximo.mandante
            adv_meta = next((x for x in mercado if x.get("selecao") == adv_nome), None)
            j["proximo_adversario_sigla"] = adv_meta.get("sigla") if adv_meta else None
            j["proximo_adversario_escudo"] = adv_meta.get("url_escudo") if adv_meta else None
            j["proximo_adversario_data"] = proximo.data

    _salvar_json(caminho_mercado, mercado)


def limpar_metricas_selecoes_copa(
    caminho_selecoes: Path,
    caminho_classificacao: Path,
) -> set[str]:
    """Remove métricas de eliminatórias; mantém só seleções que já estrearam na Copa."""
    selecoes = _carregar_json(caminho_selecoes)
    classificacao = _carregar_json(caminho_classificacao)
    jogos_por_sigla = _jogos_por_sigla_classificacao(classificacao)
    estrearam: set[str] = set()
    for selecao in selecoes:
        sigla = selecao.get("sigla")
        if not sigla:
            continue
        if jogos_por_sigla.get(sigla, 0) <= 0:
            selecao["metricas_coletivas"] = dict(METRICAS_COPA_VAZIAS)
            selecao["competicao"] = None
        else:
            estrearam.add(sigla)
    _salvar_json(caminho_selecoes, selecoes)
    return estrearam


def atualizar_metricas_selecoes(
    siglas: set[str],
    caminho_selecoes: Path,
    caminho_classificacao: Path,
) -> None:
    selecoes = _carregar_json(caminho_selecoes)
    classificacao = _carregar_json(caminho_classificacao)
    jogos_por_sigla = _jogos_por_sigla_classificacao(classificacao)

    for selecao in selecoes:
        sigla = selecao.get("sigla")
        if not sigla or sigla not in siglas:
            continue
        j = jogos_por_sigla.get(sigla, 0)
        if j <= 0:
            continue
        nome_fotmob = SIGLA_PARA_FOTMOB_STATS.get(sigla)
        if not nome_fotmob:
            continue
        metricas = buscar_metricas_coletivas_time(nome_fotmob)
        metricas["J"] = float(j)
        selecao["metricas_coletivas"] = metricas
        selecao["competicao"] = "Copa 2026"
    _salvar_json(caminho_selecoes, selecoes)


def executar_atualizacao(pasta_dados: Path) -> dict:
    caminho_estado = pasta_dados / "copa_estado.json"
    caminho_grupos = pasta_dados / "grupos_wc2026.json"
    caminho_selecoes = pasta_dados / "selecoes.json"
    caminho_classificacao = pasta_dados / "classificacao_grupos.json"
    caminho_pontuacao = pasta_dados / "pontuacao_cedida.json"
    caminho_mercado = pasta_dados / "jogadores_mercado.json"

    estado = carregar_ou_criar_estado(caminho_estado)
    partidas = listar_partidas_grupos()
    processadas = list(estado.get("partidas_processadas") or [])

    sincronizar_calendario(partidas, caminho_grupos, caminho_selecoes)
    atualizar_classificacao(caminho_classificacao, caminho_selecoes)

    novas = [
        p.match_id
        for p in partidas
        if p.finalizada and p.match_id not in processadas
    ]

    if novas:
        processadas.extend(novas)

    selecoes = _carregar_json(caminho_selecoes)
    estrearam = limpar_metricas_selecoes_copa(caminho_selecoes, caminho_classificacao)

    dados_cartola = buscar_dados_cartola_copa()
    resumo_cartola = aplicar_dados_cartola(pasta_dados, dados_cartola, estado)

    if processadas:
        rebuild_extras_fotmob(processadas, caminho_mercado, selecoes)
        reprocessar_cedido_cartola(
            dados_cartola,
            estado,
            selecoes,
            caminho_pontuacao,
            caminho_grupos,
            caminho_mercado=caminho_mercado,
        )
        siglas_partidas = set(resumo_cartola.get("siglas_cedido") or [])
        atualizar_metricas_selecoes(
            siglas_partidas | estrearam,
            caminho_selecoes,
            caminho_classificacao,
        )
    else:
        if not resumo_cartola.get("siglas_cedido") and not caminho_pontuacao.is_file():
            _salvar_json(caminho_pontuacao, {})

    rodada = int(estado.get("rodada_cartola_atual") or _rodada_efetiva(partidas, estado))
    estado["rodada_cartola_atual"] = rodada
    estado["partidas_processadas"] = processadas
    estado["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    _salvar_json(caminho_estado, estado)

    atualizar_proximo_adversario(partidas, caminho_mercado)

    return {
        "rodada_cartola_atual": rodada,
        "partidas_processadas": len(processadas),
        "novas_partidas": novas,
        "total_calendario": len(partidas),
        "cartola": resumo_cartola,
    }
