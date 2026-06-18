"""Testa auto-aprendizado de aliases OddsNotifier (Etapa 4)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import scrapers.mapeamento_odds as mo  # noqa: E402
from scrapers.mapeamento_odds import (  # noqa: E402
    carregar_mapeamento,
    jogador_por_alias,
    registrar_alias_aprendido,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "mapeamento_teste.json"
        mo.CAMINHO_MAPEAMENTO = caminho
        mo._cache = None

        jogador = {
            "atleta_id": 999001,
            "apelido": "Test Player",
            "sigla": "TST",
        }
        pool = [jogador]

        ok = registrar_alias_aprendido("Test Player (Score)", jogador, 98)
        if not ok:
            print("FALHA: registrar_alias_aprendido retornou False.")
            return 1

        data = json.loads(caminho.read_text(encoding="utf-8"))
        aliases = data["por_atleta_id"]["999001"]["aliases_odds"]
        if "Test Player" not in aliases:
            print("FALHA: alias nao persistido.", aliases)
            return 1

        mo._cache = None
        resolvido, score = jogador_por_alias("Test Player (Score)", pool)
        if not resolvido or int(resolvido["atleta_id"]) != 999001 or score != 100:
            print("FALHA: alias nao resolve apos salvar.")
            return 1

        dup = registrar_alias_aprendido("Test Player (Score)", jogador, 98)
        if dup:
            print("FALHA: alias duplicado foi registrado novamente.")
            return 1

        conflito = registrar_alias_aprendido("Test Player", {"atleta_id": 999002, "sigla": "TST"}, 99)
        if conflito:
            print("FALHA: alias conflitante aceito para outro atleta.")
            return 1

    print("OK: auto-aprendizado de aliases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
