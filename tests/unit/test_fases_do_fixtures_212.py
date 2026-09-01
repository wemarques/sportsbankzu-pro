# -*- coding: utf-8 -*-
"""#212 - onde o tempo do /fixtures realmente esta.

A instrumentacao do #207 respondeu a pergunta que eu tinha feito, e a resposta
derrubou a minha hipotese. Eu previa ~6000ms por chamada de /lastx sob os 3
workers do #115. Medido em producao em 01/09/2026, championship com 8 jogos:

    media por chamada .... 234-378ms   (eu previa ~6000ms)
    soma das 16 chamadas . 3,7 a 6,1s  ->  10 a 17% do pedido
    com cache quente ..... 0,3s (media 20ms)

Decompondo os REPORT do CloudWatch pelo marco 'parallelizing':

    pedido       total    antes do split   no laco   lastx   laco sem lastx
    3a2445e9     62,7s          44,7s       18,0s     6,1s        11,9s
    4f338c6d     41,1s          24,6s       16,5s     4,0s        12,5s
    c78d5b3b     34,8s          19,7s       15,1s     0,3s        14,8s

Ou seja: o tempo esta ANTES do laco (busca da liga) e DENTRO do laco em coisa
que nao e /lastx (calculo do modelo). Estas linhas separam as duas metades para
nao chutarmos uma terceira vez.
"""
import inspect

import backend.routes.fixtures as fx


def test_as_fases_estao_instrumentadas():
    src = inspect.getsource(fx._process_single_league)
    for marco in ("_t_liga", "_ms_season", "_ms_matches", "_ms_aux", "_t_laco"):
        assert marco in src, f"falta o marco {marco}"


def test_emite_as_duas_linhas_de_fase():
    src = inspect.getsource(fx._process_single_league)
    assert "ate_o_laco=" in src, "falta a linha da fase de busca da liga"
    assert "laco_de_montagem=" in src, "falta a linha da fase de montagem"


def test_os_marcos_estao_na_ordem_certa():
    """_t_liga abre tudo; _t_laco so comeca depois das buscas de liga."""
    src = inspect.getsource(fx._process_single_league)
    assert src.index("_t_liga") < src.index("_ms_season") < src.index("_t_laco")
    assert src.index("_ms_aux = ") < src.index("_t_laco")


def test_usa_relogio_monotonico():
    """time.time() anda para tras com ajuste de NTP; medicao de fase, nao."""
    src = inspect.getsource(fx._process_single_league)
    assert "time.monotonic()" in src
    assert "time.time()" not in src.split("#212")[0][-400:]


def test_medicao_nao_altera_o_retorno(monkeypatch):
    """Instrumentacao nao pode mudar comportamento."""
    r = fx.fixtures(leagues="", date="today")
    assert r["matches"] == []
