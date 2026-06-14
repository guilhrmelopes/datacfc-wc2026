"""Atualiza status_id e foto_url em jogadores_mercado.json (Cartola / Prováveis)."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"
CAMINHO_ESTADO = RAIZ / "frontend" / "public" / "data" / "copa_estado.json"

sys.path.insert(0, str(RAIZ / "src"))
from pipeline.timestamp_dashboard import marcar_dashboard_atualizado  # noqa: E402

SIT_PARA_STATUS = {"provavel": 6, "duvida": 2}
CARTOLA_ACEITOS_FORA_LINEUP = {2, 3, 5}
FOTO_GLOBO_HOST = "s.sde.globo.com"
URL_MERCADO_CARTOLA = "https://api.cartola.globo.com/copa/atletas/mercado"


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

    cartola_fotos: dict[int, str] = {}
    try:
        mercado_cartola = _fetch(URL_MERCADO_CARTOLA)
        cartola_fotos = {
            int(a["atleta_id"]): a["foto"]
            for a in mercado_cartola.get("atletas") or []
            if a.get("atleta_id") and a.get("foto")
        }
        print(f"cartola-mercado fotos: {len(cartola_fotos)}")
    except OSError as exc:
        print(f"Aviso: cartola mercado indisponível — {exc}", file=sys.stderr)

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

        nova_foto = foto_map.get(aid) or cartola_fotos.get(aid)
        atual_foto = j.get("foto_url")
        if nova_foto and (
            not atual_foto
            or FOTO_GLOBO_HOST in str(atual_foto)
            or atual_foto != nova_foto
        ):
            j["foto_url"] = nova_foto
            fotos_ok += 1

    CAMINHO.write_text(
        json.dumps(jogadores, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Status atualizados: {status_ok} | Fotos atualizadas: {fotos_ok}")

    marcar_dashboard_atualizado(CAMINHO_ESTADO)
    print(f"Timestamp dashboard: {CAMINHO_ESTADO.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
