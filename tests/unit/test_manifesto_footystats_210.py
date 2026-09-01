# -*- coding: utf-8 -*-
"""#210 - o manifesto e o contrato dos campos da FootyStats.

Medido em 01/09/2026: 230 campos mapeados, 128 sem um unico consumidor. Entre
os orfaos, `home_advantage_attack`, `home_advantage_defence`,
`btts_percentage_home/away` e `xg_for_avg_home/away` - dados que passamos
semanas derivando por outros caminhos enquanto ja estavam mapeados.

Estes testes garantem que isso nao volta a acontecer em silencio.
"""
import backend.config.footystats_manifest as mf


def test_todo_campo_mapeado_esta_declarado():
    """MANDATORIO: nenhum campo pode ficar em estado nao declarado."""
    faltando = sorted(set(mf.campos_mapeados()) - set(mf.CAMPOS))
    assert not faltando, (
        f"{len(faltando)} campo(s) mapeados pelo data_mapper e ausentes do manifesto: "
        f"{faltando[:10]}. Declare cada um como CONSUMIDO, PLANEJADO ou DESCARTADO."
    )


def test_nenhum_consumido_perdeu_o_consumidor():
    """A renomeacao silenciosa - a que apaga um dado sem ninguem ver."""
    consumidos = mf.campos_consumidos()
    orfaos = sorted(c for c, (e, _) in mf.CAMPOS.items()
                    if e == mf.CONSUMIDO and c not in consumidos)
    assert not orfaos, (
        f"{len(orfaos)} campo(s) declarados CONSUMIDO sem nenhum consumidor no backend: "
        f"{orfaos[:10]}."
    )


def test_verificar_nao_bloqueia_no_estado_atual():
    assert mf.verificar()["bloqueia"] == []


def test_estados_sao_validos_e_tem_motivo():
    for campo, (estado, motivo) in mf.CAMPOS.items():
        assert estado in mf.ESTADOS, (campo, estado)
        assert motivo and len(motivo) > 10, f"{campo} precisa de um motivo escrito"


def test_o_manifesto_nao_se_conta_como_consumidor():
    """Sem isso a verificacao vira um espelho: todo campo pareceria consumido."""
    assert "footystats_manifest.py" in mf._IGNORADOS
    assert "data_mapper.py" in mf._IGNORADOS
    assert len(mf.campos_consumidos()) < len(mf.CAMPOS)


def test_as_ancoras_que_procuramos_estao_na_fila_com_motivo():
    """As quatro que a analise de 01/09 provou que faziam falta."""
    fila = dict(mf.fila_de_trabalho())
    for campo in ("home_advantage_attack", "home_advantage_defence",
                  "btts_percentage_home", "btts_percentage_away",
                  "xg_for_avg_home", "xg_for_avg_away"):
        assert campo in fila, f"{campo} sumiu da fila sem virar CONSUMIDO"
        assert len(fila[campo]) > 20, f"{campo} esta na fila sem motivo util"


def test_campo_novo_sem_declaracao_bloqueia(tmp_path):
    mapper = tmp_path / "data_mapper.py"
    mapper.write_text('x = {\n    "campo_novissimo": 1,\n}\n', encoding="utf-8")
    assert "campo_novissimo" in mf.campos_mapeados(str(mapper))


def test_resumo_soma_o_total():
    r = mf.resumo()
    assert r["CONSUMIDO"] + r["PLANEJADO"] + r["DESCARTADO"] == r["TOTAL"] == len(mf.CAMPOS)


def test_a_fila_e_grande_o_bastante_para_ser_levada_a_serio():
    """Guarda contra alguem 'resolver' o problema marcando tudo DESCARTADO."""
    r = mf.resumo()
    assert r["DESCARTADO"] < r["TOTAL"] * 0.30, (
        "mais de 30% dos campos descartados; o manifesto virou um carimbo"
    )
