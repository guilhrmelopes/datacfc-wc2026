"""Marca o horário da última atualização do dashboard em copa_estado.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_ESTADO_MINIMO = {
    "rodada_cartola_atual": 1,
    "partidas_processadas": [],
}


def marcar_dashboard_atualizado(caminho_estado: Path) -> str:
    if caminho_estado.is_file():
        estado = json.loads(caminho_estado.read_text(encoding="utf-8"))
    else:
        estado = dict(_ESTADO_MINIMO)

    agora = datetime.now(timezone.utc).isoformat()
    estado["atualizado_em"] = agora
    caminho_estado.parent.mkdir(parents=True, exist_ok=True)
    caminho_estado.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return agora
