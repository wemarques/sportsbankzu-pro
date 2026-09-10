# -*- coding: utf-8 -*-
"""A linha de base da VERSAO 0, para medir contra ela.

O defeito que este modulo fecha (#248, C1): tres lugares supunham que a
versao 0 era a curva IDENTIDADE `(a=0, b=1)` — a trava de passo em
`ciclo.executar`, o `parametros_antigos` da re-derivacao de limiares, e o
teste de volume constante. Ela nao e. A versao 0 delega a
`legado.calibrar_legado`, a pilha inteira de deflacao, que fica de 12 a 25
pontos de probabilidade ABAIXO da identidade (medido: 12,25pp de distancia
maxima no ramo de meia-banda, 24,50pp no de banda inteira).

Consequencia da suposicao errada, medida contra o ledger real antes da
correcao: o primeiro ciclo moveria +5,03pp em Over/Under, +11,14pp em
Corners e +12,24pp em Cards, com maximo de +24,95pp — contra uma trava
declarada de 2pp. A trava media a distancia ate uma curva que nunca foi
publicada a ninguem.

ESTE MODULO NAO MUDA O QUE A VERSAO 0 SERVE. `curva.aplicar_versao` continua
delegando ao legado, byte a byte. `(a0, b0)` existe SO como referencial de
medicao — trava de passo e limiares. Como so serve a versao 0, morre junto
com `legado.py` quando nenhuma celula referenciar mais a versao 0.

## Limite conhecido da aproximacao (medido, nao estimado)

Dois parametros no logit NAO reproduzem a pilha de bandas — a propria spec
diz isso na secao 6.1, e a medicao confirma. O erro maximo do ajuste por
minimos quadrados no logit, sobre `p` em [0,02; 0,98]:

    familia          mercado representativo     erro maximo
    Over/Under       Over 2.5                     8,14 pp
    BTTS             BTTS                         8,14 pp
    Corners          Escanteios Over 9.5         15,47 pp
    Cards            Cartoes Over 3.5            15,47 pp
    1X2              1X2_home                    15,47 pp
    Double Chance    Double Chance 1X            15,47 pp

Os 2pp da trava NAO sao atingidos, e o residuo nao e do metodo de ajuste: a
melhor curva de dois parametros POSSIVEL (busca em grade minimizando o erro
maximo em espaco de probabilidade) ainda erra 6,03pp no ramo de meia-banda e
9,45pp no de banda inteira. A causa e a forma: o legado satura (p=0,98 sai
em 0,8575 / 0,7350 por causa da banda de 25%) enquanto qualquer logistica
com b>0 continua subindo ate 1. O ganho da correcao e reduzir o erro de
referencia de 24,50pp (identidade) para <=15,47pp, nao zera-lo.
"""
import logging
from typing import Dict, Tuple

from backend.modeling.calibragem.curva import _logit, aplicar
from backend.modeling.calibragem.legado import calibrar_legado

logger = logging.getLogger("sportsbankzu.calibragem.linha_base")

# Mercado usado para amostrar a curva legada de cada familia.
#
# Escolha, e a razao dela: dentro de `calibrar_legado` o RAMO — e portanto a
# forma da curva — depende so de tres testes sobre o rotulo:
#   1. `market.upper() == "BTTS"`            -> meia banda (#152)
#   2. `market.lower().startswith(("over ", "under "))` -> meia banda (#165-e)
#   3. qualquer outro                        -> banda inteira (#105)
# Nenhum deles olha a LINHA (2.5, 9.5, ...), entao trocar "Over 2.5" por
# "Over 3.5" nao muda um digito. A escolha dentro da familia so importa em um
# caso: "Under 2.5" carrega o extra do #113, que hoje e caminho morto
# (`_DEFAULT_OU_DEFLATION` = 0,90 < 1,0, medido em 0 de 13.524 casos da
# fixture dourada) mas voltaria a viver se a constante mudasse. Por isso o
# representativo de Over/Under e "Over 2.5", nao "Under 2.5": a linha de base
# nao pode depender de um ramo que a producao nao exercita.
#
# Os rotulos abaixo sao os que o SERVING de fato usa (ver a guarda por AST em
# tests/calibragem/test_12_guardas.py), nao formas inventadas.
MERCADO_REPRESENTATIVO: Dict[str, str] = {
    "Over/Under": "Over 2.5",
    "BTTS": "BTTS",
    "Corners": "Escanteios Over 9.5",
    "Cards": "Cartoes Over 3.5",
    "1X2": "1X2_home",
    "Double Chance": "Double Chance 1X",
}

# Mesma faixa da trava (`curva.distancia_maxima`): o ajuste tem de ser bom
# onde a trava mede. Passo de 0,01 -> 97 pontos; com 0,001 o (a0,b0) muda na
# 4a casa e o erro maximo na 3a, ou seja, o custo de 10x mais chamadas a
# `calibrar_legado` nao compra nada.
_P_MIN, _P_MAX, _PASSO = 0.02, 0.98, 0.01

_CACHE: Dict[Tuple[str, str, str], Tuple[float, float]] = {}


def limpar_cache() -> None:
    _CACHE.clear()


def _grade():
    ps, p = [], _P_MIN
    while p <= _P_MAX + 1e-12:
        ps.append(round(p, 6))
        p += _PASSO
    return ps


def _mercado(familia: str) -> str:
    mercado = MERCADO_REPRESENTATIVO.get(familia)
    if not mercado:
        raise ValueError(
            f"familia '{familia}' sem mercado representativo em "
            "MERCADO_REPRESENTATIVO — sem ele nao ha como medir a linha de "
            "base da versao 0 desta familia")
    return mercado


def _curva_legada(familia: str, liga: str, regime: str):
    """Os pares (p, legado(p)) na grade. Sem banco: `_get_league_deflation`
    so alimenta o campo `ou_defl` do detalhe, que nao entra em `final`."""
    mercado = _mercado(familia)
    return [(p, calibrar_legado(p, mercado, liga, regime).final)
            for p in _grade()]


def ajustar_ao_legado(familia: str, liga: str = "",
                      regime: str = "NORMAL") -> Tuple[float, float]:
    """(a0, b0) que aproximam a curva legada por minimos quadrados no logit.

    `logit(legado(p))` contra `logit(p)`, com intercepto. Regressao linear
    simples de uma variavel: a solucao e fechada (Sxy/Sxx e a media), entao
    nao ha iteracao, nao ha tolerancia e nao ha dependencia externa — a mesma
    razao pela qual o `estimador` escreve a inversa 2x2 a mao.
    """
    pares = _curva_legada(familia, liga, regime)
    xs = [_logit(p) for p, _ in pares]
    ys = [_logit(q) for _, q in pares]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        raise ValueError("grade degenerada: variancia zero em logit(p)")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    return (a, b)


def erro_maximo(familia: str, a: float, b: float, liga: str = "",
                regime: str = "NORMAL") -> float:
    """max |curva(p; a,b) - legado(p)| em pontos de PROBABILIDADE (0-1).

    A mesma unidade da trava. Publicado na docstring do modulo por familia;
    esta funcao existe para o teste e para quem quiser remedir depois de
    qualquer mexida no legado.
    """
    return max(abs(aplicar(p, a, b) - q)
               for p, q in _curva_legada(familia, liga, regime))


def linha_base(familia: str, liga: str = "",
               regime: str = "NORMAL") -> Tuple[float, float]:
    """`ajustar_ao_legado` com cache por (familia, liga, regime).

    O ciclo pede a linha de base de toda celula sem versao gravada, e cada
    ajuste custa 97 chamadas a `calibrar_legado` (que abre o pickle do
    isotonico). Sem cache seriam ~3 mil aberturas de arquivo por ciclo.
    """
    chave = (familia, liga or "", regime)
    if chave not in _CACHE:
        a, b = ajustar_ao_legado(familia, liga or "", regime)
        _CACHE[chave] = (a, b)
        logger.info(
            "[calibragem] linha de base da versao 0 para (%s, %s): "
            "a0=%.6f b0=%.6f (erro maximo %.2fpp — ver docstring de "
            "linha_base.py: dois parametros nao reproduzem a pilha de bandas)",
            familia, liga or "-", a, b,
            erro_maximo(familia, a, b, liga or "", regime) * 100,
        )
    return _CACHE[chave]
