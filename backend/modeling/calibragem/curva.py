# -*- coding: utf-8 -*-
"""A curva de correcao, COMPOSTA COM O LEGADO (#248, C1):

    p_corrigida = sigmoide(a + b * logit(legado(p_raw)))

`aplicar(x, a, b)` continua sendo `sigmoide(a + b*logit(x))` e mais nada --
matematica pura, sem I/O e sem dependencia externa. O que mudou foi o que se
ALIMENTA a ela: a entrada nao e mais `p_raw`, e a saida do legado. `a` e o
deslocamento sistematico sobre o legado (positivo = o legado publica abaixo
da realidade); `b` e a dispersao (b < 1 = o legado exagera nos extremos).

Por que compor, e nao medir contra: com a composicao, `(a=0, b=1)` E a versao
0 POR CONSTRUCAO -- nao aproximadamente. A trava de 2pp de
`governanca.avaliar_proposta` mede `distancia_maxima(0, 1, a_p, b_p)` e isso
e exatamente a distancia ate a curva publicada na vespera, desde o primeiro
ciclo. Antes, a versao 0 servia o legado e a trava media contra a identidade
(ou contra uma logistica que aproximava o legado com erro de 5,89pp a 9,35pp
-- piso de Chebyshev PROVADO, porque o legado satura em 0,8575 e nenhuma
logistica com b>0 satura). Com a composicao esse erro nao diminui: SOME.

Consequencia registrada: `legado.py` deixa de ser um modulo temporario. Ele
nao morre quando as celulas saem da versao 0 -- passa a ser a camada base
permanente sobre a qual a camada aprendida escreve o residuo.
"""
import logging
import math
from typing import Optional

from backend.modeling.calibragem import VERSAO_LEGADO

logger = logging.getLogger("sportsbankzu.calibragem.curva")

# Prende p antes do logit. 1e-6 mantem logit em ~±13,8, longe de estourar em
# float, e a diferenca em probabilidade e invisivel no card (0,0001%).
_EPS = 1e-6

_FAMILIAS = (
    # Rotulos de exibicao em pt-BR (telas) e as formas reais do
    # `prediction_ledger` (ingles, `market`+`selection` concatenados) tem de
    # coexistir aqui. "corners"/"cards" tem de vir antes de "over "/"under "
    # -- senao "Corners Corners Over 7.5" casa "over " primeiro e vira
    # Over/Under silenciosamente (achado da rodada 1 de correcao).
    ("escanteios", "Corners"),
    ("corners", "Corners"),
    ("cartoes", "Cards"),
    ("cartões", "Cards"),
    ("cards", "Cards"),
    ("btts", "BTTS"),
    # "double chance" e o rotulo que o SERVING usa ("Double Chance 1X/12/X2",
    # em `ev_classification`); "dc "/"dupla chance" sao as formas de tela e do
    # ledger. Sem este token as tres linhas de DC levantavam ValueError dentro
    # de `aplicar_versao`, que engolia a excecao — o estimador aprendia DC
    # (600 picks) e o serving ignorava para sempre.
    ("double chance", "Double Chance"),
    ("dc ", "Double Chance"),
    ("dupla chance", "Double Chance"),
    ("1x2", "1X2"),
    ("over ", "Over/Under"),
    ("under ", "Over/Under"),
)


def _prender(p: float) -> float:
    return min(max(float(p), _EPS), 1.0 - _EPS)


def _logit(p: float) -> float:
    p = _prender(p)
    return math.log(p / (1.0 - p))


def _sigmoide(x: float) -> float:
    # Forma estavel nos dois lados: evita overflow de exp(+x) para x grande.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def aplicar(p: float, a: float, b: float) -> float:
    """logit(p_corrigida) = a + b * logit(p). Monotona crescente se b > 0.

    NAO chama o legado, e nao deve chamar: esta funcao e matematica pura,
    tem 24 chamadores no repositorio, e a fronteira declarada do desenho e
    que `curva.py` nao faz I/O. Quem compoe e `aplicar_versao` (serving) e
    quem alimenta `p_legado` e o `repositorio` (ajuste); os dois entregam a
    ela uma probabilidade que JA passou pelo legado.
    """
    return _sigmoide(a + b * _logit(p))


def base_da_composicao(raw: float, market: str, league_id: str,
                       regime: str) -> float:
    """A ENTRADA da curva: o que a versao 0 publicaria para este pick.

    Unico ponto do pacote, junto com `aplicar_versao`, que chama o legado --
    e o motivo de `legado.py` continuar com um so chamador (`curva.py`), o
    que a guarda `test_1b` de `tests/calibragem/test_12_guardas.py` trava.

    O `repositorio` usa esta funcao para preencher `Pick.p_legado`, que e o
    regressor do estimador. Chamar `calibrar_legado` direto de la
    espalharia a pilha legada por um segundo modulo sem necessidade.
    """
    from backend.modeling.calibragem.legado import calibrar_legado
    return calibrar_legado(raw, market, league_id, regime).final


def entrada_da_curva(pick) -> float:
    """`pick.p_legado`, com erro ALTO quando falta.

    A camada aprende o residuo SOBRE O LEGADO. Cair em `p_raw` quando
    `p_legado` esta ausente reintroduziria, em silencio, exatamente o defeito
    que a composicao resolve (a camada aprendendo sobre uma curva que nunca
    foi publicada). Nao ha alternativa aceitavel: `p_legado` ausente e
    defeito de construcao do `Pick`, e tem de aparecer.

    E a mesma regra da proibicao 15 do CLAUDE.md, do outro lado: o valor
    legitimo pode ser qualquer float em (0, 1) -- inclusive baixo --, entao
    nenhum sentinela numerico serve; so a ausencia e detectavel, e ela e erro.
    """
    p = getattr(pick, "p_legado", None)
    if p is None:
        raise ValueError(
            "Pick sem `p_legado`: a camada de calibragem aprende o residuo "
            "sobre o legado (#248), entao o regressor e a saida do legado, "
            "nao `p_raw`. Quem constroi o Pick tem de preencher `p_legado` "
            "(ver `repositorio.carregar_amostra`).")
    return float(p)


def familia_do_mercado(market: str) -> str:
    """Familia a que o rotulo pertence. Levanta se nao reconhecer.

    Mercado novo tem de quebrar aqui em vez de cair numa familia por acaso —
    calibrar Handicap com a curva de 1X2 seria um erro invisivel.
    """
    m = (market or "").strip().lower()
    for prefixo, familia in _FAMILIAS:
        if prefixo in m:
            return familia
    raise ValueError(f"familia desconhecida para o mercado '{market}'")


def distancia_maxima(a1: float, b1: float, a2: float, b2: float,
                     passo: float = 0.001) -> float:
    """max |curva(p; a1,b1) - curva(p; a2,b2)| para p em [0,02; 0,98].

    Varredura em grade em vez de solucao analitica: a diferenca de duas
    sigmoides pode ter dois maximos locais, e a grade de 0,001 erra no maximo
    alguns milesimos de ponto — folgado para uma trava de 2 pontos.
    """
    pior = 0.0
    p = 0.02
    while p <= 0.98 + 1e-12:
        d = abs(aplicar(p, a1, b1) - aplicar(p, a2, b2))
        if d > pior:
            pior = d
        p += passo
    return pior


def aplicar_versao(raw: float, market: str, league_id: str, regime: str,
                   parametros: Optional[dict] = None):
    """Aplica a versao vigente da celula. Versao 0 delega ao legado.

    `parametros` e o mapa {(familia, liga): (versao, a, b)} lido pelo
    repositorio e passado pelo chamador. Ausente, ou celula ausente dele,
    significa versao 0 — o comportamento de hoje.

    Versao real: COMPOE (#248, C1). A curva e aplicada sobre `detalhe.final`
    (a saida do legado), nao sobre `raw`. Com `(a, b) = (0, 1)` o resultado
    e o proprio `detalhe.final`, a menos do erro de ida-e-volta
    sigmoide(logit(.)) em ponto flutuante (< 1e-9; travado em
    `tests/calibragem/test_13_composicao.py`). E isso que torna a trava de
    2pp exata desde o primeiro ciclo, em vez de medir contra uma curva que
    nunca foi publicada.
    """
    from backend.modeling.calibragem.legado import calibrar_legado

    if not parametros:
        return calibrar_legado(raw, market, league_id, regime)

    try:
        familia = familia_do_mercado(market)
    except ValueError:
        # NAO engolir em silencio: um rotulo do serving que nao resolve
        # familia significa que aquele mercado NUNCA sai da versao 0, por
        # mais que o estimador aprenda para ele. Foi assim que "Double
        # Chance 1X/12/X2" ficou fora da camada sem uma linha no log.
        logger.warning(
            "[calibragem] mercado '%s' (liga=%s) nao resolve familia — "
            "servido pela versao 0 (legado). Se este rotulo e de producao, "
            "falta um token em curva._FAMILIAS.",
            market, league_id or "-",
        )
        return calibrar_legado(raw, market, league_id, regime)

    chave = (familia, league_id or "")
    entrada = parametros.get(chave) or parametros.get((familia, ""))
    if not entrada or entrada[0] == VERSAO_LEGADO:
        return calibrar_legado(raw, market, league_id, regime)

    _versao, a, b = entrada
    detalhe = calibrar_legado(raw, market, league_id, regime)
    # COMPOSICAO: a entrada da curva e a saida do legado, nao `raw`.
    detalhe.final = aplicar(detalhe.final, a, b)
    detalhe.tipo_banda = f"curva-v{_versao}"
    return detalhe
