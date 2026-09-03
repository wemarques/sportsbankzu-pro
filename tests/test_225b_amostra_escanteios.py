# -*- coding: utf-8 -*-
"""#225-b - a cadeia de fallback do motor de escanteios estava morta.

`d.get(k, alternativa)` so usa a alternativa quando a chave esta AUSENTE. Com a
chave presente valendo None — que e o caso, porque `fixtures_service.py:1950`
SEMPRE cria `corners_recorded_matches_num`, preenchida ou nao — o get devolve
None, `_safe_float(None)` da 0.0, `min_sample` vai a zero e o tier despenca para
INSUFFICIENT mesmo com a temporada inteira jogada.

Mesmo defeito que o #201 corrigiu no lambda com `_num()`, mesma forma do #208 e
do #217: ausencia de informacao tratada como informacao de ausencia.
"""
import pytest

from backend.modeling.corners.data_quality import compute_corners_data_quality


def _time(**kw):
    base = {"matchesPlayed_home": 24, "matchesPlayed_away": 24,
            "matchesPlayed_overall": 25, "homeCornersPerMatch": 5.4,
            "awayCornersPerMatch": 4.9, "cornersAVG_home": 5.4,
            "cornersAVG_away": 4.9}
    base.update(kw)
    return base


def test_chave_presente_e_nula_nao_zera_a_amostra():
    """O caso real: temporada inteira jogada e a contagem de escanteios nula."""
    casa = _time(corners_recorded_matches_num=None)
    fora = _time(corners_recorded_matches_num=None)
    r = compute_corners_data_quality(casa, fora)
    assert r["details"]["home_corner_sample"] == 24, r["details"]
    assert r["details"]["away_corner_sample"] == 24, r["details"]
    assert r["sample_adequacy_score"] > 0.8


def test_chave_ausente_tambem_cai_no_fallback():
    r = compute_corners_data_quality(_time(), _time())
    assert r["details"]["home_corner_sample"] == 24


def test_valor_real_tem_precedencia_sobre_o_fallback():
    """Quando a FootyStats manda a contagem, e ela que vale."""
    r = compute_corners_data_quality(
        _time(corners_recorded_matches_num=8),
        _time(corners_recorded_matches_num=8),
    )
    assert r["details"]["home_corner_sample"] == 8


def test_amostra_realmente_zero_continua_zero():
    """0 informado e diferente de None: se a fonte diz zero, e zero."""
    r = compute_corners_data_quality(
        _time(corners_recorded_matches_num=0, matchesPlayed_home=0,
              matchesPlayed_overall=0),
        _time(corners_recorded_matches_num=0, matchesPlayed_away=0,
              matchesPlayed_overall=0),
    )
    assert r["details"]["home_corner_sample"] == 0


def test_media_de_escanteios_nula_cai_no_proximo_nome():
    """Mesma cadeia morta no `has_corners`: presente-com-None matava o fallback."""
    r = compute_corners_data_quality(
        _time(corners_total_per_match=None),
        _time(corners_total_per_match=None),
    )
    assert r["sample_adequacy_score"] > 0.8
    assert r["data_quality_tier"] != "INSUFFICIENT"


def test_sem_dado_nenhum_de_escanteio_o_tier_cai():
    """A correcao nao pode transformar ausencia real em qualidade inventada."""
    vazio = {"matchesPlayed_overall": 25}
    r = compute_corners_data_quality(vazio, vazio)
    assert r["data_quality_tier"] in ("LOW", "INSUFFICIENT", "MEDIUM")
