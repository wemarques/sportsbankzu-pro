"""Enforcement da recomendacao vs. tabela de EV deflacionado (Camada 7).

Caso real observado em producao (KRC Genk x Waasland-Beveren, 2026-08-28):
a Sugestao da Analise AI exibia "Double Chance 1X (odd 1.14). Probabilidade
de 87% (EV positivo)" enquanto a tabela de mercados do MESMO jogo listava
"DC 1X (KRC/EMP) | 84% raw -> 63% cal | EV -29.8% — EV negativo apos
deflacao" no bloco NAO RECOMENDADOS.

Duas brechas combinadas permitiram isso:
1. O prompt #096 permitia "um mercado complementar" fora da lista de picks.
2. A validacao #181 era log-only e o padrao de mercado nao cobria a grafia
   inglesa "Double Chance" (so "Dupla chance" / "DC 1X").

Este teste protege o fix: padrao Double Chance detectado + substituicao
deterministica via _enforce_recommendation_contract / aligned_recommendation.
"""
from backend.ai.mistral_contract import (
    ApprovedPick,
    aligned_recommendation,
    validate_output,
)
from backend.services.mistral_analysis import MistralAnalysisService


KRC_GENK_PICKS = [
    {"market": "Escanteios Over 8.5", "classification": "VIAVEL",
     "prob_pct": 52.0, "odd": 1.92, "ev_pct": 1.8},
    {"market": "Over 3.5 gols", "classification": "VIAVEL",
     "prob_pct": 56.0, "odd": 1.79, "ev_pct": 2.4},
]

KRC_GENK_BAD_RECOMMENDATION = (
    "Double Chance 1X (odd 1.14). Probabilidade de 87% (EV positivo) cobre "
    "vitoria casa ou empate, alinhado ao dominio ofensivo de Genk."
)


def _approved():
    return [
        ApprovedPick("Escanteios Over 8.5", "VIAVEL", 52.0, 1.92, 1.8),
        ApprovedPick("Over 3.5 gols", "VIAVEL", 56.0, 1.79, 2.4),
    ]


# ---- deteccao (mistral_contract) -------------------------------------------

def test_double_chance_english_detected_as_violation():
    """Grafia inglesa 'Double Chance 1X' passava sem deteccao pelo padrao DC."""
    v = validate_output(KRC_GENK_BAD_RECOMMENDATION, _approved())
    assert v["ok"] is False
    assert any("Double Chance" in viol for viol in v["violations"])


def test_dupla_chance_with_line_detected():
    v = validate_output("Sugiro Dupla chance 1X neste jogo.", _approved())
    assert v["ok"] is False


def test_1x2_mention_detected():
    v = validate_output("O mercado 1X2 Home oferece valor.", _approved())
    assert v["ok"] is False


# ---- substituicao deterministica -------------------------------------------

def test_aligned_recommendation_uses_top_ev_pick():
    text = aligned_recommendation(_approved())
    assert "Over 3.5 gols" in text  # maior EV entre aprovados
    assert "1.79" in text


def test_aligned_recommendation_without_picks_says_no_recommendation():
    text = aligned_recommendation([])
    assert "Sem recomenda" in text


# ---- enforcement de ponta a ponta (Camada 7) --------------------------------

def test_enforce_replaces_krc_genk_regression():
    """O caso de producao: recomendacao rejeitada pela tabela e substituida."""
    out = MistralAnalysisService._enforce_recommendation_contract(
        KRC_GENK_BAD_RECOMMENDATION, KRC_GENK_PICKS,
        match_label="KRC Genk vs Waasland-Beveren",
    )
    assert "Double Chance" not in out
    assert "Over 3.5 gols" in out


def test_enforce_keeps_clean_recommendation():
    clean = (
        "Over 3.5 gols e o pick principal: dominio ofensivo do mandante e "
        "defesa visitante instavel sustentam o cenario de muitos gols."
    )
    out = MistralAnalysisService._enforce_recommendation_contract(
        clean, KRC_GENK_PICKS,
    )
    assert out == clean


def test_enforce_without_picks_blocks_any_market():
    out = MistralAnalysisService._enforce_recommendation_contract(
        KRC_GENK_BAD_RECOMMENDATION, [],
    )
    assert "Sem recomenda" in out


def test_enforce_empty_recommendation_passthrough():
    assert MistralAnalysisService._enforce_recommendation_contract("", KRC_GENK_PICKS) == ""
