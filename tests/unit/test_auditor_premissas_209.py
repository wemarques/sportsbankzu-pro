# -*- coding: utf-8 -*-
"""#209 - o auditor tem de pegar o que nos pegamos na mao.

Cada caso aqui e um defeito real observado na rodada de 01/09/2026. Se o
auditor deixar de acusar qualquer um deles, ele parou de servir.
"""
import math

import backend.services.auditor_premissas as ap


def jogo(lh=1.45, la=1.25, liga="championship", casa="Casa FC", fora="Fora FC",
         gp=20, mercados=None, **stats):
    s = {"lambdaHome": lh, "lambdaAway": la, "matchesPlayed_overall": gp}
    s.setdefault("over25Prob", ap.p_over25(lh + la) * 100)
    s.setdefault("bttsProb", ap.p_btts(lh, la) * 100)
    s.update(stats)
    return {"leagueId": liga, "homeTeam": {"name": casa}, "awayTeam": {"name": fora},
            "stats": s, "mercados": mercados or []}


def nomes(rel):
    return {v.premissa for v in rel.violacoes}


# ── a matematica de referencia ───────────────────────────────────────

def test_regua_bate_com_o_calculo_manual():
    assert round(ap.lambda_minimo_para(0.75, "over25"), 2) == 3.92
    assert round(ap.lambda_minimo_para(0.75, "btts_simetrico"), 2) == 4.02
    assert round(ap.p_over25(2.70) * 100, 1) == 50.6
    assert round(ap.p_btts(1.45, 1.25) * 100, 1) == 54.6


def test_1x2_soma_cem_e_respeita_o_favorito():
    h, d, a = ap.p_1x2(1.80, 0.90)
    assert abs(h + d + a - 100) < 1e-6
    assert h > a
    assert round(h, 1) == 57.5


# ── rodada limpa ─────────────────────────────────────────────────────

def test_rodada_coerente_nao_acusa_nada():
    rodada = [jogo(lh=1.55, la=1.20, casa=f"C{i}") for i in range(8)]
    rel = ap.auditar(rodada)
    assert rel.violacoes == [], [v.linha() for v in rel.violacoes]
    assert rel.ok
    assert len(rel.premissas_rodadas) == len(ap.PREMISSAS) == 10


# ── os defeitos reais ────────────────────────────────────────────────

def test_pega_over_que_nao_sai_do_lambda():
    rel = ap.auditar([jogo(over25Prob=75.0)])   # lambda 2,70 nao da 75%
    assert "over_bate_com_lambda" in nomes(rel)
    assert not rel.ok, "incoerencia entre probabilidade e lambda e critica"


def test_pega_btts_que_nao_sai_do_lambda():
    rel = ap.auditar([jogo(bttsProb=88.0)])
    assert "btts_bate_com_lambda" in nomes(rel)


def test_pega_a_fusao_inflada_de_amostra_curta():
    """West Ham x Wolverhampton: Poisson 62,5%, fusao 88,8%, 3 rodadas."""
    rel = ap.auditar([jogo(lh=1.18, la=2.35, gp=3, bttsFusionProb=88.8)])
    v = [x for x in rel.violacoes if x.premissa == "fusao_nao_ultrapassa_o_lambda"]
    assert v and v[0].severidade == ap.SEV_ALTO
    assert "3 rodadas" in v[0].detalhe


def test_fusao_com_temporada_cheia_e_menos_grave():
    rel = ap.auditar([jogo(lh=1.17, la=1.17, gp=25, bttsFusionProb=69.6)])
    v = [x for x in rel.violacoes if x.premissa == "fusao_nao_ultrapassa_o_lambda"]
    assert v and v[0].severidade == ap.SEV_MEDIO


def test_pega_safe_sem_lambda_que_sustente():
    m = [{"mercado": "Over 2.5 gols", "classification": "SAFE"}]
    rel = ap.auditar([jogo(lh=1.45, la=1.25, mercados=m)])
    v = [x for x in rel.violacoes if x.premissa == "safe_tem_lambda_que_sustente"]
    assert v and v[0].severidade == ap.SEV_CRITICO
    assert "3.92" in (v[0].esperado or "")


def test_safe_com_lambda_alto_passa():
    m = [{"mercado": "Over 2.5 gols", "classification": "SAFE"}]
    rel = ap.auditar([jogo(lh=2.10, la=2.05, mercados=m)])
    assert "safe_tem_lambda_que_sustente" not in nomes(rel)


def test_pega_lambda_colado_no_grampo():
    rel = ap.auditar([jogo(lh=4.5, la=1.2)])
    assert "lambda_longe_do_grampo" in nomes(rel)


def test_pega_early_season_preso_ligado():
    m = [{"mercado": "Cartoes Under 4.5", "reason_codes": ["EARLY_SEASON_FALLBACK"]}]
    rel = ap.auditar([jogo(gp=24, mercados=m)])
    assert "early_season_desliga" in nomes(rel)


def test_early_season_no_inicio_e_legitimo():
    m = [{"mercado": "Cartoes Under 4.5", "reason_codes": ["EARLY_SEASON_FALLBACK"]}]
    rel = ap.auditar([jogo(gp=3, mercados=m)])
    assert "early_season_desliga" not in nomes(rel)


def test_pega_ev_publicado_sem_odd_de_mercado():
    m = [{"mercado": "Over 1.5 gols", "odds_available": False, "ev": 0.12}]
    rel = ap.auditar([jogo(mercados=m)])
    assert "ev_so_com_odd_real" in nomes(rel)


def test_pega_vantagem_de_mando_invertida():
    """A rodada real: mediana 0,85, com 14 de 17 abaixo de 1."""
    rodada = [jogo(lh=1.18, la=1.45, casa=f"C{i}") for i in range(10)]
    rel = ap.auditar(rodada)
    v = [x for x in rel.violacoes if x.premissa == "vantagem_de_mando_existe"]
    assert v and "0.81" in (v[0].observado or "")


def test_mando_nao_dispara_em_amostra_pequena():
    rel = ap.auditar([jogo(lh=1.18, la=1.45)])
    assert "vantagem_de_mando_existe" not in nomes(rel)


def test_pega_ev_alto_demais_na_rodada():
    m = [{"mercado": "Over 2.5 gols", "ev": 0.10}]
    rodada = [jogo(lh=1.55, la=1.20, casa=f"C{i}", mercados=m) for i in range(12)]
    rel = ap.auditar(rodada)
    v = [x for x in rel.violacoes if x.premissa == "ev_alto_e_raro"]
    assert v and v[0].observado == "100%"


# ── robustez ─────────────────────────────────────────────────────────

def test_premissa_quebrada_nao_derruba_o_auditor():
    def explode(_jogos):
        raise RuntimeError("boom")
        yield  # pragma: no cover
    rel = ap.auditar([jogo()], premissas=[explode])
    assert len(rel.violacoes) == 1
    assert "a propria premissa falhou" in rel.violacoes[0].detalhe


def test_jogo_sem_lambda_e_ignorado_em_silencio():
    incompleto = {"leagueId": "x", "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"},
                  "stats": {}, "mercados": []}
    assert ap.auditar([incompleto]).violacoes == []


def test_premissa_estrutural_do_manifesto_roda(monkeypatch):
    """#210 - a decima premissa olha o codigo, nao a saida."""
    import backend.config.footystats_manifest as mf
    monkeypatch.setattr(mf, "verificar", lambda: {
        "bloqueia": ["campo_x: mapeado e ausente do manifesto."],
        "avisa": ["campo_y: ganhou consumidor."],
    })
    rel = ap.auditar([], premissas=[ap.premissa_manifesto_footystats_em_dia])
    assert sorted(v.severidade for v in rel.violacoes) == [ap.SEV_CRITICO, ap.SEV_MEDIO]
    assert not rel.ok


def test_premissa_estrutural_no_estado_atual_nao_bloqueia():
    rel = ap.auditar([], premissas=[ap.premissa_manifesto_footystats_em_dia])
    assert rel.ok, [v.linha() for v in rel.violacoes]


def test_rodada_coerente_nao_acusa_nada_inclui_o_manifesto():
    """A premissa estrutural entra no conjunto padrao."""
    assert ap.premissa_manifesto_footystats_em_dia in ap.PREMISSAS


def test_relatorio_serializa():
    rel = ap.auditar([jogo(over25Prob=75.0)])
    d = rel.para_dict()
    assert d["ok"] is False and d["jogos"] == 1
    assert d["violacoes"][0]["severidade"] == ap.SEV_CRITICO
