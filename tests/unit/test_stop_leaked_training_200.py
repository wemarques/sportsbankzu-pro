# -*- coding: utf-8 -*-
"""#200 — o retreino de calibradores nao pode rodar sozinho em fonte vazada.

`retrain_all_calibrators()` le os pares de `audit_results`, que guarda o
prognostico RECOMPUTADO depois do jogo, nao o publicado. Foi provado
empiricamente: Lecce x Roma (0-4) publicou "Under 2.5" e recomputou "Over 2.5";
Atalanta x Bologna (1-0) publicou "Escanteios Over 10.5" e recomputou "Under
8.5". Picks que erram trocam de lado e somem da amostra; os que acertam ficam.

A curva de calibracao aprendida sobre isso nao e diagnostico — ela vai para
producao em `calibrate_prob()`, antes da classificacao e do calculo de EV.
Ate existir o ledger de picks publicados, o retreino automatico fica desligado.
"""
import backend.cron_handler as ch


def _boom(*a, **k):  # pragma: no cover - so e chamado se o gate falhar
    raise AssertionError("retrain_all_calibrators foi chamado com o gate fechado")


def test_gate_fechado_por_padrao(monkeypatch):
    monkeypatch.delenv("CRON_AUTO_RETRAIN_CALIBRATORS", raising=False)
    assert ch._calibrator_retrain_enabled() is False


def test_gate_aceita_apenas_valores_explicitos(monkeypatch):
    for ligado in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("CRON_AUTO_RETRAIN_CALIBRATORS", ligado)
        assert ch._calibrator_retrain_enabled() is True, ligado
    for desligado in ("0", "false", "no", "", "  "):
        monkeypatch.setenv("CRON_AUTO_RETRAIN_CALIBRATORS", desligado)
        assert ch._calibrator_retrain_enabled() is False, repr(desligado)


def test_retrain_semanal_pula_com_gate_fechado(monkeypatch):
    monkeypatch.delenv("CRON_AUTO_RETRAIN_CALIBRATORS", raising=False)
    import backend.modeling.calibrator as cal
    monkeypatch.setattr(cal, "retrain_all_calibrators", _boom)

    r = ch._run_retrain_calibrators()

    assert r["status"] == "skipped"
    assert r["reason"] == "calibrator_retrain_disabled"


def test_retrain_semanal_roda_quando_forcado_no_evento(monkeypatch):
    monkeypatch.delenv("CRON_AUTO_RETRAIN_CALIBRATORS", raising=False)
    import backend.modeling.calibrator as cal
    monkeypatch.setattr(cal, "retrain_all_calibrators", lambda: [{"league": "x", "accepted": True}])

    r = ch._run_retrain_calibrators(force=True)

    assert r["status"] == "success"
    assert r["calibrators"] == [{"league": "x", "accepted": True}]


def test_retrain_semanal_roda_com_gate_aberto(monkeypatch):
    monkeypatch.setenv("CRON_AUTO_RETRAIN_CALIBRATORS", "1")
    import backend.modeling.calibrator as cal
    monkeypatch.setattr(cal, "retrain_all_calibrators", lambda: [])

    assert ch._run_retrain_calibrators()["status"] == "success"


def test_dispatch_repassa_force_do_evento(monkeypatch):
    vistos = {}
    monkeypatch.setattr(ch, "_run_retrain_calibrators", lambda force=False: vistos.setdefault("force", force))

    ch.cron_handler({"action": "retrain_calibrators", "force": True}, None)
    assert vistos["force"] is True

    vistos.clear()
    ch.cron_handler({"action": "retrain_calibrators"}, None)
    assert vistos["force"] is False
