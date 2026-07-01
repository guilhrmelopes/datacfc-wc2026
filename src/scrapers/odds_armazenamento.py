"""
Armazenamento e compilação de odds por evento (calendário WC2026 como âncora).

Janela de scrape: hoje (America/Sao_Paulo) + N dias.
Classificação por seleção:
  - data < hoje  → expurga do armazenamento
  - data >= hoje → confronto "atual" = partida mais próxima; demais = futuro (guardadas)
Compilação gera odds_jogadores.json só com confrontos atuais por seleção.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scrapers.bookmakers_odds import bookmaker_permitido

_FUSO_CALENDARIO = ZoneInfo("America/Sao_Paulo")
_JANELA_DIAS_PADRAO = 7
_POS_LINHA = frozenset({2, 3, 4, 5})
_POS_SG = frozenset({1, 2, 3})
_POS_ODDS_ALVO = _POS_LINHA | _POS_SG

_RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_ARMAZENAMENTO = _RAIZ / "frontend" / "public" / "data" / "odds_eventos_armazenados.json"
CAMINHO_GRUPOS = _RAIZ / "frontend" / "public" / "data" / "grupos_wc2026.json"
CAMINHO_MERCADO = _RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_SAIDA = _RAIZ / "frontend" / "public" / "data" / "odds_jogadores.json"
CAMINHO_ESTADO = _RAIZ / "frontend" / "public" / "data" / "copa_estado.json"
CAMINHO_ML_CONTEXTO = _RAIZ / "frontend" / "public" / "data" / "ml_contexto_rodada.json"

logger = logging.getLogger(__name__)

_MERCADOS_ODDS = (
    ("g_pct", "odds_g", "casa_g"),
    ("a_pct", "odds_a", "casa_a"),
    ("ga_pct", "odds_ga", "casa_ga"),
    ("sg_pct", "odds_sg", "casa_sg"),
)


def sanitizar_entrada_odds(entrada: dict) -> dict:
    """Remove mercados de casas não autorizadas; preserva demais campos."""
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    out = dict(entrada)
    for pct_key, odds_key, casa_key in _MERCADOS_ODDS:
        casa = out.get(casa_key)
        if casa and not bookmaker_permitido(str(casa)):
            out.pop(pct_key, None)
            out.pop(odds_key, None)
            out.pop(casa_key, None)
    if out.get("casa_ml") and not bookmaker_permitido(str(out["casa_ml"])):
        for chave in ("ml_home", "ml_draw", "ml_away", "casa_ml", "p_vit_home", "p_vit_away", "p_empate"):
            out.pop(chave, None)
    return enriquecer_odds_entrada(out)


def entrada_odds_tem_casa_nao_autorizada(entrada: dict) -> bool:
    for _, _, casa_key in _MERCADOS_ODDS:
        casa = entrada.get(casa_key)
        if casa and not bookmaker_permitido(str(casa)):
            return True
    casa_ml = entrada.get("casa_ml")
    return bool(casa_ml and not bookmaker_permitido(str(casa_ml)))


def expurgar_eventos_nao_conformes(armazenamento: dict[str, Any]) -> int:
    """Remove eventos cujas odds usam casas fora do grupo permitido."""
    eventos: dict[str, dict] = armazenamento.setdefault("eventos", {})
    removidos = 0
    for eid in list(eventos.keys()):
        ev = eventos[eid]
        odds_map = ev.get("odds") or {}
        contaminado = any(
            isinstance(v, dict) and entrada_odds_tem_casa_nao_autorizada(v)
            for v in odds_map.values()
        )
        if ev.get("casa_ml") and not bookmaker_permitido(str(ev["casa_ml"])):
            contaminado = True
        if contaminado:
            del eventos[eid]
            removidos += 1
    if removidos:
        logger.info("Expurgados %d eventos com casas não autorizadas.", removidos)
    return removidos


def limpar_armazenamento_odds() -> None:
    """Zera cache de eventos — força re-scrape completo."""
    payload: dict[str, Any] = {
        "eventos": {},
        "referencia_data": referencia_hoje().isoformat(),
        "janela_dias": janela_dias(),
        "atualizado_em": datetime.now(tz=_FUSO_CALENDARIO).isoformat(),
    }
    salvar_armazenamento(payload)
    salvar_ml_contexto(payload)
    logger.info("Armazenamento de odds zerado — re-scrape necessário.")


def exportar_ml_contexto(armazenamento: dict[str, Any]) -> dict[str, Any]:
    """Contexto ML compacto para o frontend (substitui odds_eventos_armazenados.json)."""
    ref = referencia_hoje().isoformat()
    eventos_list = [
        ev for ev in armazenamento.get("eventos", {}).values()
        if isinstance(ev, dict)
    ]
    p_vit: dict[str, float] = {}
    probs: list[float] = []

    for ev in eventos_list:
        d = (ev.get("data") or "")[:10]
        if not d or d < ref:
            continue
        p_home = ev.get("p_vit_home")
        p_away = ev.get("p_vit_away")
        sig_m = (ev.get("sigla_mandante") or "").upper()
        sig_v = (ev.get("sigla_visitante") or "").upper()
        if p_home is None or p_away is None or not sig_m or not sig_v:
            continue
        p_vit[sig_m] = float(p_home)
        p_vit[sig_v] = float(p_away)
        probs.extend([float(p_home), float(p_away)])

    p_mediana = 0.0
    if probs:
        ordenado = sorted(probs)
        meio = len(ordenado) // 2
        p_mediana = (
            ordenado[meio]
            if len(ordenado) % 2
            else (ordenado[meio - 1] + ordenado[meio]) / 2
        )

    return {
        "referencia_data": ref,
        "atualizado_em": datetime.now(tz=_FUSO_CALENDARIO).isoformat(),
        "p_vit_por_sigla": p_vit,
        "p_mediana": round(p_mediana, 4),
    }


def salvar_ml_contexto(armazenamento: dict[str, Any]) -> None:
    payload = exportar_ml_contexto(armazenamento)
    CAMINHO_ML_CONTEXTO.parent.mkdir(parents=True, exist_ok=True)
    with CAMINHO_ML_CONTEXTO.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    logger.info(
        "ML contexto: %d seleções -> %s",
        len(payload.get("p_vit_por_sigla", {})),
        CAMINHO_ML_CONTEXTO,
    )


def referencia_hoje() -> date:
    """Data de referência (calendário). Override: ODDS_REFERENCIA_DATA=YYYY-MM-DD."""
    bruto = os.environ.get("ODDS_REFERENCIA_DATA", "").strip()
    if bruto:
        return date.fromisoformat(bruto)
    return datetime.now(tz=_FUSO_CALENDARIO).date()


def janela_dias() -> int:
    bruto = os.environ.get("ODDS_JANELA_DIAS", "").strip()
    if bruto.isdigit():
        return max(1, int(bruto))
    return _JANELA_DIAS_PADRAO


def parse_data_calendario(valor: str | None) -> date | None:
    if not valor:
        return None
    bruto = str(valor).strip()[:10]
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        return None


def _carregar_json(caminho: Path) -> Any:
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def mapa_sigla_por_selecao(jogadores: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for j in jogadores:
        sel = (j.get("selecao") or "").upper()
        sig = (j.get("sigla") or "").upper()
        if sel and sig:
            out[sel] = sig
    return out


def mapa_sigla_por_atleta(jogadores: list[dict]) -> dict[str, str]:
    return {
        str(j["atleta_id"]): (j.get("sigla") or "").upper()
        for j in jogadores
        if j.get("atleta_id") is not None
    }


def carregar_confrontos_calendario() -> list[dict]:
    if not CAMINHO_GRUPOS.is_file():
        return []
    dados = _carregar_json(CAMINHO_GRUPOS)
    return list(dados.get("confrontos") or [])


def confrontos_na_janela(
    hoje: date | None = None,
    dias: int | None = None,
    confrontos: list[dict] | None = None,
) -> list[dict]:
    """Partidas com data no intervalo [hoje, hoje+dias] (campo `data` do calendário)."""
    ref = hoje or referencia_hoje()
    limite = ref + timedelta(days=dias if dias is not None else janela_dias())
    fonte = confrontos if confrontos is not None else carregar_confrontos_calendario()
    resultado: list[dict] = []
    for c in fonte:
        if c.get("finalizada"):
            continue
        d = parse_data_calendario(c.get("data"))
        if d is None or d < ref or d > limite:
            continue
        resultado.append(c)
    resultado.sort(key=lambda c: (c.get("data", ""), c.get("hora", ""), c.get("match_id", "")))
    return resultado


def scrape_seletivo_habilitado() -> bool:
    """Padrão: seletivo. Forçar janela completa: ODDS_SCRAPE_COMPLETO=1."""
    if os.environ.get("ODDS_SCRAPE_COMPLETO", "").strip().lower() in ("1", "true", "yes"):
        return False
    return os.environ.get("ODDS_SCRAPE_SELETIVO", "1").strip().lower() not in ("0", "false", "no", "off")


def _par_siglas(sig_a: str, sig_b: str) -> tuple[str, str]:
    return tuple(sorted((sig_a.upper(), sig_b.upper())))


def confrontos_demanda_odds(
    jogadores: list[dict],
    confrontos: list[dict],
    selecao_sigla: dict[str, str],
    hoje: date | None = None,
) -> list[dict]:
    """
    Confrontos onde há jogadores de linha/SG com ADV no mercado para aquela partida.
    Inclui também partidas de hoje envolvendo seleções com demanda.
    """
    ref = hoje or referencia_hoje()
    pares_demanda: set[tuple[str, str]] = set()
    siglas_ativas: set[str] = set()

    for j in jogadores:
        if j.get("ativo_playoffs") is False:
            continue
        prox = (j.get("proximo_adversario_sigla") or "").strip().upper()
        sig = (j.get("sigla") or "").strip().upper()
        pos = int(j.get("posicao_id") or 0)
        if not prox or not sig or pos not in _POS_ODDS_ALVO:
            continue
        pares_demanda.add(_par_siglas(sig, prox))
        siglas_ativas.add(sig)

    if not pares_demanda:
        return list(confrontos)

    vistos: set[str] = set()
    resultado: list[dict] = []
    for c in confrontos:
        if c.get("finalizada"):
            continue
        sig_m = selecao_sigla.get((c.get("mandante") or "").upper(), "").upper()
        sig_v = selecao_sigla.get((c.get("visitante") or "").upper(), "").upper()
        if not sig_m or not sig_v:
            continue

        par = _par_siglas(sig_m, sig_v)
        incluir = par in pares_demanda
        if not incluir:
            d = parse_data_calendario(c.get("data"))
            if d == ref and (sig_m in siglas_ativas or sig_v in siglas_ativas):
                incluir = True
        if not incluir:
            continue

        chave = f"{c.get('match_id')}|{c.get('data')}"
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(c)

    resultado.sort(key=lambda c: (c.get("data", ""), c.get("hora", ""), c.get("match_id", "")))
    return resultado


def _parse_iso_datetime(valor: str) -> datetime | None:
    bruto = (valor or "").strip()
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto.replace("Z", "+00:00"))
    except ValueError:
        return None


def confronto_fresco_no_armazenamento(
    confronto: dict,
    eventos_store: dict[str, dict],
    selecao_sigla: dict[str, str],
    *,
    min_odds: int | None = None,
    max_horas: float | None = None,
) -> bool:
    """True se o armazenamento já tem scrape recente e suficiente para o confronto."""
    limite_odds = min_odds if min_odds is not None else int(os.environ.get("ODDS_MIN_ODDS_EVENTO", "45"))
    limite_horas = max_horas if max_horas is not None else float(os.environ.get("ODDS_FRESH_HORAS", "10"))

    conf = enriquecer_confronto(confronto, selecao_sigla)
    data_alvo = (conf.get("data") or "")[:10]
    sig_m = (conf.get("sigla_mandante") or "").upper()
    sig_v = (conf.get("sigla_visitante") or "").upper()
    agora = datetime.now(tz=timezone.utc)

    for ev in eventos_store.values():
        if not isinstance(ev, dict):
            continue
        if (ev.get("data") or "")[:10] != data_alvo:
            continue
        if (ev.get("sigla_mandante") or "").upper() != sig_m:
            continue
        if (ev.get("sigla_visitante") or "").upper() != sig_v:
            continue
        if len(ev.get("odds") or {}) < limite_odds:
            continue
        if ev.get("p_vit_home") is None or ev.get("p_vit_away") is None:
            continue
        raspar = _parse_iso_datetime(str(ev.get("raspar_em") or ""))
        if raspar is None:
            continue
        if raspar.tzinfo is None:
            raspar = raspar.replace(tzinfo=timezone.utc)
        horas = (agora - raspar.astimezone(timezone.utc)).total_seconds() / 3600
        if horas <= limite_horas:
            return True
    return False


def filtrar_confrontos_para_scrape(
    confrontos: list[dict],
    eventos_store: dict[str, dict],
    selecao_sigla: dict[str, str],
    *,
    pular_frescos: bool = True,
) -> tuple[list[dict], list[dict]]:
    if not pular_frescos:
        return confrontos, []
    pendentes: list[dict] = []
    pulados: list[dict] = []
    for c in confrontos:
        if confronto_fresco_no_armazenamento(c, eventos_store, selecao_sigla):
            pulados.append(c)
        else:
            pendentes.append(c)
    return pendentes, pulados


def enriquecer_confronto(confronto: dict, selecao_sigla: dict[str, str]) -> dict[str, Any]:
    mandante = (confronto.get("mandante") or "").upper()
    visitante = (confronto.get("visitante") or "").upper()
    return {
        **confronto,
        "sigla_mandante": selecao_sigla.get(mandante, ""),
        "sigla_visitante": selecao_sigla.get(visitante, ""),
    }


def carregar_armazenamento() -> dict[str, Any]:
    if not CAMINHO_ARMAZENAMENTO.is_file():
        return {"eventos": {}}
    try:
        bruto = _carregar_json(CAMINHO_ARMAZENAMENTO)
    except (json.JSONDecodeError, OSError):
        return {"eventos": {}}
    eventos = bruto.get("eventos")
    if isinstance(eventos, list):
        por_id = {
            str(ev.get("event_id")): ev
            for ev in eventos
            if isinstance(ev, dict) and ev.get("event_id") is not None
        }
        return {**bruto, "eventos": por_id}
    if not isinstance(eventos, dict):
        return {**bruto, "eventos": {}}
    return bruto


def salvar_armazenamento(payload: dict[str, Any]) -> None:
    CAMINHO_ARMAZENAMENTO.parent.mkdir(parents=True, exist_ok=True)
    with CAMINHO_ARMAZENAMENTO.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    logger.info("Armazenamento: %d eventos -> %s", len(payload.get("eventos", {})), CAMINHO_ARMAZENAMENTO)


def normalizar_odds_pos_estreia(
    resultado: dict[str, dict],
    jogadores: list[dict],
) -> int:
    """
    Remove mercados de ataque/SG obsoletos quando adversario_sigla != proximo ADV.
    Evita exibir odds da rodada anterior após merge parcial.
    """
    removidos = 0
    for jog in jogadores:
        aid = str(jog.get("atleta_id"))
        if jog.get("ativo_playoffs") is False:
            if aid in resultado:
                del resultado[aid]
                removidos += 1
            continue
        if int(jog.get("copa_jogos_num") or 0) <= 0:
            continue
        prox = (jog.get("proximo_adversario_sigla") or "").upper()
        if not prox:
            if aid in resultado:
                del resultado[aid]
                removidos += 1
            continue
        aid = str(jog.get("atleta_id"))
        entrada = resultado.get(aid)
        if not isinstance(entrada, dict):
            continue
        odds_adv = (entrada.get("adversario_sigla") or "").upper()
        if odds_adv == prox:
            continue
        for chave in (
            "g_pct", "casa_g", "odds_g",
            "a_pct", "casa_a", "odds_a",
            "ga_pct", "casa_ga", "odds_ga",
            "sg_pct", "casa_sg", "odds_sg",
            "adversario_sigla", "rodada",
        ):
            if chave in entrada:
                del entrada[chave]
                removidos += 1
    if removidos:
        logger.info("Normalizacao pos-estreia: %d campos obsoletos removidos.", removidos)
    return removidos


def expurgar_passados(armazenamento: dict[str, Any], hoje: date | None = None) -> int:
    """Remove eventos com data de calendário anterior a hoje."""
    ref = hoje or referencia_hoje()
    eventos: dict[str, dict] = armazenamento.setdefault("eventos", {})
    removidos = 0
    for eid in list(eventos.keys()):
        ev = eventos[eid]
        d = parse_data_calendario(ev.get("data"))
        if d is not None and d < ref:
            del eventos[eid]
            removidos += 1
    if removidos:
        logger.info("Expurgados %d eventos passados (ref=%s).", removidos, ref.isoformat())
    return removidos


def confronto_atual_por_sigla(
    eventos: list[dict],
    hoje: date | None = None,
    jogadores: list[dict] | None = None,
) -> dict[str, dict]:
    """
    Para cada sigla, usa o confronto do próximo adversário no mercado Cartola.
    Sem proximo no mercado, usa a partida futura mais próxima no calendário.
    """
    ref = hoje or referencia_hoje()
    proximo_por_sigla: dict[str, tuple[str, str]] = {}
    if jogadores:
        for j in jogadores:
            sig = (j.get("sigla") or "").upper()
            adv = (j.get("proximo_adversario_sigla") or "").strip().upper()
            data = (j.get("proximo_adversario_data") or "").strip()
            if sig and adv and data:
                proximo_por_sigla.setdefault(sig, (adv, data))

    por_sigla: dict[str, list[dict]] = defaultdict(list)
    for ev in eventos:
        d = parse_data_calendario(ev.get("data"))
        if d is None or d < ref:
            continue
        for sig in (ev.get("sigla_mandante"), ev.get("sigla_visitante")):
            s = (sig or "").upper()
            if s:
                por_sigla[s].append(ev)

    def _adv_do_evento(ev: dict, sig: str) -> str:
        sig_m = (ev.get("sigla_mandante") or "").upper()
        sig_v = (ev.get("sigla_visitante") or "").upper()
        return sig_v if sig == sig_m else sig_m

    def _distancia_data(ev: dict, data_alvo: str) -> int:
        d_ev = parse_data_calendario(ev.get("data"))
        d_alvo = parse_data_calendario(data_alvo)
        if d_ev is None or d_alvo is None:
            return 9999
        return abs((d_ev - d_alvo).days)

    atual: dict[str, dict] = {}
    for sig, evs in por_sigla.items():
        evs.sort(key=lambda e: (e.get("data", ""), int(e.get("event_id") or 0)))
        escolhido: dict | None = None
        prox = proximo_por_sigla.get(sig)
        if prox:
            adv_alvo, data_alvo = prox
            candidatos = [ev for ev in evs if _adv_do_evento(ev, sig) == adv_alvo]
            if candidatos:
                candidatos.sort(
                    key=lambda e: (_distancia_data(e, data_alvo), e.get("data", "")),
                )
                escolhido = candidatos[0]
        if escolhido is None and evs and not prox:
            escolhido = evs[0]
        if escolhido is not None:
            atual[sig] = escolhido
    return atual


def _entrada_odds_util(entrada: dict, posicao_id: int) -> bool:
    """True se a entrada tem odds mínimas para a posição."""
    if posicao_id in _POS_LINHA:
        return bool(
            entrada.get("ga_pct")
            or entrada.get("g_pct")
            or entrada.get("a_pct")
        )
    if posicao_id in _POS_SG:
        return bool(entrada.get("sg_pct"))
    return False


def _mediana(vals: list[float]) -> float | None:
    if not vals:
        return None
    ordenado = sorted(vals)
    n = len(ordenado)
    meio = n // 2
    if n % 2:
        return round(ordenado[meio], 2)
    return round((ordenado[meio - 1] + ordenado[meio]) / 2, 2)


def _imputar_odds_de_pares(peers: list[dict], posicao_id: int) -> dict:
    """Mediana das odds dos colegas no mesmo evento (fallback quando a casa não lista o jogador)."""
    entrada: dict[str, Any] = {"imputado": True}
    if posicao_id in _POS_LINHA:
        for pct_key, odds_key, casa_key in (
            ("g_pct", "odds_g", "casa_g"),
            ("a_pct", "odds_a", "casa_a"),
            ("ga_pct", "odds_ga", "casa_ga"),
        ):
            pcts = [float(p[pct_key]) for p in peers if p.get(pct_key) is not None]
            odds_vals = [float(p[odds_key]) for p in peers if p.get(odds_key) is not None]
            casas = [
                str(p[casa_key]) for p in peers
                if p.get(casa_key) and bookmaker_permitido(str(p[casa_key]))
            ]
            if pcts:
                entrada[pct_key] = _mediana(pcts)
            if odds_vals:
                entrada[odds_key] = _mediana(odds_vals)
            if casas:
                entrada[casa_key] = casas[0]
    elif posicao_id in _POS_SG:
        pcts = [float(p["sg_pct"]) for p in peers if p.get("sg_pct") is not None]
        odds_vals = [float(p["odds_sg"]) for p in peers if p.get("odds_sg") is not None]
        casas = [
            str(p["casa_sg"]) for p in peers
            if p.get("casa_sg") and bookmaker_permitido(str(p["casa_sg"]))
        ]
        if pcts:
            entrada["sg_pct"] = _mediana(pcts)
        if odds_vals:
            entrada["odds_sg"] = _mediana(odds_vals)
        if casas:
            entrada["casa_sg"] = casas[0]
    return entrada


def _colegas_mesma_posicao(
    aid: str,
    sigla: str,
    bucket: str | None,
    pos: int,
    event_odds: dict,
    por_id: dict[str, dict],
) -> list[dict]:
    """Colegas de seleção e posição com odds utilizáveis no mesmo evento."""
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    peers: list[dict] = []
    for peer_aid, peer_ent in event_odds.items():
        if peer_aid == aid or not isinstance(peer_ent, dict):
            continue
        peer_jog = por_id.get(str(peer_aid))
        if not peer_jog or (peer_jog.get("sigla") or "").upper() != sigla:
            continue
        if pos in _POS_LINHA and peer_jog.get("bucket_posicao") != bucket:
            continue
        if pos in _POS_SG and int(peer_jog.get("posicao_id") or 0) not in _POS_SG:
            continue
        peer_copy = enriquecer_odds_entrada(dict(peer_ent))
        if _entrada_odds_util(peer_copy, int(peer_jog.get("posicao_id") or 0)):
            peers.append(peer_copy)
    return peers


def _imputar_campos_faltantes(entrada: dict, peers: list[dict], pos: int) -> bool:
    """Preenche G%/A% (e SG% se defesa) ausentes com mediana dos colegas."""
    alterou = False
    if pos in _POS_LINHA:
        for pct_key, odds_key, casa_key in (
            ("g_pct", "odds_g", "casa_g"),
            ("a_pct", "odds_a", "casa_a"),
            ("ga_pct", "odds_ga", "casa_ga"),
        ):
            if entrada.get(pct_key) is not None:
                continue
            pcts = [float(p[pct_key]) for p in peers if p.get(pct_key) is not None]
            odds_vals = [float(p[odds_key]) for p in peers if p.get(odds_key) is not None]
            casas = [
                str(p[casa_key]) for p in peers
                if p.get(casa_key) and bookmaker_permitido(str(p[casa_key]))
            ]
            if pcts:
                entrada[pct_key] = _mediana(pcts)
                alterou = True
            if odds_vals and entrada.get(odds_key) is None:
                entrada[odds_key] = _mediana(odds_vals)
            if casas and entrada.get(casa_key) is None:
                entrada[casa_key] = casas[0]
        if alterou:
            entrada["imputado"] = True
    elif pos in _POS_SG and entrada.get("sg_pct") is None:
        pcts = [float(p["sg_pct"]) for p in peers if p.get("sg_pct") is not None]
        odds_vals = [float(p["odds_sg"]) for p in peers if p.get("odds_sg") is not None]
        casas = [
            str(p["casa_sg"]) for p in peers
            if p.get("casa_sg") and bookmaker_permitido(str(p["casa_sg"]))
        ]
        if pcts:
            entrada["sg_pct"] = _mediana(pcts)
            entrada["imputado"] = True
        if odds_vals and entrada.get("odds_sg") is None:
            entrada["odds_sg"] = _mediana(odds_vals)
        if casas and entrada.get("casa_sg") is None:
            entrada["casa_sg"] = casas[0]
        alterou = bool(pcts)
    return alterou


def imputar_odds_faltantes(
    resultado: dict[str, dict],
    jogadores: list[dict],
    eventos_list: list[dict],
    atuais: dict[str, dict],
) -> int:
    """Preenche G%/A% ausentes com colega da mesma posição e seleção."""
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    por_id = {str(j.get("atleta_id")): j for j in jogadores if j.get("atleta_id") is not None}
    imputados = 0

    for aid, jog in por_id.items():
        pos = int(jog.get("posicao_id") or 0)
        if pos not in _POS_ODDS_ALVO:
            continue
        prox = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        if not prox:
            continue

        sigla = (jog.get("sigla") or "").upper()
        ev = atuais.get(sigla)
        if not ev:
            continue
        sig_m = (ev.get("sigla_mandante") or "").upper()
        sig_v = (ev.get("sigla_visitante") or "").upper()
        adv_ev = sig_v if sigla == sig_m else sig_m
        if adv_ev != prox:
            continue

        bucket = jog.get("bucket_posicao")
        event_odds = ev.get("odds") or {}
        peers = _colegas_mesma_posicao(aid, sigla, bucket, pos, event_odds, por_id)
        if not peers:
            continue

        if aid in resultado:
            entrada = dict(resultado[aid])
            if _imputar_campos_faltantes(entrada, peers, pos):
                enriquecer_odds_entrada(entrada)
                resultado[aid] = entrada
                imputados += 1
            continue

        entrada = _imputar_odds_de_pares(peers, pos)
        entrada = _montar_entrada_dashboard(entrada, ev, sigla)
        enriquecer_odds_entrada(entrada)
        if _entrada_odds_util(entrada, pos):
            resultado[aid] = entrada
            imputados += 1

    if imputados:
        logger.info("Odds imputadas (colega mesma posição/seleção): %d jogadores.", imputados)
    return imputados


def _montar_entrada_dashboard(
    entrada_bruta: dict,
    ev: dict,
    sigla: str,
) -> dict:
    sig_m = (ev.get("sigla_mandante") or "").upper()
    sig_v = (ev.get("sigla_visitante") or "").upper()
    adv = sig_v if sigla == sig_m else sig_m

    entrada = dict(entrada_bruta)
    entrada["event_id"] = ev.get("event_id")
    entrada["adversario_sigla"] = adv or entrada.get("adversario_sigla")
    entrada["data_confronto"] = ev.get("data")
    entrada["rodada"] = ev.get("rodada")
    return entrada


def compilar_dashboard(
    armazenamento: dict[str, Any],
    jogadores: list[dict] | None = None,
    hoje: date | None = None,
) -> dict[str, dict]:
    """Monta odds_jogadores (chave atleta_id) só dos confrontos atuais por seleção."""
    from scrapers.odds_ga_fallback import enriquecer_odds_entrada

    ref = hoje or referencia_hoje()
    if jogadores is None:
        if not CAMINHO_MERCADO.is_file():
            jogadores = []
        else:
            jogadores = _carregar_json(CAMINHO_MERCADO)

    jogadores = [j for j in jogadores if j.get("ativo_playoffs") is not False]

    eventos_list = [
        ev for ev in armazenamento.get("eventos", {}).values()
        if isinstance(ev, dict)
    ]
    atuais = confronto_atual_por_sigla(eventos_list, ref, jogadores=jogadores)
    sigla_por_atleta = mapa_sigla_por_atleta(jogadores)

    resultado: dict[str, dict] = {}
    for aid, sigla in sigla_por_atleta.items():
        if not sigla:
            continue
        ev = atuais.get(sigla)
        if not ev:
            continue
        entrada_bruta = (ev.get("odds") or {}).get(aid)
        if not isinstance(entrada_bruta, dict):
            continue
        resultado[aid] = _montar_entrada_dashboard(sanitizar_entrada_odds(entrada_bruta), ev, sigla)

    # Backfill: jogadores com ADV ainda sem odds no confronto atual
    prox_por_sigla = {
        (j.get("selecao") or "").upper(): j
        for j in jogadores
        if j.get("proximo_adversario_sigla")
    }
    eventos_ordenados = sorted(
        eventos_list,
        key=lambda e: (e.get("data", ""), int(e.get("event_id") or 0)),
    )
    for aid, sigla in sigla_por_atleta.items():
        if aid in resultado:
            continue
        jog = next((j for j in jogadores if str(j.get("atleta_id")) == aid), None)
        if not jog:
            continue
        pos = int(jog.get("posicao_id") or 0)
        if pos not in _POS_ODDS_ALVO:
            continue
        prox_adv = (jog.get("proximo_adversario_sigla") or "").strip().upper()
        if not prox_adv:
            continue
        prox_data = (jog.get("proximo_adversario_data") or "").strip()
        candidatos: list[tuple[int, dict]] = []
        for ev in eventos_ordenados:
            d = parse_data_calendario(ev.get("data"))
            if d is None or d < ref:
                continue
            sig_m = (ev.get("sigla_mandante") or "").upper()
            sig_v = (ev.get("sigla_visitante") or "").upper()
            if sigla not in (sig_m, sig_v):
                continue
            adv_ev = sig_v if sigla == sig_m else sig_m
            if adv_ev != prox_adv:
                continue
            dist = 9999
            if prox_data:
                d_alvo = parse_data_calendario(prox_data)
                if d_alvo is not None:
                    dist = abs((d - d_alvo).days)
            entrada_bruta = (ev.get("odds") or {}).get(aid)
            if not isinstance(entrada_bruta, dict):
                continue
            if not _entrada_odds_util(entrada_bruta, pos):
                continue
            candidatos.append((dist, ev))

        if candidatos:
            candidatos.sort(key=lambda item: (item[0], item[1].get("data", "")))
            ev = candidatos[0][1]
            entrada_bruta = (ev.get("odds") or {}).get(aid)
            if isinstance(entrada_bruta, dict):
                resultado[aid] = _montar_entrada_dashboard(
                    sanitizar_entrada_odds(entrada_bruta), ev, sigla,
                )

    imputar_odds_faltantes(resultado, jogadores, eventos_list, atuais)

    for entrada in resultado.values():
        enriquecer_odds_entrada(entrada)

    normalizar_odds_pos_estreia(resultado, jogadores)

    logger.info(
        "Compilado dashboard: %d atletas | %d seleções com confronto atual (ref=%s).",
        len(resultado),
        len(atuais),
        ref.isoformat(),
    )
    return resultado


_CAMPOS_ML = (
    "ml_home",
    "ml_draw",
    "ml_away",
    "casa_ml",
    "p_vit_home",
    "p_vit_away",
    "p_empate",
)


def montar_registro_evento(
    evento: dict,
    confronto: dict,
    odds: dict[str, dict],
    ml: dict | None = None,
) -> dict[str, Any]:
    registro: dict[str, Any] = {
        "event_id": int(evento["id"]),
        "data": confronto.get("data") or evento.get("data", ""),
        "hora": confronto.get("hora", ""),
        "rodada": confronto.get("rodada"),
        "grupo": confronto.get("grupo", ""),
        "mandante": confronto.get("mandante", ""),
        "visitante": confronto.get("visitante", ""),
        "sigla_mandante": confronto.get("sigla_mandante", ""),
        "sigla_visitante": confronto.get("sigla_visitante", ""),
        "home": evento.get("home", ""),
        "away": evento.get("away", ""),
        "fixture_id": confronto.get("match_id") or evento.get("fixture_id"),
        "odds": {
            str(aid): sanitizar_entrada_odds(dict(v))
            for aid, v in odds.items()
            if isinstance(v, dict)
        },
    }
    if ml:
        for chave in _CAMPOS_ML:
            if chave in ml and ml[chave] is not None:
                registro[chave] = ml[chave]
    return registro


def compilar_e_salvar(
    hoje: date | None = None,
    min_jogadores: int = 500,
) -> dict[str, dict]:
    """Recompila odds_jogadores.json a partir do armazenamento (sem scrape)."""
    from pipeline.timestamp_dashboard import marcar_dashboard_atualizado

    ref = hoje or referencia_hoje()
    armaz = carregar_armazenamento()
    expurgar_passados(armaz, ref)
    expurgar_eventos_nao_conformes(armaz)
    armaz["referencia_data"] = ref.isoformat()
    armaz["janela_dias"] = janela_dias()
    armaz["atualizado_em"] = datetime.now(tz=_FUSO_CALENDARIO).isoformat()
    salvar_armazenamento(armaz)
    salvar_ml_contexto(armaz)

    odds = compilar_dashboard(armaz, hoje=ref)
    from scrapers.odds_ga_fallback import enriquecer_mapa_odds

    enriquecer_mapa_odds(odds)
    if len(odds) < min_jogadores and CAMINHO_SAIDA.is_file():
        logger.warning(
            "Compilação com %d atletas (< %d) — preservando odds_jogadores anterior.",
            len(odds),
            min_jogadores,
        )
        return odds

    payload = {
        "atualizado_em": datetime.now(tz=_FUSO_CALENDARIO).isoformat(),
        "referencia_data": ref.isoformat(),
        "total_jogadores": len(odds),
        "odds": odds,
    }
    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with CAMINHO_SAIDA.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    if CAMINHO_ESTADO.is_file():
        marcar_dashboard_atualizado(CAMINHO_ESTADO)
    logger.info("Salvo dashboard: %d atletas -> %s", len(odds), CAMINHO_SAIDA)
    return odds
