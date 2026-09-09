# -*- coding: utf-8 -*-
"""Camada de calibragem aprendida.

Substitui a deflacao fixa por uma correcao de dois parametros por familia que
se ajusta a cada lote de jogos liquidados. Spec:
docs/superpowers/specs/2026-09-09-camada-calibragem-aprendida-design.md
"""

# Piso de decisao. Reusa a constante do #079 (`MIN_N_BRIER = 20`): abaixo
# disso o repositorio ja trata amostra como diagnostica, nunca decisoria.
MIN_N_JOGOS = 20

# Trava: mudanca maxima de probabilidade que um pick pode sofrer num ciclo.
PASSO_MAXIMO_PP = 0.02

# `k` do encolhimento quando ha celulas de menos para estima-lo dos dados.
# O dobro do piso: uma celula precisa do dobro do minimo para valer tanto
# quanto o pai.
K_FIXO = 40
MIN_CELULAS_PARA_ESTIMAR_K = 5

# Semente do backfill.
TETO_N_PRIOR = 150
N_PRIOR_NAO_VALIDADA = 75
MIN_PICKS_PARA_VALIDAR_SEMENTE = 30
TOLERANCIA_CONCORDANCIA = 0.02

VERSAO_LEGADO = 0
