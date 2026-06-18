"""Atualiza status_id e foto_url — Cartola /copa + Prováveis (lineups) para status 6."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "frontend" / "public" / "data"
CAMINHO_ESTADO = DADOS / "copa_estado.json"

sys.path.insert(0, str(RAIZ / "src"))
from pipeline.cartola_copa_sync import sincronizar_status_fotos_cartola  # noqa: E402
from pipeline.timestamp_dashboard import marcar_dashboard_atualizado  # noqa: E402


def main() -> int:
    resumo = sincronizar_status_fotos_cartola(DADOS)
    print(
        f"Cartola Copa: status={resumo['status_campos_atualizados']} campos | "
        f"fotos={resumo['fotos_atualizadas']} | "
        f"provaveis_lineup={resumo.get('provaveis_lineup', 0)} | "
        f"mercado_api={resumo['mercado_api']} | "
        f"rodada={resumo['rodada_cartola_atual']}"
    )

    marcar_dashboard_atualizado(CAMINHO_ESTADO)
    print(f"Timestamp dashboard: {CAMINHO_ESTADO.name}")

    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
