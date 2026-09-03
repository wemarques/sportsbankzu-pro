# -*- coding: utf-8 -*-
"""#225-c - o fallback que morre em silencio.

`d.get(k, alternativa)` so usa a alternativa quando a chave esta AUSENTE.
Quando ela existe valendo `None` — que e a regra, nao a excecao, num pipeline
onde o produtor monta o dicionario inteiro com todas as chaves — o `get`
devolve `None` e a alternativa nunca e alcancada.

O projeto ja corrigiu isso QUATRO vezes, cada uma sem perceber que era a mesma
coisa:

    #201  `_num()` no lambda ......... chave com None e o default nunca usado
    #208  `_peso_amostra` ............ ausencia != amostra zero
    #217  `season_data_state` ........ "nao sei" != "inicio de temporada"
    #225-b `corners/data_quality` .... cadeia morta zerava a amostra e mandava
                                       o motor inteiro para RESTRICTED

Varredura por AST (`scripts/varredura_get.py`): 1990 ocorrencias de
`.get("k", default)` em `backend/`, 234 delas encadeadas, 230 com o primeiro
nome literal. Cruzando com as 172 chaves que o record SEMPRE cria nos tres
cenarios de referencia do #223, **52 estao confirmadas** — o primeiro nome nunca
esta ausente, entao a alternativa e inalcancavel por construcao. Em 18 delas o
nome ja foi visto valendo `None` num cenario real.

`primeiro_valido` pula `None` em vez de parar nele.
"""
from typing import Any


def primeiro_valido(*valores: Any, padrao: Any = None) -> Any:
    """Primeiro valor que nao e None. `padrao` quando todos forem.

    Diferente de `a or b`: preserva 0, 0.0, "" e False, que sao valores
    legitimos (0 escanteios e um resultado; "" pode ser um rotulo vazio real).
    So `None` significa ausencia.
    """
    for v in valores:
        if v is not None:
            return v
    return padrao


def pegar(d: Any, *chaves: str, padrao: Any = None) -> Any:
    """Primeiro valor nao-nulo entre varias chaves do mesmo dicionario.

    Substitui a cadeia `d.get(a, d.get(b, d.get(c, padrao)))`, que morre no
    primeiro `a` presente-com-None.
    """
    if not isinstance(d, dict):
        return padrao
    for k in chaves:
        v = d.get(k)
        if v is not None:
            return v
    return padrao
