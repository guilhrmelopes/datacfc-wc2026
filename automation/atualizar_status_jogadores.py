"""Atualiza status_id e foto_url em jogadores_mercado.json (Cartola / Prováveis)."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"

SIT_PARA_STATUS = {"provavel": 6, "duvida": 2}
CARTOLA_ACEITOS_FORA_LINEUP = {2, 3, 5}


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    status_map: dict[int, int] = {}
    lineup_status: dict[int, int] = {}
    foto_map: dict[int, str] = {}

    try:
        mercado = _fetch(
            "https://provaveisdocartola.com.br/api/copa/cartola-mercado?_="
            + str(int(time.time() * 1000))
        )
        status_map = {a["atleta_id"]: a["status_id"] for a in mercado.get("atletas", [])}
        print(f"cartola-mercado: {len(status_map)} jogadores")
    except OSError as exc:
        print(f"Aviso: cartola-mercado indisponível — {exc}", file=sys.stderr)

    try:
        lineups = _fetch("https://provaveisdocartola.com.br/api/copa/lineups")
        for team in lineups.get("teams", {}).values():
            for titular in team.get("titulares", []):
                sit = titular.get("sit")
                if sit in SIT_PARA_STATUS:
                    lineup_status[titular["id"]] = SIT_PARA_STATUS[sit]
        print(f"lineups: {len(lineup_status)} titulares mapeados")
    except OSError as exc:
        print(f"Aviso: lineups indisponível — {exc}", file=sys.stderr)

    try:
        fotos_data = _fetch("https://provaveisdocartola.com.br/api/copa/fotos-atletas")
        foto_map = {
            int(aid): d["url"] for aid, d in fotos_data.get("atletas", {}).items()
        }
        print(f"fotos-atletas: {len(foto_map)} fotos")
    except OSError as exc:
        print(f"Aviso: fotos-atletas indisponível — {exc}", file=sys.stderr)

    jogadores = json.loads(CAMINHO.read_text(encoding="utf-8"))
    status_ok = fotos_ok = 0

    for j in jogadores:
        aid = j["atleta_id"]
        if aid in lineup_status:
            novo_status = lineup_status[aid]
        else:
            s = status_map.get(aid, 7)
            novo_status = s if s in CARTOLA_ACEITOS_FORA_LINEUP else 7

        if j.get("status_id") != novo_status:
            j["status_id"] = novo_status
            status_ok += 1

        nova_foto = foto_map.get(aid)
        if nova_foto and j.get("foto_url") != nova_foto:
            j["foto_url"] = nova_foto
            fotos_ok += 1

    CAMINHO.write_text(
        json.dumps(jogadores, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Status atualizados: {status_ok} | Fotos atualizadas: {fotos_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
