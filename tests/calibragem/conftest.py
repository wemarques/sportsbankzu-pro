# -*- coding: utf-8 -*-
"""Isolamento comum dos testes da camada de calibragem.

Dois problemas, os dois ja pagos em defeitos neste repositorio:

1. **Cache global entre testes.** O cache TTL por liga do #231-a e o cache de
   parametros do ciclo sobrevivem ao fim do teste. O #242 nasceu disso, e o
   controle positivo da fixture dourada quebrou de novo pelo mesmo motivo na
   Task 12 (passava isolado, falhava na suite). A fixture que consertava isso
   estava duplicada em `test_233_classificacao_valor.py` e `test_01`; aqui
   ela e uma so, `autouse`, antes E depois de cada teste.

2. **A suite escrevia DDL na RDS de producao.** `test_11` chamava
   `ciclo.executar()` sem dublê de `_conn`, entao `garantir_tabela()` rodava
   de verdade — foi assim que a tabela `calibragem_versoes` nasceu la. Cada
   teste que precisa de banco monta o proprio dublê; nenhum tem por que
   abrir socket. A guarda e no `psycopg2.connect`, e nao em
   `repositorio._conn`, porque assim ela nao atrapalha os testes que
   substituem `_conn` (a substituicao deles vem depois e vence) nem o que
   exercita o proprio `_conn`.
"""
import pytest


@pytest.fixture(autouse=True)
def _cache_limpo():
    """Cache do ciclo e das correcoes por liga zerados nas duas pontas.

    `get_lambda_corrections` tambem sai do caminho: devolve `{}`, que faz
    `_get_league_deflation` cair nos padroes documentados — as condicoes em
    que a fixture dourada foi capturada. Sem isso, um teste anterior que
    aqueca o cache com a RDS real muda o resultado por ORDEM DE EXECUCAO.

    A fixture YIELDA a funcao ORIGINAL. Quem precisa da funcao de verdade
    (com o cache por liga do #231-a dentro dela) pede `_cache_limpo` pelo
    nome e a recoloca -- e o caso do teste que conta consultas por liga em
    `test_03`: substituir `get_lambda_corrections` inteira mede o numero
    errado, porque o cache mora DENTRO dela.
    """
    from backend.modeling import lambda_calculator as LC
    from backend.modeling.calibragem import ciclo

    original = LC.get_lambda_corrections
    LC.get_lambda_corrections = lambda league: {}
    LC.limpar_cache_correcoes()
    ciclo.limpar_cache()
    try:
        yield original
    finally:
        LC.get_lambda_corrections = original
        LC.limpar_cache_correcoes()
        ciclo.limpar_cache()


@pytest.fixture(autouse=True)
def _sem_banco_de_verdade(monkeypatch):
    """Nenhum teste deste diretorio abre conexao com a RDS.

    Quem precisa de banco substitui `repositorio._conn` por um dublê; quem
    esquecer bate nesta guarda com a mensagem certa, em vez de emitir DDL
    contra producao em silencio.
    """
    import psycopg2

    def _proibido(*a, **k):
        raise AssertionError(
            "teste de tests/calibragem/ tentou abrir conexao real com o "
            "banco. Substitua `repositorio._conn` por um dublê (ver "
            "test_09_auditoria.py) — a suite nao fala com a RDS.")

    monkeypatch.setattr(psycopg2, "connect", _proibido)
