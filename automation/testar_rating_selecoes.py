"""Testes do rating híbrido / Elo KO."""

from __future__ import annotations

from scrapers.rating_selecoes_copa import (
    aplicar_ratings_selecoes,
    calcular_elo_ko,
    calcular_rating_scouts,
    jogos_ko_por_sigla,
    rating_hibrido,
)


def _sel(sigla: str, j: float, **metricas):
    base = {
        "goals_team_match": 1.5,
        "goals_conceded_team_match": 1.0,
        "possession_percentage_team": 50.0,
        "clean_sheet_team": 1.0,
        "expected_goals_team": 4.5,
        "expected_goals_conceded_team": 3.0,
        "ontarget_scoring_att_team": 4.0,
        "big_chance_team": 5.0,
        "touches_in_opp_box_team": 40.0,
        "total_tackle_team": 14.0,
        "poss_won_att_3rd_team": 3.0,
        "saves_team": 2.0,
        "fk_foul_lost_team": 10.0,
        "total_yel_card_team": 2.0,
        "total_red_card_team": 0.0,
        "J": j,
    }
    base.update(metricas)
    return {
        "selecao": sigla,
        "sigla": sigla,
        "rating_elo_100": 70.0,
        "elo_rating": 1800.0,
        "metricas_coletivas": base,
    }


def test_jogos_ko_e_elo():
    mata = {
        "fases": [
            {
                "stage": "1/8",
                "confrontos": [
                    {
                        "finalizada": True,
                        "mandante_venceu": True,
                        "visitante_venceu": False,
                        "placar_mandante": 2,
                        "placar_visitante": 0,
                        "data": "2026-07-04",
                        "hora": "12:00:00",
                        "match_id": "1",
                        "mandante": {"sigla": "ARG", "tbd": False},
                        "visitante": {"sigla": "EGI", "tbd": False},
                    }
                ],
            }
        ]
    }
    assert jogos_ko_por_sigla(mata) == {"ARG": 1, "EGI": 1}
    elo = calcular_elo_ko(mata, {"ARG": 2000.0, "EGI": 1600.0})
    assert elo["ARG"] > 2000.0
    assert elo["EGI"] < 1600.0


def test_hibrido_e_scouts():
    pool = [
        _sel("ARG", 5, goals_team_match=2.8, expected_goals_team=12.0),
        _sel("BRA", 5, goals_team_match=1.2, expected_goals_team=5.0),
        _sel("PAR", 3, goals_team_match=0.6, expected_goals_team=1.6),
    ]
    r_arg = calcular_rating_scouts(pool[0], pool)
    r_par = calcular_rating_scouts(pool[2], pool)
    assert r_arg is not None and r_par is not None
    assert r_arg > r_par
    h = rating_hibrido(elo_100=90.0, scouts_100=80.0, ko_100=75.0, jogos_ko=2)
    assert h is not None and 70 < h < 95


def test_aplicar_ratings():
    mata = {
        "fases": [
            {
                "stage": "1/16",
                "confrontos": [
                    {
                        "finalizada": True,
                        "mandante_venceu": True,
                        "visitante_venceu": False,
                        "placar_mandante": 1,
                        "placar_visitante": 0,
                        "data": "2026-06-29",
                        "hora": "15:00:00",
                        "match_id": "1",
                        "mandante": {"sigla": "ARG", "tbd": False},
                        "visitante": {"sigla": "CAB", "tbd": False},
                    }
                ],
            }
        ]
    }
    selecoes = [
        _sel("ARG", 4),
        _sel("CAB", 4),
        _sel("BRA", 3),
    ]
    resumo = aplicar_ratings_selecoes(selecoes, mata)
    assert resumo["com_elo_ko"] == 2
    assert selecoes[0]["rating_copa_100"] is not None
    assert selecoes[0]["jogos_mata_mata"] == 1
    assert selecoes[2]["rating_ko_100"] is None


if __name__ == "__main__":
    test_jogos_ko_e_elo()
    test_hibrido_e_scouts()
    test_aplicar_ratings()
    print("ok")
