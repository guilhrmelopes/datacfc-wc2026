"""Testa parser de payload API OddsNotifier (sem browser)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from scrapers.captura_odds_api import extrair_odds_de_payload, extrair_sg_de_payload  # noqa: E402
from scrapers.scraper_odds_jogadores import extrair_odds_rsc, extrair_sg_times  # noqa: E402

SAMPLE = {
    "bookmakers": {
        "Bet365": [
            {
                "name": "Anytime Goalscorer",
                "updatedAt": "2026-06-17T00:00:00Z",
                "odds": [
                    {"label": "Harry Kane", "hdp": 0, "over": "2.50"},
                ],
            },
            {
                "name": "Player To Score or Assist",
                "updatedAt": "2026-06-17T00:00:00Z",
                "odds": [
                    {"label": "Harry Kane (Score) (1)", "hdp": 0, "over": "2.50"},
                    {"label": "Harry Kane (Assist) (2)", "hdp": 0, "over": "5.00"},
                ],
            },
            {
                "name": "Team Total Home",
                "updatedAt": "2026-06-17T00:00:00Z",
                "odds": [
                    {"label": "Over", "hdp": 0.5, "over": "3.00", "under": "1.40"},
                ],
            },
            {
                "name": "Team Total Away",
                "updatedAt": "2026-06-17T00:00:00Z",
                "odds": [
                    {"label": "Over", "hdp": 0.5, "over": "2.00", "under": "1.80"},
                ],
            },
        ],
    },
}


def main() -> int:
    odds = extrair_odds_de_payload(SAMPLE, extrair_odds_rsc)
    sg = extrair_sg_de_payload(SAMPLE, extrair_sg_times)
    g, a, ga = len(odds["g"]), len(odds["a"]), len(odds["ga"])
    print(f"parser: g={g} a={a} ga={ga} sg_home={bool(sg[0])} sg_away={bool(sg[1])}")

    if g < 1 or a < 1 or not sg[0] or not sg[1]:
        print("FALHA: parser API incompleto.")
        return 1

    print("OK: parser API unitario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
