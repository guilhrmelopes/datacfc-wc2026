"""Avalia precisão do matching Cartola ↔ nomes simulados (OddsNotifier)."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scrapers.matching_cartola import (  # noqa: E402
    melhor_jogador_para_nome,
)

CAMINHO_MERCADO = RAIZ / "frontend" / "public" / "data" / "jogadores_mercado.json"


def _variantes_nome(apelido: str, nome: str) -> list[str]:
    """Simula formatos comuns do OddsNotifier."""
    base = apelido or nome
    partes = base.split()
    out = [
        base,
        base.upper(),
        f"{base} (Score)",
        f"{base} (Assist)",
        f"{base} (Score Or Assist) (1)",
    ]
    if len(partes) >= 2:
        out.append(f"{partes[-1]} {partes[0][0]}")
        out.append(f"{partes[0][0]}. {partes[-1]}")
        out.append(" ".join(reversed(partes)))
    if nome and nome != base:
        out.append(nome)
    return out


def main() -> int:
    mercado: list[dict] = json.loads(CAMINHO_MERCADO.read_text(encoding="utf-8"))
    por_sigla: dict[str, list[dict]] = {}
    for j in mercado:
        sig = j.get("sigla") or "?"
        por_sigla.setdefault(sig, []).append(j)

    total = 0
    acertos = 0
    falhas: list[str] = []

    random.seed(42)
    for sigla, elenco in por_sigla.items():
        if len(elenco) < 3:
            continue
        amostra = random.sample(elenco, min(8, len(elenco)))
        for jog in amostra:
            for var in _variantes_nome(jog.get("apelido", ""), jog.get("nome", "")):
                total += 1
                aid_exp = int(jog["atleta_id"])
                melhor, score = melhor_jogador_para_nome(var, elenco, min_score=70)
                if melhor and int(melhor["atleta_id"]) == aid_exp:
                    acertos += 1
                else:
                    got = int(melhor["atleta_id"]) if melhor else None
                    falhas.append(
                        f"{sigla}: {var!r} -> esperado {aid_exp}, obteve {got} (score={score})"
                    )

    pct = (acertos / total * 100) if total else 0.0
    print(f"Matching simulado: {acertos}/{total} ({pct:.1f}%)")
    if falhas:
        print(f"Falhas ({len(falhas)}):")
        for linha in falhas[:25]:
            print(f"  {linha}")
        if len(falhas) > 25:
            print(f"  ... +{len(falhas) - 25}")
    return 0 if pct >= 98.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
