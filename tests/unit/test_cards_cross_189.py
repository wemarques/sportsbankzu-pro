"""#189-b — cross-estimate simétrico no motor de cartões.

Auditoria 2026-08-29: o código dividia os termos "against" por 2
individualmente — (hf + aa/2 + af + ha/2)/2 — contradizendo o próprio
comentário e o padrão do corners_engine, e viesando o λ de cartões em
~-10% (-0.4 cartões num jogo típico de 4): "Under" inflado, "Over"
deflacionado. A fórmula simétrica correta: (hf + aa + af + ha)/2, i.e.
λ_time ≈ média(própria média, cartões que o adversário provoca).

Também: dados "against" ausentes viram 0.0 via _safe_float e o cross com
zeros arrastava λ para 0.8λ — agora o cross exige against > 0.
"""
import pytest

from backend.modeling.cards_engine import predict_cards


LEAGUE = {"cardsAVG_overall": 4.0}


def _predict(hf, af, ha=None, aa=None):
    home = {"homeCardsPerMatch": hf}
    away = {"awayCardsPerMatch": af}
    if ha is not None:
        home["homeCardsAgainstPerMatch"] = ha
    if aa is not None:
        away["awayCardsAgainstPerMatch"] = aa
    return predict_cards(home, away, league_id="", league_stats=LEAGUE)


def _lambda(result):
    for key in ("cards_lambda", "lambda_adjusted", "projected_total_cards"):
        if key in result:
            return float(result[key])
    raise AssertionError(f"nenhuma chave de lambda em {sorted(result.keys())}")


def test_dados_simetricos_nao_alteram_lambda():
    """Se médias 'for' e 'against' coincidem, o cross deve ser neutro."""
    r = _predict(2.0, 2.0, ha=2.0, aa=2.0)
    assert _lambda(r) == pytest.approx(4.0, abs=1e-3)


def test_formula_simetrica_caso_auditoria():
    """hf=2.1 af=1.9 ha=2.0 aa=2.2: cross=(2.1+2.2+1.9+2.0)/2=4.10 →
    λ = 0.6*4.0 + 0.4*4.10 = 4.04 (o código antigo dava 3.62)."""
    r = _predict(2.1, 1.9, ha=2.0, aa=2.2)
    assert _lambda(r) == pytest.approx(4.04, abs=1e-3)


def test_against_ausente_nao_arrasta_lambda():
    """Sem dado de cartões sofridos, λ deve ficar em hf+af (não 0.8×)."""
    r = _predict(2.0, 2.0)
    assert _lambda(r) == pytest.approx(4.0, abs=1e-3)


def test_against_zero_nao_arrasta_lambda():
    r = _predict(2.0, 2.0, ha=0.0, aa=0.0)
    assert _lambda(r) == pytest.approx(4.0, abs=1e-3)


def test_over_probabilities_sobem_com_fix():
    """λ maior (sem o viés -10%) ⇒ P(Over) maior que sob o código antigo."""
    r = _predict(2.1, 1.9, ha=2.0, aa=2.2)
    lam = _lambda(r)
    assert lam > 0.6 * 4.0 + 0.4 * 3.05  # 3.62 = valor do código antigo
