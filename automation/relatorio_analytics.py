"""
Relatório privado de tráfego — mídia kit Data CFC WC2026.

Uso (após configurar GA4):
  pip install -r requirements-analytics.txt
  set GA4_PROPERTY_ID=123456789
  set GOOGLE_APPLICATION_CREDENTIALS=C:\\caminho\\service-account.json
  python automation/relatorio_analytics.py

Saída (gitignored em exports/):
  - relatorio_midia_kit.json
  - relatorio_midia_kit.md  (copiar para X / GitHub no fim da Copa)

Setup GA4 (uma vez):
  1. analytics.google.com → propriedade Web para o domínio do dashboard
  2. Admin → Fluxos de dados → ID de medição (G-XXXX) → VITE_GA_MEASUREMENT_ID no Vercel
  3. Admin → Detalhes da propriedade → ID numérico → GA4_PROPERTY_ID
  4. Google Cloud → service account + Analytics Data API → JSON da chave
  5. GA4 Admin → Acesso à propriedade → adicionar e-mail da service account (Leitor)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA_EXPORT = RAIZ / "exports"
CONFIG_ANALYTICS = RAIZ / "config" / "analytics.json"
ENV_LOCAL = RAIZ / "config" / "analytics.local.env"


def _carregar_env_local() -> None:
    if not ENV_LOCAL.is_file():
        return
    for linha in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave, valor = chave.strip(), valor.strip()
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def _data_inicio_coleta() -> str:
    if CONFIG_ANALYTICS.is_file():
        cfg = json.loads(CONFIG_ANALYTICS.read_text(encoding="utf-8"))
        ini = (cfg.get("inauguracao") or "").strip()
        if ini:
            return ini
    return date.today().isoformat()


def _fmt_int(val: float | int | None) -> str:
    if val is None:
        return "—"
    return f"{int(round(float(val))):,}".replace(",", ".")


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{float(val) * 100:.1f}%"


def _fmt_duracao(segundos: float | None) -> str:
    if segundos is None:
        return "—"
    s = int(round(float(segundos)))
    m, r = divmod(s, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}min"
    return f"{m}min {r:02d}s"


def _metricas_periodo(client, property_id: str, inicio: str, fim: str) -> dict:
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest

    req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=inicio, end_date=fim)],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="averageSessionDuration"),
            Metric(name="engagementRate"),
            Metric(name="eventCount"),
            Metric(name="sessions"),
        ],
    )
    resp = client.run_report(req)
    if not resp.rows:
        return {}
    row = resp.rows[0]
    vals = [float(v.value) if v.value else 0.0 for v in row.metric_values]

    return {
        "visualizacoes": int(vals[0]),
        "usuarios_ativos": int(vals[1]),
        "novos_usuarios": int(vals[2]),
        "tempo_medio_engajamento_seg": round(vals[3], 1),
        "taxa_engajamento": round(vals[4], 4),
        "contagem_eventos": int(vals[5]),
        "trafego_web_sessoes": int(vals[6]),
    }


def _usuarios_ativos_agora(client, property_id: str) -> int:
    from google.analytics.data_v1beta.types import Metric, RunRealtimeReportRequest

    req = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        metrics=[Metric(name="activeUsers")],
    )
    resp = client.run_realtime_report(req)
    if not resp.rows:
        return 0
    return int(resp.rows[0].metric_values[0].value or 0)


def _montar_relatorio(property_id: str) -> dict:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    inicio_coleta = _data_inicio_coleta()
    hoje = date.today().isoformat()
    client = BetaAnalyticsDataClient()

    desde = _metricas_periodo(client, property_id, inicio_coleta, hoje)
    # Últimos 30 dias (referência “visualizações/mês”)
    from datetime import timedelta

    fim = date.today()
    inicio_mes = (fim - timedelta(days=29)).isoformat()
    ultimos_30 = _metricas_periodo(client, property_id, inicio_mes, hoje)
    agora = _usuarios_ativos_agora(client, property_id)

    return {
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "inicio_coleta": inicio_coleta,
        "periodo_total": {"inicio": inicio_coleta, "fim": hoje},
        "desde_inicio_coleta": desde,
        "ultimos_30_dias": ultimos_30,
        "usuarios_ativos_agora": agora,
    }


def _markdown(rel: dict) -> str:
    t = rel.get("desde_inicio_coleta") or rel.get("desde_inauguracao") or {}
    m = rel.get("ultimos_30_dias") or {}
    agora = rel.get("usuarios_ativos_agora", 0)
    ini, fim = rel["periodo_total"]["inicio"], rel["periodo_total"]["fim"]

    return f"""# Data CFC WC2026 — Mídia kit (privado)

Período total: **{ini}** a **{fim}**  
Gerado em: {rel.get("atualizado_em", "")}

## Desde o início da coleta ({ini})

| Métrica | Valor |
|---------|------:|
| Visualizações (páginas) | {_fmt_int(t.get("visualizacoes"))} |
| Usuários ativos | {_fmt_int(t.get("usuarios_ativos"))} |
| Novos usuários | {_fmt_int(t.get("novos_usuarios"))} |
| Tempo médio de engajamento | {_fmt_duracao(t.get("tempo_medio_engajamento_seg"))} |
| Taxa de engajamento | {_fmt_pct(t.get("taxa_engajamento"))} |
| Contagem de eventos | {_fmt_int(t.get("contagem_eventos"))} |
| Tráfego web (sessões) | {_fmt_int(t.get("trafego_web_sessoes"))} |

## Últimos 30 dias (referência mensal)

| Métrica | Valor |
|---------|------:|
| Visualizações/mês | {_fmt_int(m.get("visualizacoes"))} |
| Usuários ativos | {_fmt_int(m.get("usuarios_ativos"))} |
| Novos usuários | {_fmt_int(m.get("novos_usuarios"))} |
| Tempo médio de engajamento | {_fmt_duracao(m.get("tempo_medio_engajamento_seg"))} |
| Taxa de engajamento | {_fmt_pct(m.get("taxa_engajamento"))} |
| Contagem de eventos | {_fmt_int(m.get("contagem_eventos"))} |
| Tráfego web (sessões) | {_fmt_int(m.get("trafego_web_sessoes"))} |

## Agora

- **Usuários ativos agora:** {_fmt_int(agora)}
"""


def main() -> int:
    _carregar_env_local()

    property_id = os.environ.get("GA4_PROPERTY_ID", "").strip()
    cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

    if not property_id:
        print(
            "Defina GA4_PROPERTY_ID (ID numérico da propriedade GA4).\n"
            "Execute: powershell -File automation\\configurar_analytics.ps1",
            file=sys.stderr,
        )
        return 1
    if not cred or not Path(cred).is_file():
        print(
            "Defina GOOGLE_APPLICATION_CREDENTIALS apontando para o JSON da service account.",
            file=sys.stderr,
        )
        return 1

    try:
        rel = _montar_relatorio(property_id)
    except Exception as exc:
        print(f"Erro ao consultar GA4: {exc}", file=sys.stderr)
        return 1

    PASTA_EXPORT.mkdir(parents=True, exist_ok=True)
    path_json = PASTA_EXPORT / "relatorio_midia_kit.json"
    path_md = PASTA_EXPORT / "relatorio_midia_kit.md"

    path_json.write_text(json.dumps(rel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path_md.write_text(_markdown(rel), encoding="utf-8")

    print(path_md.read_text(encoding="utf-8"))
    print(f"\nSalvo: {path_json}")
    print(f"Salvo: {path_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
