# -*- coding: utf-8 -*-
"""#252 - o gate #230 so conta geracao publicada ANTES do kickoff.

O ledger e append-only e o cron regrava o jogo depois do apito. `kickoff_utc`
esta nula em todas as linhas, entao "descarta se published_at >= kickoff_utc"
deixava tudo passar. O kickoff sai do sufixo epoch do match_id; sem kickoff
nenhum, a linha SAI (falha fechada) e e contada.
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
# Caso real medido em 2026-09-14: kickoff 13/09 11:30 UTC, regravado 14/09 05:00.
_HEIDENHEIM = "2-bundesliga-Heidenheim-Holstein Kiel-1789299000.0"


def _ln(match_id, publicado, kickoff=None):
    return {"match_id": match_id, "published_at": publicado, "kickoff_utc": kickoff}


def test_kickoff_sai_do_sufixo_epoch_do_match_id():
    assert C._kickoff_da_linha(_HEIDENHEIM, None) == datetime(2026, 9, 13, 11, 30, tzinfo=_UTC)


def test_kickoff_utc_gravado_tem_precedencia_sobre_o_sufixo():
    gravado = datetime(2026, 9, 13, 12, 0, tzinfo=_UTC)
    assert C._kickoff_da_linha(_HEIDENHEIM, gravado) == gravado


def test_match_id_sem_epoch_nao_inventa_kickoff():
    assert C._kickoff_da_linha("premier-league-todays-12345", None) is None
    assert C._kickoff_da_linha("liga-casa-fora-abc", None) is None
    assert C._kickoff_da_linha("", None) is None


def test_regravacao_pos_apito_sai_e_pre_apito_fica():
    linhas = [
        _ln(_HEIDENHEIM, datetime(2026, 9, 14, 5, 0, tzinfo=_UTC)),     # pos-apito
        _ln(_HEIDENHEIM, datetime(2026, 9, 13, 5, 0, tzinfo=_UTC)),     # pre-apito
        _ln(_HEIDENHEIM, datetime(2026, 9, 13, 11, 30, tzinfo=_UTC)),   # NO apito: sai
    ]
    mantidas, cont = C._so_pre_jogo(linhas)
    assert [l["published_at"].day for l in mantidas] == [13]
    assert cont["pos_kickoff"] == 2 and cont["sem_kickoff"] == 0


def test_kickoff_desconhecido_exclui_falha_fechada():
    linhas = [_ln("premier-league-todays-12345", datetime(2026, 9, 13, 5, 0, tzinfo=_UTC))]
    mantidas, cont = C._so_pre_jogo(linhas)
    assert mantidas == []
    assert cont["sem_kickoff"] == 1 and cont["jogos_sem_kickoff"] == 1


def test_jogo_so_com_geracao_pos_apito_nao_conta_como_jogo():
    linhas = [_ln(_HEIDENHEIM, datetime(2026, 9, 14, 5, 0, tzinfo=_UTC)),
              _ln(_HEIDENHEIM, datetime(2026, 9, 14, 23, 0, tzinfo=_UTC))]
    mantidas, cont = C._so_pre_jogo(linhas)
    assert mantidas == [] and cont["jogos_pos_kickoff"] == 1


def test_do_ledger_aplica_o_filtro_e_nao_ha_opcao_para_desligar():
    src = (_RAIZ / "scripts" / "comparar_com_mercado.py").read_text(encoding="utf-8")
    corpo = src[src.index("def _do_ledger("):src.index("_COBERTURA_LEDGER: List")]
    assert "l.published_at, l.kickoff_utc" in corpo
    assert "_so_pre_jogo(" in corpo
    assert "pos-kickoff" not in src.split("def main(")[1]      # nenhuma flag de escape
