# -*- coding: utf-8 -*-
"""#253-b - limiares e volume contados com a curva que o SERVING usaria.

O defeito medido (ensaio de 2026-09-15): 9 de 20 ligas tinham celula vigente
propria em `(0, 1)`. O ciclo movia so a celula-familia, a re-derivacao
aplicava essa curva nova a TODO pick da familia e calculava limiares que
preservavam 402 picks. No serving, as 9 ligas continuavam na curva legada com
o limiar novo: 365 picks.
"""
from datetime import datetime, timezone

from backend.modeling.calibragem import ciclo, curva, governanca
from backend.modeling.calibragem.limiares import contar_por_classe, rederivar
from backend.modeling.calibragem.repositorio import Pick

F = "Over/Under"
ATUAIS = {F: {"safe_ev": 0.06, "neutro_ev": 0.00, "safe_edge": 0.05, "neutro_edge": 0.02}}
LEGADO = {"a": 0.0, "b": 1.0}
SOBE = {"a": 0.45, "b": 1.0}
T = datetime(2026, 9, 10, tzinfo=timezone.utc)


def _picks(liga, n, deslocamento=0):
    # p_legado distinta por pick (0,450..0,649), odd 2.05: parte publica com a
    # curva legada, mais picks publicam quando a curva sobe. Valores repetidos
    # criariam blocos de EMPATES exatos no corte, e `>=` leva o bloco inteiro
    # (ver `limiares._arredondar_para_baixo`) — o teste mediria empate, nao a
    # ordem do serving.
    return [Pick(f"{liga}-{i}", F, liga, 0.45 + ((i * 37) % 200) / 1000.0, 1, 2.05,
                 "", T, 0.45 + ((i * 37) % 200) / 1000.0)
            for i in range(deslocamento, deslocamento + n)]


def _total(contagem):
    return sum(d["safe"] + d["neutro"] for d in contagem.values())


def test_celula_que_serve_e_liga_senao_familia_senao_nada():
    mapa = {(F, "mls"): 1, (F, ""): 2}
    assert curva.celula_que_serve(mapa, F, "mls") == (F, "mls")
    assert curva.celula_que_serve(mapa, F, "la-liga") == (F, "")
    assert curva.celula_que_serve({(F, "mls"): 1}, F, "la-liga") is None
    assert curva.celula_que_serve(mapa, F, "") == (F, "")


def test_aplicar_versao_usa_a_mesma_ordem():
    """Liga com vigente propria em (0,1) nao recebe a curva da familia."""
    parametros = {(F, "mls"): (13, 0.0, 1.0), (F, ""): (14, 0.45, 1.0)}
    mls = curva.aplicar_versao(0.6, "Over 2.5", "mls", "NORMAL", parametros)
    outra = curva.aplicar_versao(0.6, "Over 2.5", "la-liga", "NORMAL", parametros)
    assert mls.tipo_banda == "curva-v13" and outra.tipo_banda == "curva-v14"
    assert outra.final > mls.final


def test_contagem_pontua_cada_pick_pela_celula_que_o_serve():
    picks = _picks("mls", 60) + _picks("la-liga", 60)
    so_familia = {(F, ""): SOBE}
    liga_no_legado = {(F, "mls"): LEGADO, (F, ""): SOBE}
    todos_legado = {(F, ""): LEGADO}
    n_familia = _total(contar_por_classe(picks, so_familia, ATUAIS))
    n_misto = _total(contar_por_classe(picks, liga_no_legado, ATUAIS))
    n_legado = _total(contar_por_classe(picks, todos_legado, ATUAIS))
    assert n_legado < n_misto < n_familia


def test_rederivar_preserva_o_volume_que_o_serving_publicaria():
    """O caso medido em producao, reduzido: a liga `mls` tem vigente propria em
    (0,1), a familia sobe. O volume depois do ciclo, contado NA ORDEM DO
    SERVING, tem de ficar igual ao de antes (folga de empates de +-2)."""
    picks = _picks("mls", 200) + _picks("la-liga", 200, deslocamento=7)
    antes = {(F, "mls"): LEGADO, (F, ""): LEGADO}
    depois = {(F, "mls"): LEGADO, (F, ""): SOBE}
    novos, motivos = rederivar(picks, antes, depois, ATUAIS)
    assert "re-derivados" in motivos[F], motivos[F]
    volume_antes = _total(contar_por_classe(picks, antes, ATUAIS))
    volume_depois = _total(contar_por_classe(picks, depois, novos))
    assert abs(volume_depois - volume_antes) <= 2, (volume_antes, volume_depois)


def test_planejar_entrega_mapas_por_celula_com_familia_sempre_presente():
    picks = _picks("mls", 30)
    ajuste = {(F, ""): {"a": 0.45, "b": 1.0, "n_jogos": 30, "origem": "familia", "k_fixo": False},
              (F, "mls"): {"a": 0.45, "b": 1.0, "n_jogos": 5, "origem": "familia", "k_fixo": False}}
    vigentes = {(F, "mls"): {"versao": 13, "a": 0.0, "b": 1.0, "criada_em": T}}
    plano = ciclo.planejar(picks, ajuste, vigentes, historico=[])
    assert plano["parametros_antigos"] == {(F, "mls"): LEGADO, (F, ""): LEGADO}
    novos = plano["parametros_novos"]
    assert novos[(F, "mls")] == LEGADO                     # abaixo do piso: nao promove
    assert novos[(F, "")]["a"] > 0.0                        # familia encurtada: promove


def test_ancora_do_pick_usa_a_mesma_ordem():
    ancoras = {(F, "mls"): {"a": 0.2, "b": 1.0}, (F, ""): {"a": 0.1, "b": 1.0}}
    assert governanca.ancora_do_pick(ancoras, F, "mls") == (0.2, 1.0)
    assert governanca.ancora_do_pick(ancoras, F, "la-liga") == (0.1, 1.0)
