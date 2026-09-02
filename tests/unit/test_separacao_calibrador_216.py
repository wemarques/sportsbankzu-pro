# -*- coding: utf-8 -*-
"""#216 - separar o isotonico da deflacao antes de decidir a quarentena do #200.

A primeira leitura do #215 (25 linhas de championship, league-one e serie B)
deu o veredito "o calibrador AFASTA da ancora" — 25,1pp contra 16,7pp da crua.
Analisada, a saida mostrava algo mais forte que o vies medio:

    amplitude   empirico 75,0pp | crua 29,0pp | calibrada 11,4pp
    ajuste      calibrada = 29,0 + 0,411 x crua      r = 0,997

Um ajuste AFIM com r=0,997 nao e um isotonico que aprendeu alguma coisa —
isotonico aprendido e escada irregular. E a assinatura de um encolhimento
suave e monotonico, que e o que a deflacao progressiva por nos (#105) faz por
construcao. E o proprio log de producao confirmava:

    [GOLS-TRACE] championship Under 3.5 raw=0.8219 calib_iso=0.8219 ... final=0.7249

`calib_iso` identico ao `raw`: o isotonico nao agiu, a queda foi da banda.

Ou seja: `calibrated_probability` sempre foi o PRODUTO de dois passos, e medir
so o produto atribuia ao calibrador o que era da deflacao. Estes testes travam
a separacao.
"""
import backend.services.comparador_ancora as ca
import backend.services.ev_classification as ev
from backend.models.market_output import MarketOutput


# ── o detalhe existe e separa os dois passos ─────────────────────────

def test_detalhe_expoe_os_dois_passos():
    d = ev._calibrar_com_detalhe(0.70, "Over 2.5", "championship", "NORMAL")
    assert d.raw == 0.70
    assert d.iso is not None and d.final is not None
    assert d.final <= d.iso, "a deflacao nunca aumenta a probabilidade"


def test_fachada_devolve_o_mesmo_numero_de_antes():
    """`_calibrate_and_deflate` nao pode ter mudado de valor com o refactor."""
    for mercado in ("Over 2.5", "Under 3.5", "BTTS", "Cartoes Over 2.5",
                    "Escanteios Over 8.5", "1X2_home"):
        d = ev._calibrar_com_detalhe(0.70, mercado, "championship", "NORMAL")
        assert ev._calibrate_and_deflate(0.70, mercado, "championship", "NORMAL") == d.final


def test_tipo_de_banda_por_familia():
    """Gols levam meia banda (#165-e); cartoes, escanteios e 1X2 levam inteira."""
    def tipo(m):
        return ev._calibrar_com_detalhe(0.70, m, "championship", "NORMAL").tipo_banda
    assert tipo("Over 2.5") == "meia"
    assert tipo("Under 3.5") == "meia"
    assert tipo("BTTS") == "meia-btts"
    assert tipo("Cartoes Over 2.5") == "inteira"
    assert tipo("Escanteios Over 8.5") == "inteira"
    assert tipo("1X2_home") == "inteira"


def test_banda_inteira_corta_mais_que_meia():
    """A razao de ser da separacao: as familias sem trace levavam o corte maior."""
    meia = ev._calibrar_com_detalhe(0.70, "Over 2.5", "", "NORMAL")
    inteira = ev._calibrar_com_detalhe(0.70, "Cartoes Over 2.5", "", "NORMAL")
    assert inteira.final < meia.final


# ── o payload carrega a separacao ────────────────────────────────────

def test_market_output_publica_iso_e_banda():
    mo = MarketOutput(
        market_type="Cards", selection="Cartoes Over 2.5",
        raw_probability=0.80, iso_probability=0.80,
        calibrated_probability=0.62, deflation_band_type="inteira",
        display_label="Cartoes Over 2.5",
    )
    d = mo.to_legacy_mercado()
    assert d["iso_probability"] == 0.80
    assert d["banda"] == "inteira"


def test_payload_antigo_sem_os_campos_nao_quebra():
    mo = MarketOutput(market_type="Cards", selection="x", raw_probability=0.8,
                      calibrated_probability=0.6, display_label="x")
    d = mo.to_legacy_mercado()
    assert d["iso_probability"] is None and d["banda"] is None


# ── o comparador usa a separacao ─────────────────────────────────────

def _jogo(mercados, stats):
    return {"leagueId": "championship", "homeTeam": {"name": "A"},
            "awayTeam": {"name": "B"}, "stats": stats, "mercados": mercados}


def _mk(nome, crua, iso, calib, banda="inteira"):
    return {"mercado": nome, "raw_probability": crua, "iso_probability": iso,
            "calibrated_probability": calib, "banda": banda}


def test_comparador_le_iso_e_banda():
    c = ca.comparar([_jogo([_mk("Cartoes Over 2.5", 0.747, 0.747, 0.599)],
                           {"over25_cards_percentage": 82})])
    l = c.linhas[0]
    assert l.iso == 74.7 and l.banda == "inteira"
    assert round(l.erro_iso) == -7 and round(l.erro_calibrado) == -22


def test_isotonico_inerte_e_detectado():
    """O caso real de 01/09: calib_iso identico ao raw em toda a rodada."""
    js = [_jogo([_mk("Cartoes Over 2.5", 0.80, 0.80, 0.60)],
                {"over25_cards_percentage": 82}) for _ in range(5)]
    c = ca.comparar(js)
    assert all(l.isotonico_inerte for l in c.linhas)
    v = c.veredito_isotonico()
    assert "INERTE" in v and "#105" in v


def test_isotonico_que_agiu_e_medido_contra_a_crua():
    js = [_jogo([_mk("Cartoes Over 2.5", 0.70, 0.80, 0.60)],
                {"over25_cards_percentage": 82}) for _ in range(5)]
    v = ca.comparar(js).veredito_isotonico()
    assert "INERTE" not in v and "APROXIMA" in v   # 80 esta mais perto de 82 que 70


def test_veredito_isotonico_sem_o_campo():
    """Payload de antes do #216 nao pode produzir veredito inventado."""
    j = _jogo([{"mercado": "Cartoes Over 2.5", "raw_probability": 0.8,
                "calibrated_probability": 0.6}], {"over25_cards_percentage": 82})
    assert "sem dado de isotonico" in ca.comparar([j]).veredito_isotonico()


def test_contagem_por_banda():
    c = ca.comparar([_jogo(
        [_mk("Cartoes Over 2.5", 0.8, 0.8, 0.6, "inteira"),
         _mk("Escanteios Over 8.5", 0.7, 0.7, 0.55, "inteira")],
        {"over25_cards_percentage": 82, "over85_corners_percentage": 90})])
    assert c.por_banda() == {"inteira": 2}


def test_resumo_traz_o_bloco_isotonico():
    c = ca.comparar([_jogo([_mk("Cartoes Over 2.5", 0.80, 0.80, 0.60)],
                           {"over25_cards_percentage": 82})])
    assert c.resumo()["isotonica"]["n"] == 1
