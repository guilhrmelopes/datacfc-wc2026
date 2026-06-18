"""Integração dos dados oficiais Cartola Copa no pipeline do dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scoring.cartola import (
    BUCKETS,
    BUCKETS_SG,
    Bucket,
    PONTOS,
    AcumuladorCedidoConquistado,
    calcular_cedido_conquistado_partida,
)
from scrapers.cartola_copa import DadosCartolaCopa, POSICAO_PARA_BUCKET, payload_tem_selecoes
from scrapers.fotmob_mapa import cartola_abrev_para_selecao, url_escudo_cartola
from scrapers.fotmob_copa import processar_partida

COPA_CAMPOS_JOGADOR = (
    "copa_jogos_num",
    "copa_mins_played",
    "copa_goals",
    "copa_goal_assist",
    "copa_clean_sheet",
    "copa_pontos_total",
    "copa_media_geral",
    "copa_media_base",
    "copa_fd",
    "copa_ds",
    "copa_de",
    "copa_gs",
    "copa_gcc",
    "copa_xg",
    "copa_xa",
    "copa_int",
    "copa_c",
    "copa_br",
    "copa_ge",
    "copa_de_pct",
)

CAMPOS_LEGADO_NAO_COPA = (
    "media_geral",
    "media_base",
    "jogos_num",
    "goals",
    "goal_assist",
    "clean_sheet",
    "mins_played",
)

MAPA_SCOUT_COPA = {
    "G": "copa_goals",
    "A": "copa_goal_assist",
    "FD": "copa_fd",
    "DS": "copa_ds",
    "DE": "copa_de",
    "GS": "copa_gs",
}


def _carregar_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def _salvar_json(caminho: Path, dados) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sigla_por_selecao(selecoes: list[dict]) -> dict[str, str]:
    return {s["selecao"]: s["sigla"] for s in selecoes}


def _zerar_copa_mercado(mercado: list[dict]) -> None:
    for j in mercado:
        for campo in COPA_CAMPOS_JOGADOR:
            if campo in ("copa_media_geral", "copa_media_base", "copa_de_pct"):
                j[campo] = None
            else:
                j[campo] = 0


def limpar_campos_legado(mercado: list[dict]) -> None:
    """Remove métricas antigas (Brasileirão/eliminatórias) que não vêm da Copa."""
    for j in mercado:
        for campo in CAMPOS_LEGADO_NAO_COPA:
            j[campo] = None


def bucket_de_posicao(posicao_id: int | None) -> Bucket | None:
    if posicao_id is None:
        return None
    bucket = POSICAO_PARA_BUCKET.get(int(posicao_id))
    if bucket in BUCKETS:
        return bucket  # type: ignore[return-value]
    return None


def _bonus_oficial_scout(scout: dict[str, Any] | None, posicao_id: int | None) -> float:
    """Bônus G/A/SG a partir do dict scout oficial (mesmo payload de pontuacao)."""
    bucket = bucket_de_posicao(posicao_id)
    if not bucket:
        return 0.0
    dados = scout or {}
    bonus = int(dados.get("G") or 0) * PONTOS["G"] + int(dados.get("A") or 0) * PONTOS["A"]
    if bucket in BUCKETS_SG:
        bonus += int(dados.get("SG") or 0) * PONTOS["SG"]
    return bonus


def mb_rodada_oficial(pontuacao: float, scout: dict[str, Any] | None, posicao_id: int | None) -> float:
    """MB de uma rodada = pontuacao − bônus G/A/SG (campos oficiais de pontuados)."""
    return round(float(pontuacao) - _bonus_oficial_scout(scout, posicao_id), 2)


def _aplicar_scouts_copa(entry: dict, scout: dict[str, Any] | None) -> None:
    dados = scout or {}
    for chave_api, campo in MAPA_SCOUT_COPA.items():
        qtd = int(dados.get(chave_api) or 0)
        if qtd:
            entry[campo] = int(entry.get(campo) or 0) + qtd
    if int(dados.get("SG") or 0):
        entry["copa_clean_sheet"] = int(entry.get("copa_clean_sheet") or 0) + int(dados["SG"])


def _snapshot_pontuados(dados: DadosCartolaCopa) -> tuple[str, dict[str, dict]]:
    rodada = str(
        dados.pontuados.get("rodada")
        or dados.status.get("rodada_atual")
        or 1
    )
    snapshot: dict[str, dict] = {}
    for aid, row in (dados.pontuados.get("atletas") or {}).items():
        if row.get("posicao_id") == 6:
            continue
        if not row.get("entrou_em_campo"):
            continue
        snapshot[str(aid)] = {
            "pontuacao": float(row.get("pontuacao") or 0),
            "scout": row.get("scout") or {},
            "posicao_id": row.get("posicao_id"),
            "clube_id": row.get("clube_id"),
        }
    return rodada, snapshot


def _partidas_encerradas(dados: DadosCartolaCopa) -> list[dict]:
    return [
        p
        for p in (dados.partidas.get("partidas") or [])
        if p.get("status_transmissao_tr") == "ENCERRADA" and p.get("valida", True)
    ]


def _mapa_clube_sigla(dados: DadosCartolaCopa, selecoes: list[dict]) -> dict[int, str]:
    por_id: dict[int, str] = {}
    for origem in (
        dados.partidas.get("clubes") or {},
        dados.pontuados.get("clubes") or {},
        dados.mercado.get("clubes") or {},
    ):
        for chave, info in origem.items():
            if not isinstance(info, dict):
                continue
            clube_id = info.get("id", chave)
            try:
                cid = int(clube_id)
            except (TypeError, ValueError):
                continue
            sigla = str(info.get("abreviacao") or "").upper()
            if sigla:
                por_id[cid] = sigla

    nome_para_sigla = _sigla_por_selecao(selecoes)
    for s in selecoes:
        try:
            cid = int(s.get("clube_id"))
        except (TypeError, ValueError):
            continue
        sigla = str(s.get("sigla") or "").upper()
        if sigla:
            por_id[cid] = sigla
    for info in (dados.mercado.get("clubes") or {}).values():
        if not isinstance(info, dict):
            continue
        cid = int(info.get("id"))
        if cid in por_id:
            continue
        for campo in ("nome_fantasia", "apelido", "nome"):
            nome = info.get(campo)
            if nome in nome_para_sigla:
                por_id[cid] = nome_para_sigla[nome]
                break
    return por_id


def _agrupar_pontos_partida(
    snapshot_rodada: dict[str, dict],
    clube_casa_id: int,
    clube_visitante_id: int,
    clube_sigla: dict[int, str],
) -> dict[str, dict[Bucket, list[float]]]:
    saida: dict[str, dict[Bucket, list[float]]] = {}
    for row in snapshot_rodada.values():
        clube_id = row.get("clube_id")
        try:
            cid = int(clube_id)
        except (TypeError, ValueError):
            continue
        if cid not in (clube_casa_id, clube_visitante_id):
            continue
        sigla = clube_sigla.get(cid)
        bucket = bucket_de_posicao(row.get("posicao_id"))
        if not sigla or not bucket:
            continue
        saida.setdefault(sigla, {b: [] for b in BUCKETS})
        saida[sigla][bucket].append(float(row.get("pontuacao") or 0))
    return saida


def _clubes_cartola(dados: DadosCartolaCopa) -> dict[int, dict]:
    """Mescla metadados de clubes/seleções dos payloads Cartola."""
    por_id: dict[int, dict] = {}
    for origem in (
        dados.partidas.get("clubes") or {},
        dados.pontuados.get("clubes") or {},
        dados.mercado.get("clubes") or {},
    ):
        for chave, info in origem.items():
            if not isinstance(info, dict):
                continue
            try:
                cid = int(info.get("id", chave))
            except (TypeError, ValueError):
                continue
            por_id[cid] = info
    return por_id


def sincronizar_selecoes_cartola(selecoes: list[dict], dados: DadosCartolaCopa) -> int:
    """
    Alinha sigla, clube_id e escudo de cada seleção com a API oficial Cartola.
    Corrige trocas (ex.: Suécia/Tunísia) que distorcem bandeiras no dashboard.
    """
    por_selecao = {s["selecao"]: s for s in selecoes}
    corrigidos = 0

    for cid, info in _clubes_cartola(dados).items():
        abrev = str(info.get("abreviacao") or "").strip().upper()
        if not abrev:
            continue
        selecao_nome = cartola_abrev_para_selecao(abrev)
        if not selecao_nome:
            continue
        registro = por_selecao.get(selecao_nome)
        if not registro:
            continue

        novo = {
            "sigla": abrev,
            "clube_id": cid,
            "url_escudo": url_escudo_cartola(abrev),
        }
        if any(registro.get(k) != v for k, v in novo.items()):
            registro.update(novo)
            corrigidos += 1

    return corrigidos


def sincronizar_mercado_metadados_selecao(
    mercado: list[dict],
    selecoes: list[dict],
    dados: DadosCartolaCopa,
) -> int:
    """Propaga sigla/escudo/seleção corretos aos jogadores via clube_id Cartola."""
    meta_clube = _meta_por_clube(selecoes)
    api_por_id = {
        int(a["atleta_id"]): a
        for a in dados.mercado.get("atletas") or []
        if a.get("atleta_id")
    }
    atualizados = 0

    for jogador in mercado:
        api = api_por_id.get(int(jogador.get("atleta_id") or 0))
        clube_id = int((api or jogador).get("clube_id") or 0)
        if not clube_id:
            continue
        meta = meta_clube.get(clube_id)
        if not meta:
            continue
        for campo in ("selecao", "sigla", "grupo", "url_escudo"):
            valor = meta.get(campo)
            if valor and jogador.get(campo) != valor:
                jogador[campo] = valor
                atualizados += 1

    return atualizados


def _meta_por_clube(selecoes: list[dict]) -> dict[int, dict]:
    return {int(s["clube_id"]): s for s in selecoes if s.get("clube_id")}


def _referencia_por_sigla(mercado: list[dict]) -> dict[str, dict]:
    refs: dict[str, dict] = {}
    for jogador in mercado:
        sigla = jogador.get("sigla")
        if sigla and sigla not in refs:
            refs[sigla] = jogador
    return refs


def _novo_jogador_mercado(api: dict, meta: dict, referencia: dict | None) -> dict:
    posicao_id = int(api.get("posicao_id") or 0)
    bucket = bucket_de_posicao(posicao_id)
    ref = referencia or {}
    entry: dict[str, Any] = {
        "atleta_id": int(api["atleta_id"]),
        "apelido": api.get("apelido") or api.get("nome") or "—",
        "posicao_id": posicao_id,
        "bucket_posicao": bucket,
        "status_id": api.get("status_id", 7),
        "clube_id": int(api.get("clube_id") or meta.get("clube_id") or 0),
        "selecao": meta.get("selecao"),
        "sigla": meta.get("sigla"),
        "grupo": meta.get("grupo"),
        "url_escudo": meta.get("url_escudo"),
        "rating_recomendacao": 0.0,
        "mins_played": None,
        "jogos_num": int(api.get("jogos_num") or 0),
        "goals": None,
        "goal_assist": None,
        "clean_sheet": None,
        "media_geral": None,
        "media_base": None,
        "proximo_adversario_sigla": ref.get("proximo_adversario_sigla"),
        "proximo_adversario_escudo": ref.get("proximo_adversario_escudo"),
        "proximo_adversario_data": ref.get("proximo_adversario_data"),
        "foto_url": None,
        "preco_num": api.get("preco_num"),
        "pontos_num": api.get("pontos_num"),
        "media_num": api.get("media_num"),
        "variacao_num": api.get("variacao_num"),
    }
    for campo in COPA_CAMPOS_JOGADOR:
        if campo in ("copa_media_geral", "copa_media_base", "copa_de_pct"):
            entry[campo] = None
        else:
            entry[campo] = 0
    return entry


def incorporar_atletas_ausentes_mercado(
    mercado: list[dict],
    dados: DadosCartolaCopa,
    selecoes: list[dict],
) -> int:
    """Inclui convocados que pontuaram no Cartola mas não estavam no JSON base."""
    ids_existentes = {int(j["atleta_id"]) for j in mercado if j.get("atleta_id")}
    api_por_id = {
        int(a["atleta_id"]): a
        for a in dados.mercado.get("atletas") or []
        if a.get("atleta_id")
    }
    meta_clube = _meta_por_clube(selecoes)
    ref_sigla = _referencia_por_sigla(mercado)
    inseridos = 0

    candidatos: set[int] = set()
    for aid, row in (dados.pontuados.get("atletas") or {}).items():
        if row.get("posicao_id") == 6:
            continue
        if not row.get("entrou_em_campo"):
            continue
        candidatos.add(int(aid))

    for aid in sorted(candidatos):
        if aid in ids_existentes:
            continue
        api = api_por_id.get(aid)
        if not api:
            continue
        clube_id = int(api.get("clube_id") or 0)
        meta = meta_clube.get(clube_id)
        if not meta:
            continue
        sigla = meta.get("sigla")
        mercado.append(_novo_jogador_mercado(api, meta, ref_sigla.get(sigla)))
        ids_existentes.add(aid)
        inseridos += 1
    return inseridos


_FOTO_GLOBO_HOST = "s.sde.globo.com"
_URL_FOTOS_PROVAVEIS = "https://provaveisdocartola.com.br/api/copa/fotos-atletas"

# Status oficiais do Cartola que não são sobrescritos por provável de lineup.
_STATUS_CARTOLA_PRIORITARIO = frozenset({2, 3, 5})
_CAMPOS_MERCADO_CARTOLA = (
    "preco_num",
    "pontos_num",
    "media_num",
    "variacao_num",
    "jogos_num",
)


def resolver_status_id(
    atleta_id: int,
    status_cartola: Any,
    provavel_ids: set[int],
) -> int:
    """
    Provável (6) → lineups Prováveis do Cartola.
    Dúvida/lesionado/suspenso (2/3/5) → Cartola /copa.
    Demais casos → Cartola, exceto 6 sem lineup (vira 7).
    """
    try:
        status = int(status_cartola)
    except (TypeError, ValueError):
        status = 7

    if status in _STATUS_CARTOLA_PRIORITARIO:
        return status
    if atleta_id in provavel_ids:
        return 6
    if status == 6:
        return 7
    return status


def _carregar_fotos_provaveis() -> dict[int, str]:
    import urllib.request

    try:
        req = urllib.request.Request(_URL_FOTOS_PROVAVEIS, headers={"User-Agent": "Mozilla/5.0"})
        payload = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return {
            int(aid): str(d["url"])
            for aid, d in (payload.get("atletas") or {}).items()
            if d.get("url")
        }
    except OSError:
        return {}


def sincronizar_fotos_mercado(
    mercado: list[dict],
    dados: DadosCartolaCopa,
) -> int:
    """Atualiza foto_url: CDN Prováveis (preferido) ou foto oficial do /copa/atletas/mercado."""
    api_por_id = {
        int(a["atleta_id"]): a
        for a in dados.mercado.get("atletas") or []
        if a.get("atleta_id")
    }
    fotos_provaveis = _carregar_fotos_provaveis()
    atualizados = 0

    for jogador in mercado:
        aid = int(jogador.get("atleta_id") or 0)
        if not aid:
            continue

        nova = fotos_provaveis.get(aid)
        if not nova:
            api = api_por_id.get(aid)
            cartola_foto = api.get("foto") if api else None
            if cartola_foto:
                nova = str(cartola_foto)
        if not nova:
            continue

        atual = jogador.get("foto_url")
        if not atual or _FOTO_GLOBO_HOST in str(atual) or atual != nova:
            if atual != nova:
                jogador["foto_url"] = nova
                atualizados += 1

    return atualizados


def sincronizar_mercado_cartola(
    mercado: list[dict],
    dados: DadosCartolaCopa,
    *,
    provavel_ids: set[int] | None = None,
) -> int:
    por_id = {
        int(a["atleta_id"]): a
        for a in dados.mercado.get("atletas") or []
        if a.get("atleta_id")
    }
    aplicar_status = provavel_ids is not None
    atualizados = 0
    for jogador in mercado:
        aid = jogador.get("atleta_id")
        if aid is None:
            continue
        api = por_id.get(int(aid))
        if not api:
            continue
        campos = (
            *_CAMPOS_MERCADO_CARTOLA,
            *(() if aplicar_status else ("status_id",)),
        )
        for campo in campos:
            valor = api.get(campo)
            if valor is not None and jogador.get(campo) != valor:
                jogador[campo] = valor
                atualizados += 1
        if aplicar_status:
            novo_status = resolver_status_id(int(aid), api.get("status_id"), provavel_ids)
            if jogador.get("status_id") != novo_status:
                jogador["status_id"] = novo_status
                atualizados += 1
    return atualizados


def sincronizar_status_fotos_cartola(
    pasta_dados: Path,
    *,
    dados: DadosCartolaCopa | None = None,
) -> dict[str, Any]:
    """
    Status: Cartola /copa (2/3/5/7) + Prováveis do Cartola (lineups → 6).
    Fotos: CDN Prováveis com fallback Cartola /copa.
    """
    from scrapers.cartola_copa import buscar_dados_cartola_copa
    from scrapers.provaveis_copa import buscar_ids_provaveis_lineup

    caminho_mercado = pasta_dados / "jogadores_mercado.json"
    caminho_estado = pasta_dados / "copa_estado.json"

    if dados is None:
        dados = buscar_dados_cartola_copa()

    if not payload_tem_selecoes(dados.mercado):
        raise RuntimeError(
            "Resposta de /copa/atletas/mercado não contém seleções — "
            "abortando sync de status (possível endpoint Brasileirão)."
        )

    mercado = _carregar_json(caminho_mercado)
    estado = _carregar_json(caminho_estado) if caminho_estado.is_file() else {}

    provavel_ids = buscar_ids_provaveis_lineup()
    status_atualizados = sincronizar_mercado_cartola(
        mercado, dados, provavel_ids=provavel_ids,
    )
    fotos_atualizadas = sincronizar_fotos_mercado(mercado, dados)

    rodada = int(dados.status.get("rodada_atual") or estado.get("rodada_cartola_atual") or 1)
    estado["rodada_cartola_atual"] = rodada
    estado["status_mercado"] = dados.status.get("status_mercado")
    estado["bola_rolando"] = dados.status.get("bola_rolando")
    estado["cartola_atualizado_em"] = dados.obtido_em

    _salvar_json(caminho_mercado, mercado)
    _salvar_json(caminho_estado, estado)

    return {
        "status_campos_atualizados": status_atualizados,
        "fotos_atualizadas": fotos_atualizadas,
        "provaveis_lineup": len(provavel_ids),
        "mercado_api": len(dados.mercado.get("atletas") or []),
        "rodada_cartola_atual": rodada,
    }


def rebuild_copa_oficial(
    mercado: list[dict],
    estado: dict,
    dados: DadosCartolaCopa,
) -> None:
    """Preenche copa_* apenas com campos oficiais de pontuados e /copa/atletas/mercado."""
    _zerar_copa_mercado(mercado)
    por_atleta = {int(j["atleta_id"]): j for j in mercado if j.get("atleta_id")}
    api_mercado = {
        int(a["atleta_id"]): a
        for a in dados.mercado.get("atletas") or []
        if a.get("atleta_id")
    }

    acum_mb: dict[int, float] = {}
    rodadas = estado.get("pontuados_por_rodada") or {}

    for _rodada, snapshot in sorted(rodadas.items(), key=lambda x: int(x[0])):
        if not isinstance(snapshot, dict):
            continue
        for aid_str, row in snapshot.items():
            try:
                aid = int(aid_str)
            except (TypeError, ValueError):
                continue
            entry = por_atleta.get(aid)
            if not entry:
                continue

            pontuacao = float(row.get("pontuacao") or 0)
            scout = row.get("scout") or {}
            posicao_id = row.get("posicao_id")

            entry["copa_jogos_num"] = int(entry.get("copa_jogos_num") or 0) + 1
            entry["copa_pontos_total"] = round(
                float(entry.get("copa_pontos_total") or 0) + pontuacao,
                2,
            )
            _aplicar_scouts_copa(entry, scout)
            acum_mb[aid] = acum_mb.get(aid, 0.0) + mb_rodada_oficial(pontuacao, scout, posicao_id)

    for entry in mercado:
        aid = entry.get("atleta_id")
        if aid is None:
            continue
        aid_int = int(aid)
        api = api_mercado.get(aid_int)
        jogos = int(entry.get("copa_jogos_num") or 0)

        if api:
            api_jogos = int(api.get("jogos_num") or 0)
            api_pontos = float(api.get("pontos_num") or 0)
            api_media = float(api.get("media_num") or 0)
            api_scout = api.get("scout") or {}

            if api_jogos > 0:
                entry["copa_jogos_num"] = api_jogos
                entry["copa_pontos_total"] = round(api_pontos, 2)
                entry["copa_media_geral"] = round(api_media, 2)
                if api_scout:
                    for campo in COPA_CAMPOS_JOGADOR:
                        if campo.startswith("copa_") and campo not in (
                            "copa_media_geral",
                            "copa_media_base",
                            "copa_de_pct",
                            "copa_xg",
                            "copa_xa",
                            "copa_int",
                            "copa_c",
                            "copa_br",
                            "copa_ge",
                            "copa_gcc",
                            "copa_mins_played",
                        ):
                            entry[campo] = 0
                    _aplicar_scouts_copa(entry, api_scout)
                jogos = api_jogos

        if jogos <= 0:
            continue

        if entry.get("copa_media_geral") is None:
            entry["copa_media_geral"] = round(float(entry["copa_pontos_total"]) / jogos, 2)

        if aid_int in acum_mb:
            entry["copa_media_base"] = round(acum_mb[aid_int] / jogos, 2)


def _partidas_cedido_historico(
    estado: dict,
    selecoes: list[dict],
    caminho_grupos: Path,
) -> list[dict]:
    """Partidas finalizadas já processadas — fonte estável quando a API só expõe a janela atual."""
    processadas = set(str(x) for x in (estado.get("partidas_processadas") or []))
    mapa_sel = {s["selecao"]: s for s in selecoes}
    confrontos = _carregar_json(caminho_grupos).get("confrontos") or []
    saida: list[dict] = []

    for c in confrontos:
        match_id = str(c.get("match_id") or "")
        if match_id not in processadas and not c.get("finalizada"):
            continue
        mandante = mapa_sel.get(c.get("mandante", ""))
        visitante = mapa_sel.get(c.get("visitante", ""))
        if not mandante or not visitante:
            continue
        try:
            casa_id = int(mandante["clube_id"])
            visitante_id = int(visitante["clube_id"])
        except (KeyError, TypeError, ValueError):
            continue
        saida.append(
            {
                "clube_casa_id": casa_id,
                "clube_visitante_id": visitante_id,
                "sig_m": str(mandante["sigla"]).upper(),
                "sig_v": str(visitante["sigla"]).upper(),
                "rodada_cartola": int(c.get("rodada") or 1),
            }
        )
    return saida


def reprocessar_cedido_cartola(
    dados: DadosCartolaCopa,
    estado: dict,
    selecoes: list[dict],
    caminho_pontuacao: Path,
    caminho_grupos: Path | None = None,
) -> set[str]:
    clube_sigla = _mapa_clube_sigla(dados, selecoes)
    acumuladores: dict[str, AcumuladorCedidoConquistado] = {}
    rodadas = estado.get("pontuados_por_rodada") or {}

    partidas: list[dict] = []
    if caminho_grupos and caminho_grupos.is_file():
        partidas = _partidas_cedido_historico(estado, selecoes, caminho_grupos)

    if not partidas:
        for partida in _partidas_encerradas(dados):
            try:
                casa = int(partida["clube_casa_id"])
                visitante = int(partida["clube_visitante_id"])
            except (KeyError, TypeError, ValueError):
                continue
            sig_m = clube_sigla.get(casa)
            sig_v = clube_sigla.get(visitante)
            if not sig_m or not sig_v:
                continue
            partidas.append(
                {
                    "clube_casa_id": casa,
                    "clube_visitante_id": visitante,
                    "sig_m": sig_m,
                    "sig_v": sig_v,
                    "rodada_cartola": int(
                        partida.get("rodada")
                        or dados.partidas.get("rodada")
                        or estado.get("rodada_cartola_atual")
                        or 1
                    ),
                }
            )

    for partida in partidas:
        casa = int(partida["clube_casa_id"])
        visitante = int(partida["clube_visitante_id"])
        sig_m = partida.get("sig_m") or clube_sigla.get(casa)
        sig_v = partida.get("sig_v") or clube_sigla.get(visitante)
        if not sig_m or not sig_v:
            continue

        rodada_partida = str(partida.get("rodada_cartola") or 1)
        snapshot = rodadas.get(rodada_partida)
        if not isinstance(snapshot, dict):
            continue

        agrupado = _agrupar_pontos_partida(snapshot, casa, visitante, clube_sigla)
        if sig_m not in agrupado or sig_v not in agrupado:
            continue

        conquistado, cedido = calcular_cedido_conquistado_partida(agrupado, sig_m, sig_v)
        acumuladores.setdefault(sig_m, AcumuladorCedidoConquistado())
        acumuladores.setdefault(sig_v, AcumuladorCedidoConquistado())
        acumuladores[sig_m].registrar_partida(conquistado[sig_m], cedido[sig_m])
        acumuladores[sig_v].registrar_partida(conquistado[sig_v], cedido[sig_v])

    if acumuladores:
        pontuacao = {sigla: acc.exportar() for sigla, acc in acumuladores.items()}
        _salvar_json(caminho_pontuacao, pontuacao)
    elif not caminho_pontuacao.is_file():
        _salvar_json(caminho_pontuacao, {})

    return set(acumuladores.keys())


def rebuild_extras_fotmob(
    partidas_ids: list[str],
    caminho_mercado: Path,
    selecoes: list[dict],
) -> None:
    """Preenche xG/xA e métricas FotMob sem alterar pontuação oficial Cartola."""
    mercado = _carregar_json(caminho_mercado)
    sigla_map = _sigla_por_selecao(selecoes)

    from scrapers.fotmob_fixtures import listar_partidas_grupos

    partidas_idx = {p.match_id: p for p in listar_partidas_grupos()}

    for match_id in partidas_ids:
        meta = partidas_idx.get(match_id)
        if not meta:
            continue
        sig_m = sigla_map.get(meta.mandante)
        sig_v = sigla_map.get(meta.visitante)
        if not sig_m or not sig_v:
            continue
        resultado = processar_partida(match_id, caminho_mercado, sig_m, sig_v)
        por_atleta = {j["atleta_id"]: j for j in mercado if j.get("atleta_id")}
        for jogador in resultado.jogadores:
            if jogador.atleta_id is None:
                continue
            entry = por_atleta.get(jogador.atleta_id)
            if not entry:
                continue
            sc = jogador.scouts
            entry["copa_mins_played"] = int(entry.get("copa_mins_played") or 0) + sc.minutos
            entry["copa_gcc"] = int(entry.get("copa_gcc") or 0) + sc.GCC
            entry["copa_int"] = int(entry.get("copa_int") or 0) + sc.INT
            entry["copa_c"] = int(entry.get("copa_c") or 0) + sc.C
            entry["copa_br"] = int(entry.get("copa_br") or 0) + sc.BR
            entry["copa_ge"] = round(float(entry.get("copa_ge") or 0) + sc.GE, 2)
            entry["copa_xg"] = round(float(entry.get("copa_xg") or 0) + jogador.xg, 2)
            entry["copa_xa"] = round(float(entry.get("copa_xa") or 0) + jogador.xa, 2)

        for entry in mercado:
            if entry.get("copa_jogos_num") and entry.get("bucket_posicao") == "GOL":
                mins = int(entry.get("copa_mins_played") or 0)
                if mins:
                    entry["copa_de_pct"] = round(
                        (float(entry.get("copa_de") or 0) / mins) * 90,
                        2,
                    )

    _salvar_json(caminho_mercado, mercado)


def aplicar_dados_cartola(
    pasta_dados: Path,
    dados: DadosCartolaCopa,
    estado: dict,
) -> dict[str, Any]:
    caminho_mercado = pasta_dados / "jogadores_mercado.json"
    caminho_pontuacao = pasta_dados / "pontuacao_cedida.json"
    selecoes = _carregar_json(pasta_dados / "selecoes.json")
    mercado = _carregar_json(caminho_mercado)

    limpar_campos_legado(mercado)

    selecoes_corrigidas = sincronizar_selecoes_cartola(selecoes, dados)
    if selecoes_corrigidas:
        _salvar_json(pasta_dados / "selecoes.json", selecoes)

    rodada, snapshot = _snapshot_pontuados(dados)
    por_rodada = estado.setdefault("pontuados_por_rodada", {})
    if snapshot:
        por_rodada[rodada] = snapshot

    estado["rodada_cartola_atual"] = int(dados.status.get("rodada_atual") or rodada)
    estado["status_mercado"] = dados.status.get("status_mercado")
    estado["bola_rolando"] = dados.status.get("bola_rolando")
    estado["cartola_atualizado_em"] = dados.obtido_em

    from scrapers.provaveis_copa import buscar_ids_provaveis_lineup

    provavel_ids = buscar_ids_provaveis_lineup()
    mercado_atualizados = sincronizar_mercado_cartola(
        mercado, dados, provavel_ids=provavel_ids,
    )
    meta_mercado = sincronizar_mercado_metadados_selecao(mercado, selecoes, dados)
    mercado_inseridos = incorporar_atletas_ausentes_mercado(mercado, dados, selecoes)
    fotos_atualizadas = sincronizar_fotos_mercado(mercado, dados)
    rebuild_copa_oficial(mercado, estado, dados)

    caminho_grupos = pasta_dados / "grupos_wc2026.json"
    if por_rodada:
        siglas = reprocessar_cedido_cartola(
            dados, estado, selecoes, caminho_pontuacao, caminho_grupos,
        )
    else:
        siglas = set()

    _salvar_json(caminho_mercado, mercado)

    return {
        "rodada_cartola": estado["rodada_cartola_atual"],
        "pontuados_rodada": len(snapshot),
        "mercado_api": len(dados.mercado.get("atletas") or []),
        "partidas_encerradas": len(_partidas_encerradas(dados)),
        "mercado_campos_atualizados": mercado_atualizados,
        "mercado_meta_selecao": meta_mercado,
        "selecoes_corrigidas": selecoes_corrigidas,
        "mercado_inseridos": mercado_inseridos,
        "fotos_atualizadas": fotos_atualizadas,
        "siglas_cedido": sorted(siglas),
        "avisos": dados.avisos,
    }
