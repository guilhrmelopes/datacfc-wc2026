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

logger = logging.getLogger(__name__)

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
) -> dict[str, dict]:
    """
    Para cada sigla, partida mais próxima com data >= hoje.
    Usa apenas o campo `data` do calendário (ignora UTC/fuso do hub).
    """
    ref = hoje or referencia_hoje()
    por_sigla: dict[str, list[dict]] = defaultdict(list)
    for ev in eventos:
        d = parse_data_calendario(ev.get("data"))
        if d is None or d < ref:
            continue
        for sig in (ev.get("sigla_mandante"), ev.get("sigla_visitante")):
            s = (sig or "").upper()
            if s:
                por_sigla[s].append(ev)
    atual: dict[str, dict] = {}
    for sig, evs in por_sigla.items():
        evs.sort(key=lambda e: (e.get("data", ""), int(e.get("event_id") or 0)))
        atual[sig] = evs[0]
    return atual


def compilar_dashboard(
    armazenamento: dict[str, Any],
    jogadores: list[dict] | None = None,
    hoje: date | None = None,
) -> dict[str, dict]:
    """Monta odds_jogadores (chave atleta_id) só dos confrontos atuais por seleção."""
    ref = hoje or referencia_hoje()
    if jogadores is None:
        if not CAMINHO_MERCADO.is_file():
            jogadores = []
        else:
            jogadores = _carregar_json(CAMINHO_MERCADO)

    eventos_list = [
        ev for ev in armazenamento.get("eventos", {}).values()
        if isinstance(ev, dict)
    ]
    atuais = confronto_atual_por_sigla(eventos_list, ref)
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
        sig_m = (ev.get("sigla_mandante") or "").upper()
        sig_v = (ev.get("sigla_visitante") or "").upper()
        adv = sig_v if sigla == sig_m else sig_m

        entrada = dict(entrada_bruta)
        entrada["event_id"] = ev.get("event_id")
        entrada["adversario_sigla"] = adv or entrada.get("adversario_sigla")
        entrada["data_confronto"] = ev.get("data")
        entrada["rodada"] = ev.get("rodada")
        resultado[aid] = entrada

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
        "odds": odds,
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
    armaz["referencia_data"] = ref.isoformat()
    armaz["janela_dias"] = janela_dias()
    armaz["atualizado_em"] = datetime.now(tz=_FUSO_CALENDARIO).isoformat()
    salvar_armazenamento(armaz)

    odds = compilar_dashboard(armaz, hoje=ref)
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
