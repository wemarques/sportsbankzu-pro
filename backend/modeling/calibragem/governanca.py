# -*- coding: utf-8 -*-
"""Politica: quem PODE mudar, e quanto. Sem ajuste e sem I/O.

A trava e expressa em pontos de PROBABILIDADE, nao em `a` e `b`. Limitar os
parametros separadamente e dificil de raciocinar: o mesmo delta em `a` move
pouco no meio da escala e muito nas pontas.

#253 - dois limites por celula, contra a ANCORA:
  * trava por ciclo: `distancia(vigente, final) <= PASSO_MAXIMO_PP`;
  * teto acumulado: `distancia(ancora, final) <= TETO_DERIVA_PP`.
#253-a - o julgamento (reverter/ancorar/congelar) e POR FAMILIA, somando as
ligas: por liga, nenhuma das 20 juntava 20 jogos em 10 ciclos.
"""
import logging
from typing import Dict, Optional, Sequence, Tuple

from backend.modeling.calibragem import (
    MIN_N_JOGOS, PASSO_MAXIMO_PP, TETO_DERIVA_PP,
)
from backend.modeling.calibragem.curva import (
    aplicar, celula_que_serve, distancia_maxima, entrada_da_curva,
)

logger = logging.getLogger("sportsbankzu.calibragem.governanca")

_ITER_BUSCA = 40

# Movimento abaixo disto nao vira versao nova (#253). A grade de
# `distancia_maxima` tem passo 0,001 em p; perto do teto a busca acha passos
# de milionesimos de ponto, e cada um criaria uma versao — girando `criada_em`
# a cada ciclo, que e a forma do defeito que o teto existe para fechar.
_MOVIMENTO_MINIMO = 0.001

_LEGADO = (0.0, 1.0)


def curva_servida(vigencia: Sequence[tuple], instante) -> Tuple[float, float]:
    """O `(a, b)` que estava vigente numa celula quando o pick foi publicado.

    `vigencia` e a lista `(criada_em, a, b)` das copias `vigente`/`substituida`
    da celula, em ordem de gravacao. Vale a ultima com `criada_em < instante`
    (estrito: publicado no instante da troca nao foi servido por ela). Antes
    da primeira, a versao 0, `(0, 1)`.
    """
    a, b = _LEGADO
    if instante is None:
        return a, b
    for criada_em, a_v, b_v in vigencia:
        try:
            if criada_em < instante:
                a, b = float(a_v), float(b_v)
            else:
                break
        except TypeError:
            break
    return a, b


def _vigorava(vigencia: Sequence[tuple], instante) -> bool:
    if instante is None:
        return False
    for criada_em, _a, _b in vigencia:
        try:
            if criada_em < instante:
                return True
        except TypeError:
            return False
        break
    return False


def curva_servida_do_pick(vigencia: Dict[tuple, Sequence[tuple]], pick) -> Tuple[float, float]:
    """A curva que SERVIU o pick, na ordem do serving (#253-a, #253-b).

    A ordem e `curva.celula_que_serve` — a mesma de `curva.aplicar_versao`:
    a celula da liga quando ela tem vigente, senao a celula-familia. Aqui ela
    e aplicada ao INSTANTE da publicacao: so disputam as celulas que ja
    vigoravam naquele momento; nenhuma -> o legado.
    """
    familia, liga, instante = pick.familia, pick.liga, pick.publicado_em
    # So disputam a ordem do serving as celulas que ja vigoravam no instante.
    vigoravam = {c: vigencia[c] for c in ((familia, liga), (familia, ""))
                 if c in vigencia and _vigorava(vigencia[c], instante)}
    celula = celula_que_serve(vigoravam, familia, liga)
    return curva_servida(vigoravam[celula], instante) if celula else _LEGADO


def ancora_do_pick(ancoras: Dict[tuple, dict], familia: str, liga: str) -> Tuple[float, float]:
    """A ancora da celula que responde pelo pick: a da liga, senao a da
    familia, senao o legado."""
    celula = celula_que_serve(ancoras, familia, liga)
    anc = ancoras.get(celula) if celula else None
    if not anc:
        return _LEGADO
    return float(anc["a"]), float(anc["b"])


def avaliar_proposta(proposta: dict, vigente: dict, n_jogos: int,
                     limite: Optional[float] = None,
                     ancora: Optional[dict] = None,
                     teto: Optional[float] = None) -> dict:
    """Decide o que de fato passa a valer. Nunca levanta.

    Com `ancora`, o resultado respeita tambem o teto de deriva acumulada
    (#253). Sem `ancora`, so a trava por ciclo — o comportamento do #248,
    mantido para o controle dos testes.
    """
    limite = PASSO_MAXIMO_PP if limite is None else limite
    teto = TETO_DERIVA_PP if teto is None else teto
    a_v, b_v = float(vigente["a"]), float(vigente["b"])
    a_p, b_p = float(proposta["a"]), float(proposta["b"])

    def _mantem(status: str, motivo: str) -> dict:
        return {"a": a_v, "b": b_v, "status": status,
                "fator_encurtamento": None, "motivo": motivo}

    if n_jogos < MIN_N_JOGOS:
        return _mantem("abaixo_do_piso",
                       f"n_jogos={n_jogos} < {MIN_N_JOGOS} (#079)")

    if b_p <= 0:
        # b <= 0 inverteria a ordem das probabilidades, e a regra do corredor
        # (#246-a) decide por ordem — a correcao mudaria o corredor por efeito
        # colateral, sem ninguem decidir.
        return _mantem("rejeitada", f"b={b_p:.4f} nao positivo; ordem inverteria")

    if (a_p, b_p) == (a_v, b_v):
        return _mantem("inalterada", "proposta identica a vigente")

    def _cabe(a_c: float, b_c: float) -> bool:
        if distancia_maxima(a_v, b_v, a_c, b_c) > limite:
            return False
        if ancora is None:
            return True
        return distancia_maxima(float(ancora["a"]), float(ancora["b"]),
                                a_c, b_c) <= teto

    if _cabe(a_p, b_p):
        return {"a": a_p, "b": b_p, "status": "adotada",
                "fator_encurtamento": None, "motivo": ""}

    # Encurta ao longo do segmento vigente->proposta. A distancia a VIGENTE
    # cresce de forma monotona com t; a distancia a ANCORA nao precisa. A
    # bisseccao guarda sempre um ponto viavel (`baixo`, que comeca em t=0 — a
    # vigente ja respeita o teto), entao o resultado respeita os dois limites
    # mesmo quando nao e o maior t possivel: erro so para o lado conservador.
    baixo, alto = 0.0, 1.0
    for _ in range(_ITER_BUSCA):
        meio = (baixo + alto) / 2.0
        if _cabe(a_v + meio * (a_p - a_v), b_v + meio * (b_p - b_v)):
            baixo = meio
        else:
            alto = meio
    a_f = a_v + baixo * (a_p - a_v)
    b_f = b_v + baixo * (b_p - b_v)

    no_teto = ancora is not None and distancia_maxima(
        float(ancora["a"]), float(ancora["b"]), a_f, b_f) >= teto - _MOVIMENTO_MINIMO
    if distancia_maxima(a_v, b_v, a_f, b_f) < _MOVIMENTO_MINIMO:
        return _mantem("inalterada",
                       f"teto de deriva de {teto:.4f} atingido contra a ancora"
                       if no_teto else "movimento abaixo do minimo")
    motivo = f"passo limitado a {limite:.4f} de probabilidade"
    if no_teto:
        motivo += f"; teto de deriva de {teto:.4f} contra a ancora"
    return {"a": a_f, "b": b_f, "status": "encurtada",
            "fator_encurtamento": baixo, "motivo": motivo}


def brier(pares: Sequence[Tuple[float, int]]):
    """Media de (p - y)^2. None se vazio."""
    if not pares:
        return None
    return sum((p - y) ** 2 for p, y in pares) / len(pares)


def julgar_familia(janela: Sequence, vigencia: Dict[tuple, Sequence[tuple]],
                   ancoras: Dict[tuple, dict], vigentes: Dict[tuple, dict],
                   reversoes_seguidas: int) -> dict:
    """Um veredito para a FAMILIA inteira (#253-a).

    `janela`: picks da familia, de todas as ligas, publicados depois do
    `desde` da ancora da familia. Cada um e pontuado pela curva que o serviu
    (`curva_servida_do_pick`, ajustada antes de o desfecho dele existir: fora
    da amostra por construcao) e pela ancora da sua celula (`ancora_do_pick`).
    `vigentes`: as celulas vigentes da familia, para saber se alguma ja saiu
    da ancora.

    Reverte pelo PONTO, sem esperar o IC excluir zero: reversao falsa volta
    para curvas ja validadas e custa quase nada; reversao que nao acontece
    deixa curvas ruins publicando mais um ciclo. `ancorar` exige so nao
    perder: a ancora nova continua sob o teto e sob a proxima janela.
    """
    n_jogos = len({p.match_id for p in janela})
    if n_jogos < MIN_N_JOGOS:
        return {"acao": "manter",
                "motivo": f"janela da familia com {n_jogos} jogos < {MIN_N_JOGOS}",
                "limite_proximo": PASSO_MAXIMO_PP, "n_jogos": n_jogos}

    # A probabilidade PUBLICADA e a composta: `aplicar(legado(raw), a, b)`
    # (#248, C1). Medir o Brier sobre `p_raw` compararia curvas que nenhuma
    # versao serviu.
    b_serv = brier([(aplicar(entrada_da_curva(p), *curva_servida_do_pick(vigencia, p)), p.y)
                    for p in janela])
    b_anc = brier([(aplicar(entrada_da_curva(p), *ancora_do_pick(ancoras, p.familia, p.liga)), p.y)
                   for p in janela])
    placar = f"brier servido {b_serv:.5f} x ancora {b_anc:.5f} em {n_jogos} jogos"

    if b_serv > b_anc:
        if reversoes_seguidas >= 1:
            logger.error(
                "[calibragem] familia CONGELADA apos 2 reversoes seguidas sem "
                "validacao no meio: %s", placar)
            return {"acao": "congelar",
                    "motivo": f"duas reversoes seguidas; enviado para revisao humana; {placar}",
                    "limite_proximo": 0.0, "n_jogos": n_jogos}
        return {"acao": "reverter", "motivo": placar,
                "limite_proximo": PASSO_MAXIMO_PP / 2, "n_jogos": n_jogos}

    fora_da_ancora = any(
        (float(v["a"]), float(v["b"])) != ancora_do_pick(ancoras, cel[0], cel[1])
        for cel, v in vigentes.items())
    if fora_da_ancora:
        return {"acao": "ancorar", "motivo": placar,
                "limite_proximo": PASSO_MAXIMO_PP, "n_jogos": n_jogos}
    return {"acao": "manter",
            "motivo": f"todas as celulas ja estao na ancora; {placar}",
            "limite_proximo": PASSO_MAXIMO_PP, "n_jogos": n_jogos}
