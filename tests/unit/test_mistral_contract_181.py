"""Test #181 — Mistral input/output contract (full-text validation).

Diagnostic context: bug 2026-05-04 (Sporting CP x Vitoria Guimaraes) where
Mistral narrative cited "Under 3.5 odd 1.67 prob 70% EV +16.9%" while
display showed "Under 3.5 odd 1.70 prob 56-58%" — gap = exact deflation
amount per regra #105. validate_output now catches this class of violation
in resumo_analitico/key_points (Camada 6 only inspected recomendacao_principal).
"""
import logging

from backend.ai.mistral_contract import (
    ApprovedPick,
    fallback_narrative,
    log_violations,
    validate_output,
)


def _approved():
    return [
        ApprovedPick("Under 3.5 gols", "VIAVEL", 57.0, 1.70, -3.0),
        ApprovedPick("Escanteios Over 8.5", "VIAVEL", 50.0, 1.94, +2.0),
    ]


def test_validate_passes_clean_narrative():
    text = (
        "Under 3.5 gols faz sentido neste confronto — ambas equipes com media "
        "ofensiva moderada, sem incentivos taticos para uma corrida de gols."
    )
    v = validate_output(text, _approved())
    assert v["ok"] is True
    assert v["violations"] == []


def test_validate_detects_market_outside_list():
    """Sugestao Over 2.5 nao deveria existir — pipeline aprovou Under 3.5."""
    text = (
        "Recomendacao adicional: Over 2.5 gols (odd 1.47) parece interessante "
        "dado o ataque do mandante."
    )
    v = validate_output(text, _approved())
    assert v["ok"] is False
    assert any("Over 2.5" in violation for violation in v["violations"])


def test_validate_detects_ev_computation():
    """O bug observado em producao: Mistral fabrica numero de EV."""
    text = (
        "Under 3.5 gols e a melhor opcao (odd 1.67, prob 70%, EV +16.9%) "
        "considerando o historico recente."
    )
    v = validate_output(text, _approved())
    assert v["ok"] is False
    assert any("EV" in violation for violation in v["violations"])


def test_validate_handles_empty_text():
    """Texto vazio nao gera violacao — fail open por design."""
    v = validate_output("", _approved())
    assert v["ok"] is True


def test_validate_handles_empty_approved_list():
    """Sem picks aprovados, qualquer mercado mencionado e violacao
    EXCETO quando o texto nao menciona nenhum mercado."""
    text = "Jogo bastante equilibrado, sem favorito claro."
    v = validate_output(text, [])
    assert v["ok"] is True
    text_with_market = "Recomendo Over 2.5 gols."
    v2 = validate_output(text_with_market, [])
    assert v2["ok"] is False


def test_fallback_lists_top_pick():
    fb = fallback_narrative(_approved())
    assert "Under 3.5 gols" in fb
    assert "57" in fb
    assert "1.70" in fb


def test_fallback_handles_empty():
    fb = fallback_narrative([])
    assert "Sem picks" in fb


def test_log_violations_emits_warning(caplog):
    """log_violations escreve no logger sportsbankzu.mistral.contract."""
    caplog.set_level(logging.WARNING, logger="sportsbankzu.mistral.contract")
    log_violations(["Mercado fora da lista: 'Over 2.5'"], match_label="Sporting vs Vitoria")
    msgs = [r.message for r in caplog.records]
    assert any("Sporting" in m and "Over 2.5" in m for m in msgs)


def test_approved_pick_short_label_formatting():
    pick = ApprovedPick("Under 3.5 gols", "VIAVEL", 57.0, 1.70, -3.0)
    label = pick.short_label()
    assert "VIAVEL" in label
    assert "Under 3.5 gols" in label
    assert "57.0%" in label
    assert "odd 1.70" in label
