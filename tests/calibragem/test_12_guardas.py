# -*- coding: utf-8 -*-
"""Testes 1b, 7 e 9 da spec — os invariantes que atravessam modulos."""
import pathlib

import pytest

from backend.modeling.calibragem.curva import aplicar
from backend.services.ev_classification import _filter_corridor_bets

PACOTE = pathlib.Path("backend/modeling/calibragem")


def test_9_nenhum_modulo_do_pacote_le_audit_results():
    """Regra #244: a fonte de calibracao e o ledger, nunca o audit."""
    ofensores = [f.name for f in PACOTE.glob("*.py")
                 if "audit_results" in f.read_text(encoding="utf-8")]
    assert not ofensores, ofensores


# Lista FECHADA de quem pode chamar o legado. Nao e "quem chama hoje": e
# quem morre junto com a versao 0.
#   curva.py      — o serving: `aplicar_versao` delega quando a celula esta
#                   na versao 0. E a razao de `legado.py` existir.
#   linha_base.py — a MEDICAO da versao 0 (#248, C1): ajusta (a0, b0) a curva
#                   legada para a trava de passo e a re-derivacao de limiares
#                   terem contra o que medir. Nao serve numero a ninguem; some
#                   no mesmo dia que `legado.py`.
# Qualquer terceiro nome aqui significa que a pilha legada voltou a se
# espalhar, e ai `legado.py` nunca mais e deletavel — que e o que este teste
# existe para impedir.
CHAMADORES_PERMITIDOS_DO_LEGADO = ["curva.py", "linha_base.py"]


def test_1b_legado_so_tem_os_chamadores_permitidos():
    """Enquanto houver celula na versao 0 o legado vive — com chamadores
    contados, todos eles deletaveis junto com ele."""
    chamadores = sorted(f.name for f in PACOTE.glob("*.py")
                        if f.name != "legado.py"
                        and "calibrar_legado" in f.read_text(encoding="utf-8"))
    assert chamadores == sorted(CHAMADORES_PERMITIDOS_DO_LEGADO), chamadores


def test_1b_legado_esta_marcado_como_congelado():
    fonte = (PACOTE / "legado.py").read_text(encoding="utf-8")
    assert "PROIBIDO EDITAR" in fonte


class _M:
    """Dublê minimo de MarketOutput para o filtro de corredor."""
    def __init__(self, market_type, selection, prob):
        self.market_type = market_type
        self.selection = selection
        self.calibrated_probability = prob
        self.raw_probability = prob


def test_7_a_curva_preserva_a_decisao_do_corredor():
    """A monotonicidade protege o #246-a: a correcao nao pode reordenar linhas.

    Numeros reais de Toronto x Nashville SC (09/09/2026), geracao 03:09.
    """
    brutos = {"Over 1.5": 0.810, "Under 2.5": 0.425, "Over 2.5": 0.575,
              "Under 3.5": 0.649, "Over 3.5": 0.351, "Under 4.5": 0.816}

    def decidir(probs):
        mercados = [_M("Over/Under", sel, p) for sel, p in probs.items()]
        sobreviventes = _filter_corridor_bets(mercados)
        return sorted(m.selection for m in sobreviventes)

    sem_camada = decidir(brutos)
    for a, b in ((0.45, 1.0), (0.0, 0.7), (0.3, 1.2), (-0.2, 0.9), (0.9, 1.5)):
        com_camada = decidir({s: aplicar(p, a, b) for s, p in brutos.items()})
        assert com_camada == sem_camada, (a, b, com_camada, sem_camada)


def test_7_qualquer_b_positivo_preserva_a_ordem():
    brutos = [0.05, 0.2, 0.351, 0.5, 0.649, 0.81, 0.95]
    for a, b in ((0.0, 0.1), (2.0, 3.0), (-1.5, 0.4)):
        corrigidos = [aplicar(p, a, b) for p in brutos]
        assert corrigidos == sorted(corrigidos), (a, b)


# ─── C3: a trava contra a TERCEIRA ocorrencia da mesma classe de defeito ────
#
# Duas vezes um rotulo de producao deixou de resolver familia e o efeito foi
# invisivel: na Task 3 os rotulos do ledger em ingles ("Corners Over 7.5")
# caiam em Over/Under; no C3 os rotulos do serving ("Double Chance 1X")
# levantavam ValueError que `aplicar_versao` engolia. Listar rotulos a mao
# nao trava a terceira: um mercado novo entra em `ev_classification` e a
# lista do teste continua verde. Este teste LE os rotulos direto das
# chamadas a `_calibrar_com_detalhe` no fonte de producao.

def _rotulos_das_chamadas_de_producao():
    """Extrai, por AST, o 2o argumento de cada `_calibrar_com_detalhe(...)`.

    Constantes entram como estao. f-strings viram o literal com cada campo
    interpolado substituido por "2.5" — o token de familia vive sempre na
    parte LITERAL do rotulo (`f"Over {threshold}"`, `f"Cartoes Over {line}"`),
    entao o valor do campo nao muda a familia e um placeholder serve.
    """
    import ast

    fonte = pathlib.Path("backend/services/ev_classification.py").read_text(
        encoding="utf-8")
    rotulos = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
        if nome != "_calibrar_com_detalhe" or len(no.args) < 2:
            continue
        arg = no.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            rotulos.append(arg.value)
        elif isinstance(arg, ast.JoinedStr):
            partes = []
            for p in arg.values:
                if isinstance(p, ast.Constant) and isinstance(p.value, str):
                    partes.append(p.value)
                else:
                    partes.append("2.5")
            rotulos.append("".join(partes))
    return sorted(set(rotulos))


def test_todo_rotulo_chamado_em_producao_resolve_familia():
    from backend.modeling.calibragem.curva import familia_do_mercado

    rotulos = _rotulos_das_chamadas_de_producao()
    assert len(rotulos) >= 8, (
        "o scanner de AST nao achou as chamadas de producao — "
        f"achou {rotulos}; o alvo ou a assinatura mudaram?")

    sem_familia = []
    for r in rotulos:
        try:
            familia_do_mercado(r)
        except ValueError:
            sem_familia.append(r)
    assert not sem_familia, (
        f"rotulos servidos em producao que nao resolvem familia: {sem_familia}. "
        "Eles ficam presos na versao 0 para sempre, por mais que o estimador "
        "aprenda a familia deles. Acrescente o token em curva._FAMILIAS.")
