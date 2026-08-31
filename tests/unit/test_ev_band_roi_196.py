"""#196 — a tabela que responde "os VALOR DETECTADO se pagam?".

Três defeitos que, juntos, tornavam a pergunta impossível de responder:

1. `compute_hit_rate_by_ev_band` usava `abs(ev)` — um pick de EV -35% caía na
   mesma faixa "20-100%" de um de +35%. Como os mercados rejeitados aparecem
   com EV de -20% a -36%, a faixa alta vivia poluída pelos piores picks do dia.
2. A auditoria recalculava EV de `prob_max × odd_minima` em vez de usar o `ev`
   do próprio pick — e `odd_minima` vira a odd justa (1/prob) quando não há
   mercado, o que dava EV exatamente zero e uma "odd da casa" que era a própria
   probabilidade do modelo.
3. `hit_rate_by_ev`, `roi`, `ev_metrics` e `sharpe_ratio` eram calculados todo
   dia e nunca gravados — o registro do cron guardava 10 campos, nenhum deles.
"""
import inspect

from backend.services.backtesting import compute_hit_rate_by_ev_band


# ── 1. EV com sinal ───────────────────────────────────────────────────

def test_ev_negativo_nao_conta_como_positivo():
    """O caso que corrompia a faixa alta: -25% ia parar em 20-100%."""
    picks = [
        {"ev_pct": 25.0, "outcome": True},
        {"ev_pct": -25.0, "outcome": False},
    ]
    bandas = {b["band"]: b for b in compute_hit_rate_by_ev_band(picks)}
    assert bandas["20-100%"]["total"] == 1
    assert bandas["20-100%"]["correct"] == 1
    assert bandas["20-100%"]["accuracy"] == 1.0
    assert bandas["-100--10%"]["total"] == 1
    assert bandas["-100--10%"]["correct"] == 0


def test_faixas_negativas_existem():
    bandas = [b["band"] for b in compute_hit_rate_by_ev_band([])]
    assert "-100--10%" in bandas and "-10-0%" in bandas


# ── 2. ROI por faixa — a metrica que decide ───────────────────────────

def test_roi_por_faixa_pode_ser_positivo_com_acerto_minoritario():
    """O ponto todo do EV: 40% de acerto a odd 3.00 dá +20% de ROI.

    Julgar "VALOR DETECTADO" por taxa de acerto leva à conclusão errada.
    """
    picks = [
        {"ev_pct": 25.0, "outcome": True, "odd": 3.0},
        {"ev_pct": 25.0, "outcome": False, "odd": 3.0},
        {"ev_pct": 25.0, "outcome": False, "odd": 3.0},
        {"ev_pct": 25.0, "outcome": True, "odd": 3.0},
        {"ev_pct": 25.0, "outcome": False, "odd": 3.0},
    ]
    banda = next(b for b in compute_hit_rate_by_ev_band(picks) if b["band"] == "20-100%")
    assert banda["accuracy"] == 0.4          # erra a maioria
    assert banda["roi"] == 0.2               # e ainda assim lucra 20%
    assert banda["n_with_odds"] == 5


def test_roi_ausente_quando_nao_ha_odd_real():
    """Sem odd real não há retorno simulável — ROI fica None, não zero."""
    picks = [{"ev_pct": 12.0, "outcome": True, "odd": None}]
    banda = next(b for b in compute_hit_rate_by_ev_band(picks) if b["band"] == "10-20%")
    assert banda["total"] == 1
    assert banda["roi"] is None
    assert banda["n_with_odds"] == 0


# ── 3. cron: EV do pick, odd real, e persistencia ─────────────────────

def _cron_src():
    import backend.cron_handler as cron
    return inspect.getsource(cron)


def test_cron_usa_o_ev_do_proprio_pick():
    src = _cron_src()
    assert '_ev_field = merc.get("ev")' in src, "o EV auditado deve ser o do card"
    assert 'merc.get("calibrated_probability")' in src, "prob deve ser a calibrada"


def test_cron_so_grava_book_odd_quando_a_odd_e_real():
    src = _cron_src()
    assert '"book_odd": float(_odds_reais) if _odds_reais else None' in src, (
        "book_odd nao pode receber odd_minima — vira 1/prob e a 'casa' passa a "
        "ser o proprio modelo na comparacao do /metrics/brier"
    )


def test_cron_persiste_metricas_de_ev_e_roi():
    src = _cron_src()
    assert '"hit_rate_by_ev": batch_summary.get("hit_rate_by_ev", [])' in src
    assert '"roi": batch_summary.get("roi", {})' in src
    assert '"ev_metrics": batch_summary.get("ev_metrics", {})' in src
