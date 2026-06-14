"""Sincroniza mercado (Cartola + FotMob) antes do scrape de odds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline.copa_atualizar import executar_atualizacao  # noqa: E402

DADOS = RAIZ / "frontend" / "public" / "data"


def main() -> int:
    resumo = executar_atualizacao(DADOS)
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
