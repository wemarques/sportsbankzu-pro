# -*- coding: utf-8 -*-
"""#252-a - o gate #230 exclui a janela em que `calibrated_prob` era a camada.

Entre a primeira versao nao-identidade da camada #248 (2026-09-10 23:02:06)
e o deploy do #251 (2026-09-14 04:50:22) a coluna carregou a saida da camada.
So `calibrated_prob` e cortada; as outras colunas nao foram afetadas.
"""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "comparar_com_mercado", _RAIZ / "scripts" / "comparar_com_mercado.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

_UTC = timezone.utc


def _ln(jogo, publicado):
    return {"match_id": jogo, "published_at": publicado}


def test_limites_sao_os_medidos():
    assert C._JANELA_CONTAMINADA_251 == (
        datetime(2026, 9, 10, 23, 2, 6, tzinfo=_UTC),
        datetime(2026, 9, 14, 4, 50, 22, tzinfo=_UTC),
    )


def test_inicio_inclusivo_fim_exclusivo():
    ini, fim = C._JANELA_CONTAMINADA_251
    linhas = [
        _ln("a", datetime(2026, 9, 10, 23, 2, 5, tzinfo=_UTC)),   # antes: fica
        _ln("b", ini),                                            # no inicio: sai
        _ln("c", datetime(2026, 9, 12, 12, 0, tzinfo=_UTC)),      # dentro: sai
        _ln("d", fim),                                            # no fim: fica
    ]
    mantidas, cont = C._fora_da_janela_contaminada(linhas, "calibrated_prob")
    assert [l["match_id"] for l in mantidas] == ["a", "d"]
    assert cont == {"contaminados": 2, "jogos_contaminados": 2}


def test_jogo_com_geracao_limpa_nao_conta_como_sumido():
    linhas = [_ln("a", datetime(2026, 9, 10, 20, 0, tzinfo=_UTC)),
              _ln("a", datetime(2026, 9, 11, 3, 0, tzinfo=_UTC))]
    mantidas, cont = C._fora_da_janela_contaminada(linhas, "calibrated_prob")
    assert len(mantidas) == 1
    assert cont == {"contaminados": 1, "jogos_contaminados": 0}


def test_outras_colunas_nao_sao_cortadas():
    linhas = [_ln("c", datetime(2026, 9, 12, 12, 0, tzinfo=_UTC))]
    for campo in ("raw_prob", "iso_prob", "published_prob"):
        mantidas, cont = C._fora_da_janela_contaminada(linhas, campo)
        assert mantidas == linhas and cont["contaminados"] == 0, campo


def test_do_ledger_aplica_o_corte_sem_opcao_de_desligar():
    src = (_RAIZ / "scripts" / "comparar_com_mercado.py").read_text(encoding="utf-8")
    corpo = src[src.index("def _do_ledger("):src.index("_COBERTURA_LEDGER: List")]
    assert "_fora_da_janela_contaminada(" in corpo
    main = src.split("def main(")[1]
    assert "contaminad" not in main.split("args = ap.parse_args()")[0]   # nenhuma flag
