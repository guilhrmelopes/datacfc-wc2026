"""Cálculo de pontuação Cartola FC 2026 a partir de estatísticas FotMob agregadas."""

from __future__ import annotations

from typing import Any

import pandas as pd

POSICOES_GOLEIRO = frozenset({1, 2, 11})
POSICOES_LATERAL = frozenset({32, 36, 37, 38, 62})
POSICOES_ZAGUEIRO = frozenset({33, 34, 35, 52})
POSICOES_DEFESA = POSICOES_GOLEIRO | POSICOES_LATERAL | POSICOES_ZAGUEIRO
POSICOES_COM_SG = POSICOES_DEFESA

BUCKETS_POSICAO = ("GOL", "LAT", "ZAG", "MEI", "ATA")

MAPEAMENTO_BUCKET = {
    "GOL": POSICOES_GOLEIRO,
    "LAT": POSICOES_LATERAL,
    "ZAG": POSICOES_ZAGUEIRO,
    "MEI": frozenset({41, 51, 59, 63, 64, 65, 66, 67, 68, 71, 72, 73, 74, 75, 76, 77, 78, 79, 82}),
    "ATA": frozenset({84, 85, 86, 87, 88, 92, 95, 103, 104, 105, 106, 107, 115}),
}

# ── Pesos disponíveis via FotMob ─────────────────────────────────────────────
PESO_G  =  8.0   # Gol
PESO_A  =  5.0   # Assistência
PESO_FD =  1.2   # Finalização defendida (chute no gol - gols)
PESO_FF =  0.8   # Finalização pra fora (chutes totais - chutes no gol)
PESO_SG =  5.0   # Jogo sem sofrer gol — exclusivo GOL/LAT/ZAG
PESO_DE =  1.3   # Defesa (saves) — exclusivo GOL
PESO_DS =  1.5   # Desarme (tackle)
PESO_PS =  1.0   # Pênalti sofrido (penalty won)
PESO_FC = -0.3   # Falta cometida (fouls)
PESO_PC = -1.0   # Pênalti cometido (penalty conceded)
PESO_CA = -1.0   # Cartão amarelo
PESO_CV = -3.0   # Cartão vermelho
PESO_GS = -1.0   # Gol sofrido — exclusivo GOL/LAT/ZAG

# ── Pesos oficiais indisponíveis no FotMob (0 implícito no cálculo) ──────────
PESO_FT = 3.0    # Finalização na trave  — indisponível FotMob
PESO_FS = 0.5    # Falta sofrida         — indisponível FotMob
PESO_PP = -4.0   # Pênalti perdido       — indisponível FotMob
PESO_I  = -0.1   # Impedimento           — indisponível FotMob
PESO_DP = 7.0    # Defesa de pênalti (GOL) — indisponível FotMob
PESO_GC = -3.0   # Gol contra (own goal) — indisponível FotMob

TAXA_ASSISTENCIA_GOL = 0.65
META_GOLS_PARTIDA = 1.2


def bucket_posicao(posicao_id: int) -> str:
    codigo = int(posicao_id)
    for bucket, ids in MAPEAMENTO_BUCKET.items():
        if codigo in ids:
            return bucket
    if codigo in POSICOES_ZAGUEIRO or codigo in POSICOES_LATERAL:
        return "ZAG"
    return "MEI"


def estimar_n_partidas(mins_played: pd.Series) -> pd.Series:
    return mins_played.clip(lower=0) / 90


def _coluna_numerica(quadro: pd.DataFrame, nome: str) -> pd.Series:
    if nome not in quadro.columns:
        return pd.Series(0.0, index=quadro.index)
    return pd.to_numeric(quadro[nome], errors="coerce").fillna(0)


def _mascara_posicao(resultado: pd.DataFrame, posicoes: frozenset[int]) -> pd.Series:
    return resultado["posicao_id"].astype(int).isin(posicoes)


def _calcular_eventos_sg(
    resultado: pd.DataFrame,
    clean_sheet_jogador: pd.Series,
) -> pd.Series:
    """
    SG (+5): clean sheet do time beneficia GOL, LAT e ZAG.

    clean_sheet_team = total de SG do time na competição (não é taxa por partida).
    Goleiro com clean_sheet individual usa o valor do jogador; linha recebe quota
    proporcional aos minutos entre os defensores.
    """
    eh_defesa = _mascara_posicao(resultado, POSICOES_COM_SG)
    eh_goleiro = _mascara_posicao(resultado, POSICOES_GOLEIRO)
    mins = _coluna_numerica(resultado, "mins_played")
    clean_sheet_time = _coluna_numerica(resultado, "clean_sheet_team")

    temp = resultado.assign(_mins=mins, _def=eh_defesa)
    mins_def_por_selecao = (
        temp.loc[temp["_def"]].groupby("selecao_id")["_mins"].sum()
    )
    mins_def_total = resultado["selecao_id"].map(mins_def_por_selecao).fillna(0)
    participacao = mins.div(mins_def_total.replace(0, pd.NA)).fillna(0)

    eventos_alocados = clean_sheet_time * participacao
    eventos_goleiro = clean_sheet_jogador.where(clean_sheet_jogador > 0, eventos_alocados)
    eventos = eventos_goleiro.where(eh_goleiro, eventos_alocados)
    return eventos.where(eh_defesa, 0.0)


def calcular_scouts_cartola_por_jogador(quadro: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula cada scout Cartola 2026 respeitando elegibilidade por posição.

    Elegibilidade:
    - Todas as posições: G, A, FD, FF, PS, DS, FC, PC, CA, CV.
    - Exclusivo GOL: DE, GS (gol sofrido individual via saves/goals_conceded).
    - GOL + LAT + ZAG: SG, GS (gol sofrido por posição defensiva).
    - Indisponíveis no FotMob (0 implícito): FT, FS, I, PP, GC (gol contra), DP.
      → Esses scouts existem nos dados do SofaScore (scouts_individuais.json).
    """
    resultado = quadro.copy()
    eh_goleiro = _mascara_posicao(resultado, POSICOES_GOLEIRO)
    eh_defesa  = _mascara_posicao(resultado, POSICOES_DEFESA)  # GOL + LAT + ZAG

    goals          = _coluna_numerica(resultado, "goals")
    assists        = _coluna_numerica(resultado, "goal_assist")
    sot            = _coluna_numerica(resultado, "ontarget_scoring_att")
    shots          = _coluna_numerica(resultado, "total_scoring_att")
    tackles        = _coluna_numerica(resultado, "total_tackle")
    saves          = _coluna_numerica(resultado, "saves")
    clean_sheet    = _coluna_numerica(resultado, "clean_sheet")
    goals_conceded = _coluna_numerica(resultado, "goals_conceded")
    fouls          = _coluna_numerica(resultado, "fouls")
    penalty_won    = _coluna_numerica(resultado, "penalty_won")
    penalty_conceded = _coluna_numerica(resultado, "penalty_conceded")
    yellow         = _coluna_numerica(resultado, "yellow_card")
    red            = _coluna_numerica(resultado, "red_card")

    fd_eventos = (sot - goals).clip(lower=0)
    ff_eventos = (shots - sot).clip(lower=0)
    sg_eventos = _calcular_eventos_sg(resultado, clean_sheet)

    resultado["scout_G"]  = goals * PESO_G
    resultado["scout_A"]  = assists * PESO_A
    resultado["scout_FD"] = fd_eventos * PESO_FD
    resultado["scout_FF"] = ff_eventos * PESO_FF
    resultado["scout_PS"] = penalty_won * PESO_PS
    resultado["scout_SG"] = sg_eventos * PESO_SG
    resultado["scout_DE"] = saves.where(eh_goleiro, 0.0) * PESO_DE
    resultado["scout_DS"] = tackles * PESO_DS
    # GS aplica-se a GOL, LAT e ZAG (FotMob só fornece goals_conceded para GOL;
    # para LAT/ZAG o valor será 0 na fonte, mas a elegibilidade está correta).
    resultado["scout_GS"] = goals_conceded.where(eh_defesa, 0.0) * PESO_GS
    resultado["scout_FC"] = fouls * PESO_FC
    resultado["scout_PC"] = penalty_conceded * PESO_PC
    resultado["scout_CA"] = yellow * PESO_CA
    resultado["scout_CV"] = red * PESO_CV
    # Scouts com peso oficial mas indisponíveis no FotMob → contribuição = 0:
    #   FT (+3.0), FS (+0.5), PP (-4.0), I (-0.1), GC (-3.0), DP (+7.0 GOL)
    return resultado


def calcular_pontuacao_cartola(quadro: pd.DataFrame) -> pd.DataFrame:
    """
    Pontuação Cartola por jogador.

    1. Soma scouts com pesos oficiais (acumulado do torneio).
    2. Divide por (mins_played / 90) → pontuação média por partida (P90).
    """
    resultado = calcular_scouts_cartola_por_jogador(quadro)
    fator_tempo = _coluna_numerica(resultado, "mins_played").clip(lower=0) / 90

    colunas_scout = [c for c in resultado.columns if c.startswith("scout_")]
    resultado["pontuacao_cartola"] = resultado[colunas_scout].sum(axis=1)
    resultado["pontuacao_cartola_p90"] = (
        resultado["pontuacao_cartola"] / fator_tempo.replace(0, pd.NA)
    ).fillna(0)
    resultado["pontuacao_cartola_media_jogo"] = resultado["pontuacao_cartola_p90"]
    resultado["pontuacao_conquistada_media"] = resultado["pontuacao_cartola_p90"]
    resultado["n_partidas_est"] = fator_tempo
    resultado["bucket_posicao"] = resultado["posicao_id"].apply(bucket_posicao)
    return resultado


def _valor_metrica_selecao(metricas: dict[str, Any], chave: str) -> float:
    valor = metricas.get(chave)
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def calcular_proxy_cedida_por_bucket(metricas: dict[str, Any]) -> dict[str, float]:
    """
    Proxy estatística da pontuação cedida por bucket (por partida).

    Usa scouts defensivos/ofensivos agregados da seleção (FotMob):
    - ATA/MEI adversário: gols sofridos (G) e finalizações permitidas (FD/FF).
    - GOL/LAT/ZAG adversário: fraca produção ofensiva e ações defensivas induzidas (DS/SG/DE).
    """
    gc = _valor_metrica_selecao(metricas, "goals_conceded_team_match")
    gm = _valor_metrica_selecao(metricas, "goals_team_match")
    xgc = _valor_metrica_selecao(metricas, "expected_goals_conceded_team")
    tkl = _valor_metrica_selecao(metricas, "total_tackle_team")
    inte = _valor_metrica_selecao(metricas, "interception_team")
    clr = _valor_metrica_selecao(metricas, "effective_clearance_team")
    saves = _valor_metrica_selecao(metricas, "saves_team")

    sot_permitidas = max(xgc * 2.5, gc * 1.8, 0.0)
    finaliz_defendida = max(sot_permitidas - gc, 0.0)
    finaliz_fora = max(sot_permitidas * 0.55 - finaliz_defendida, 0.0)

    pontos_g = gc * PESO_G
    pontos_fd = finaliz_defendida * PESO_FD
    pontos_ff = finaliz_fora * PESO_FF
    pontos_a = gc * TAXA_ASSISTENCIA_GOL * PESO_A

    fracao_sem_marcar = max(0.0, (META_GOLS_PARTIDA - min(gm, META_GOLS_PARTIDA)) / META_GOLS_PARTIDA)
    pontos_sg = fracao_sem_marcar * PESO_SG
    pontos_de = saves * PESO_DE

    indice_ataque_fraco = fracao_sem_marcar + max(0.0, 1.0 - gm / META_GOLS_PARTIDA)
    pontos_ds_total = (tkl + inte + clr * 0.15) * PESO_DS * indice_ataque_fraco

    return {
        "ATA": round(pontos_g + pontos_fd + pontos_ff, 2),
        "MEI": round(pontos_a, 2),
        "GOL": round(pontos_sg + pontos_de, 2),
        "LAT": round(pontos_ds_total * 0.30, 2),
        "ZAG": round(pontos_ds_total * 0.70, 2),
    }


def calcular_proxy_cedida_por_selecao(
    quadro_selecoes: pd.DataFrame,
    mapa_jogos: dict[str, int | None] | None = None,
    selecoes_alvo: set[str] | None = None,
) -> pd.DataFrame:
    """Gera media_cedida_p90 por seleção × bucket via proxy de stats de time."""
    from pipelines.metricas_selecoes import agregar_metricas_selecoes, converter_metricas_coletivas

    agregado = agregar_metricas_selecoes(quadro_selecoes)
    linhas: list[dict] = []
    selecoes_processar = (
        sorted(selecoes_alvo)
        if selecoes_alvo
        else sorted(agregado["selecao"].astype(str).str.strip().str.upper().unique())
    )

    mapa_metricas = {
        str(linha["selecao"]).strip().upper(): linha.to_dict()
        for _, linha in agregado.iterrows()
    }
    mapa_ids = {
        str(linha["selecao"]).strip().upper(): int(linha["selecao_id"])
        for _, linha in agregado.iterrows()
        if pd.notna(linha.get("selecao_id"))
    }

    for selecao in selecoes_processar:
        j = mapa_jogos.get(selecao) if mapa_jogos else None
        selecao_id = mapa_ids.get(selecao, 0)
        if mapa_jogos is not None and (j is None or j <= 0):
            for bucket in BUCKETS_POSICAO:
                linhas.append(
                    {
                        "selecao_id": selecao_id or None,
                        "selecao": selecao,
                        "bucket_posicao": bucket,
                        "media_cedida_p90": None,
                    }
                )
            continue

        brutos = mapa_metricas.get(selecao, {})
        if not brutos:
            for bucket in BUCKETS_POSICAO:
                linhas.append(
                    {
                        "selecao_id": selecao_id or None,
                        "selecao": selecao,
                        "bucket_posicao": bucket,
                        "media_cedida_p90": None,
                    }
                )
            continue

        metricas = converter_metricas_coletivas(brutos, j)
        por_bucket = calcular_proxy_cedida_por_bucket(metricas)
        for bucket in BUCKETS_POSICAO:
            linhas.append(
                {
                    "selecao_id": selecao_id or None,
                    "selecao": selecao,
                    "bucket_posicao": bucket,
                    "media_cedida_p90": por_bucket.get(bucket),
                }
            )
    return pd.DataFrame(linhas)


def media_ponderada_conquistada_por_posicao(
    quadro: pd.DataFrame,
    mapa_jogos: dict[str, int | None] | None = None,
) -> pd.DataFrame:
    """Média conquistada por seleção × bucket, ponderada por minutos."""
    mins = _coluna_numerica(quadro, "mins_played")
    valores = _coluna_numerica(quadro, "pontuacao_cartola_p90")
    temp = quadro.assign(_mins=mins, _valor=valores)
    temp = temp.loc[temp["_mins"] > 0]
    if temp.empty:
        return pd.DataFrame(
            columns=["selecao_id", "selecao", "bucket_posicao", "media_conquistada", "mins_total"]
        )

    def _agregar(grupo: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "media_conquistada": (grupo["_valor"] * grupo["_mins"]).sum()
                / grupo["_mins"].sum(),
                "mins_total": grupo["_mins"].sum(),
            }
        )

    resultado = (
        temp.groupby(["selecao_id", "selecao", "bucket_posicao"], as_index=False)
        .apply(_agregar, include_groups=False)
        .reset_index(drop=True)
    )
    if mapa_jogos is None:
        return resultado

    def _ajustar_conquistada(linha: pd.Series) -> float | None:
        selecao = str(linha["selecao"]).strip().upper()
        j = mapa_jogos.get(selecao)
        if j is None or j <= 0:
            return None
        valor = linha.get("media_conquistada")
        if pd.isna(valor):
            return None
        return round(float(valor), 2)

    resultado["media_conquistada"] = resultado.apply(_ajustar_conquistada, axis=1)
    return resultado


def montar_medias_posicao_selecao(
    quadro_jogadores: pd.DataFrame,
    quadro_selecoes: pd.DataFrame | None = None,
    pasta_raw: object | None = None,
    mapa_jogos: dict[str, int | None] | None = None,
    selecoes_copa: set[str] | None = None,
) -> pd.DataFrame:
    """Consolida conquistada (jogadores) e cedida (proxy por stats de time)."""
    del pasta_raw  # mantido por compatibilidade de assinatura
    conquistada = media_ponderada_conquistada_por_posicao(
        quadro_jogadores, mapa_jogos=mapa_jogos
    )
    if quadro_selecoes is None or quadro_selecoes.empty:
        cedida = pd.DataFrame(
            columns=["selecao_id", "selecao", "bucket_posicao", "media_cedida_p90"]
        )
    else:
        cedida = calcular_proxy_cedida_por_selecao(
            quadro_selecoes,
            mapa_jogos=mapa_jogos,
            selecoes_alvo=selecoes_copa,
        )
    quadro = conquistada.merge(
        cedida,
        on=["selecao_id", "selecao", "bucket_posicao"],
        how="outer",
    )

    if selecoes_copa and mapa_jogos:
        existentes = set(quadro["selecao"].astype(str).str.upper())
        linhas_extra: list[dict] = []
        for selecao in sorted(selecoes_copa):
            if selecao in existentes:
                continue
            j = mapa_jogos.get(selecao)
            if j is not None and j > 0:
                continue
            for bucket in BUCKETS_POSICAO:
                linhas_extra.append(
                    {
                        "selecao_id": 0,
                        "selecao": selecao,
                        "bucket_posicao": bucket,
                        "media_conquistada": None,
                        "media_cedida_p90": None,
                        "mins_total": None,
                    }
                )
        if linhas_extra:
            quadro = pd.concat([quadro, pd.DataFrame(linhas_extra)], ignore_index=True)

    return quadro


def classificar_cor_pontuacao(valor: float) -> str:
    if valor <= 2.50:
        return "bg-red-500"
    if valor <= 3.99:
        return "bg-orange-500"
    if valor <= 5.50:
        return "bg-yellow-500"
    return "bg-green-500"
