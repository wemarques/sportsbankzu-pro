"""Test #184 — xG filter None-guard prevents silent record drops."""


def test_ajustar_lambda_handles_none_games_played():
    """games_played=None must not crash; should yield no adjustment."""
    from backend.modeling.xg_filter import ajustar_lambda_por_xg

    lam_adj, adjusted, _meta = ajustar_lambda_por_xg(
        lambda_original=2.5, goals_scored=20, xg=15, games_played=None,
    )
    assert lam_adj == 2.5
    assert adjusted is False


def test_ajustar_lambda_handles_none_goals():
    """goals_scored=None must not crash."""
    from backend.modeling.xg_filter import ajustar_lambda_por_xg

    lam_adj, adjusted, _meta = ajustar_lambda_por_xg(
        lambda_original=2.5, goals_scored=None, xg=15, games_played=10,
    )
    assert lam_adj == 2.5
    assert adjusted is False


def test_ajustar_lambda_handles_none_xg():
    """xg=None must not crash."""
    from backend.modeling.xg_filter import ajustar_lambda_por_xg

    lam_adj, adjusted, _meta = ajustar_lambda_por_xg(
        lambda_original=2.5, goals_scored=20, xg=None, games_played=10,
    )
    assert lam_adj == 2.5
    assert adjusted is False


def test_aplicar_filtro_completo_with_team_data_all_none():
    """Both teams missing data — short-circuit at validar_dados_xg, no crash."""
    from backend.modeling.xg_filter import aplicar_filtro_completo

    home_data = {"games_played": None, "goals_scored": None, "xg": None}
    away_data = {"games_played": None, "goals_scored": None, "xg": None}

    lam_h, lam_a, meta = aplicar_filtro_completo(
        lambda_home=1.5, lambda_away=1.2,
        home_team_data=home_data, away_team_data=away_data,
        enable_filter=True,
    )
    assert lam_h == 1.5
    assert lam_a == 1.2
    # validar_dados_xg returns False for both teams → early return with this shape
    assert meta.get("data_valid") is False


def test_aplicar_filtro_completo_with_partial_none():
    """Only one team missing — pipeline must produce a result for the other."""
    from backend.modeling.xg_filter import aplicar_filtro_completo

    home_data = {"games_played": 15, "goals_scored": 25, "xg": 18}
    away_data = {"games_played": None, "goals_scored": None, "xg": None}

    lam_h, lam_a, _meta = aplicar_filtro_completo(
        lambda_home=1.5, lambda_away=1.2,
        home_team_data=home_data, away_team_data=away_data,
        enable_filter=True,
    )
    assert lam_h is not None
    assert lam_a == 1.2  # away unchanged due to missing data


def test_match_label_uses_team_a_name_keys():
    """The skip-log label must use team_a_name/team_b_name (DataMapper schema)."""
    with open('backend/services/fixtures_service.py', encoding='utf-8') as f:
        src = f.read()
    label_lines = [ln for ln in src.split('\n') if '_match_label' in ln and 'r.get' in ln]
    assert label_lines, "_match_label assignment not found"
    assert any("team_a_name" in ln for ln in label_lines), "label still uses old keys only"
