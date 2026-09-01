"""#202 — o snapshot do cron voltou a ser cumulativo.

Combinação de duas mudanças minhas: o #197 fez `audit_date` filtrar de verdade
(era o objetivo), mas o cron passa `date_filter`, que às vezes É uma data ISO.
Resultado: o batch das 05:01 gravou 170 picks (um dia) numa tabela cujas linhas
anteriores tinham 5.951 (acumulado), e o #199 passou a servir isso como
snapshot global — o ReliabilityCard exibiu 170.

`brier_history` é cumulativo por contrato. Quem fatia por dia é `daily_series`.
"""
import backend.services.brier_service as bs


def test_run_after_audit_ignora_o_recorte_e_so_etiqueta(monkeypatch):
    chamadas = {}

    def _fake_calc(audit_date=None):
        chamadas["audit_date"] = audit_date
        return {"total_picks": 5951, "audit_date": None, "accuracy": 73.8}

    salvos = {}
    monkeypatch.setattr(bs, "calculate_snapshot", _fake_calc)
    monkeypatch.setattr(bs, "persist_snapshot", lambda snap, n=0: salvos.update(snap=snap, n=n) or True)

    snap = bs.run_after_audit(new_picks=33, audit_date="2026-08-31")

    # o recorte NAO pode ser repassado — snapshot e cumulativo
    assert chamadas["audit_date"] is None, "calculate_snapshot foi chamado com recorte"
    assert snap["total_picks"] == 5951
    # a etiqueta sobrevive, para o historico nao perder a referencia
    assert snap["audit_date"] == "2026-08-31"
    assert salvos["snap"]["total_picks"] == 5951


def test_rotulo_do_cron_tambem_vira_etiqueta(monkeypatch):
    monkeypatch.setattr(bs, "calculate_snapshot",
                        lambda audit_date=None: {"total_picks": 100, "audit_date": None})
    monkeypatch.setattr(bs, "persist_snapshot", lambda snap, n=0: True)
    snap = bs.run_after_audit(audit_date="yesterday")
    assert snap["audit_date"] == "yesterday"


def test_calculate_snapshot_segue_fatiavel_sob_demanda():
    """O fatiamento por dia continua existindo — só não é o que o cron persiste."""
    import inspect
    src = inspect.getsource(bs.calculate_snapshot)
    assert "audit_date" in src, "calculate_snapshot(audit_date) continua disponivel"
