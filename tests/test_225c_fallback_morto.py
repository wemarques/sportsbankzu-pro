# -*- coding: utf-8 -*-
"""#225-c - `d.get(k, alternativa)` morre quando a chave existe valendo None.

Quatro correcoes do mesmo defeito antes de alguem notar que era o mesmo defeito
(#201, #208, #217, #225-b). Este arquivo trava o helper e impede que a forma
volte a aparecer nos caminhos de decisao.
"""
import ast
import os

import pytest

from backend.utils.valores import primeiro_valido, pegar


# ── o helper ────────────────────────────────────────────────────────────
def test_pula_none_e_para_no_primeiro_valido():
    assert primeiro_valido(None, None, 24, 99) == 24


def test_preserva_zero_falso_e_vazio():
    """`a or b` erraria os tres: 0 escanteios e resultado, nao ausencia."""
    assert primeiro_valido(None, 0, 24) == 0
    assert primeiro_valido(None, False, True) is False
    assert primeiro_valido(None, "", "x") == ""


def test_padrao_quando_tudo_e_none():
    assert primeiro_valido(None, None) is None
    assert primeiro_valido(None, None, padrao=0) == 0


def test_pegar_atravessa_a_chave_presente_com_none():
    """O caso exato do #225-b."""
    d = {"corners_recorded_matches_num": None, "matchesPlayed_home": 24}
    assert d.get("corners_recorded_matches_num", d.get("matchesPlayed_home")) is None  # o defeito
    assert pegar(d, "corners_recorded_matches_num", "matchesPlayed_home") == 24        # a correcao


def test_pegar_com_entrada_estranha():
    assert pegar(None, "a") is None
    assert pegar({}, "a", padrao=7) == 7
    assert pegar({"a": 0}, "a", "b") == 0


# ── a guarda contra a forma voltar ──────────────────────────────────────
# Modulos onde um fallback morto muda DECISAO (lambda, veto, classificacao,
# stake). Fora desta lista o defeito degrada texto de exibicao, o que e divida
# registrada, nao regressao bloqueante.
_CAMINHOS_DE_DECISAO = (
    "backend/modeling/corners/data_quality.py",
    "backend/modeling/corners_engine.py",
    "backend/modeling/cards_engine.py",
    "backend/modeling/lambda_calculator.py",
    "backend/services/ev_classification.py",
    "backend/services/bankroll_engine.py",
    "backend/services/data_governance.py",
)


def _gets_encadeados(caminho):
    """`x.get("a", y.get("b", ...))` — o segundo get e um fallback que morre."""
    try:
        with open(caminho, encoding="utf-8") as f:
            arvore = ast.parse(f.read())
    except (OSError, SyntaxError):
        return []
    achados = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "get" and len(no.args) == 2):
            continue
        alt = no.args[1]
        if isinstance(alt, ast.Call) and isinstance(alt.func, ast.Attribute) \
           and alt.func.attr == "get":
            chave = no.args[0]
            nome = chave.value if isinstance(chave, ast.Constant) else "?"
            achados.append((os.path.basename(caminho), no.lineno, nome))
    return achados


@pytest.mark.parametrize("caminho", _CAMINHOS_DE_DECISAO)
def test_caminho_de_decisao_sem_fallback_encadeado(caminho):
    """Use `pegar(d, "a", "b")` em vez de `d.get("a", d.get("b"))`.

    A cadeia morre no primeiro nome presente-com-None, e no caminho de decisao
    isso nao degrada exibicao — muda o numero publicado. Foi assim que o motor
    de escanteios inteiro foi para RESTRICTED com a temporada jogada (#225-b).
    """
    achados = _gets_encadeados(caminho)
    assert not achados, "\n".join(
        f"{a}:{ln} — .get(\"{k}\", <outro get>) morre se '{k}' existir valendo None; "
        f"troque por pegar(d, \"{k}\", ...)" for a, ln, k in achados
    )


def test_a_guarda_esta_mesmo_olhando_arquivos():
    """Se os caminhos sumirem, o teste acima ficaria verde para sempre."""
    for c in _CAMINHOS_DE_DECISAO:
        assert os.path.exists(c), f"{c} nao existe — a guarda perdeu o alvo"
