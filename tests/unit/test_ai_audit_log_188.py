"""
#188 Fase 1 — testes da infraestrutura de medição da camada de IA.

Cobre:
1. Validador de schema da saída do modelo (confidence 0-100, explanation
   não vazia, auditOdds numérico quando presente)
2. Storage SQLite fallback (roundtrip, fill_actual_result, taxa de JSON inválido)
3. Garantia "nunca levanta" (storage quebrado não derruba o fluxo)
4. extract_actual_result do script de backfill
5. Fim-a-fim no analyze_match: timeout/HTTP error → stage=fallback_static
   logado; sucesso → stage=production; log explodindo não derruba a análise
6. Postgres configurado mas fora do ar → fallback para SQLite (log-and-degrade)
7. Retenção: purge_old_records preserva não-resolvidos por default
"""
import asyncio
import json
import sqlite3
import sys
import types

import pytest

from backend.ai import audit_log
from backend.ai.audit_log import (
    STAGE_FALLBACK,
    STAGE_PRODUCTION,
    fill_actual_result,
    get_invalid_json_rate,
    get_pending_result_match_ids,
    log_ai_audit,
    validate_ai_output,
)


# ──────────────────────────────────────────────
# 1. Validador de schema
# ──────────────────────────────────────────────


class TestValidateAiOutput:

    def _valid_payload(self, **overrides):
        p = {
            "confidence": 74,
            "resumo_analitico": "Casa pressiona; lambda 1.45 sustenta over.",
        }
        p.update(overrides)
        return p

    def test_valid_output_passes(self):
        ok, errors = validate_ai_output(self._valid_payload())
        assert ok is True and errors == []

    @pytest.mark.parametrize("bad_conf", [-1, 101, "74", None, True])
    def test_confidence_invalid(self, bad_conf):
        ok, errors = validate_ai_output(self._valid_payload(confidence=bad_conf))
        assert ok is False
        assert any("confidence" in e for e in errors)

    @pytest.mark.parametrize("bad_expl", ["", "   ", None, 42])
    def test_explanation_invalid(self, bad_expl):
        ok, errors = validate_ai_output(self._valid_payload(resumo_analitico=bad_expl))
        assert ok is False
        assert any("explanation" in e for e in errors)

    def test_audit_odds_absent_is_ok(self):
        ok, _ = validate_ai_output(self._valid_payload())
        assert ok is True

    def test_audit_odds_numeric_is_ok(self):
        ok, _ = validate_ai_output(self._valid_payload(auditOdds=1.85))
        assert ok is True

    @pytest.mark.parametrize("bad_odds", ["1.85", True, {}])
    def test_audit_odds_non_numeric_fails(self, bad_odds):
        ok, errors = validate_ai_output(self._valid_payload(auditOdds=bad_odds))
        assert ok is False
        assert any("auditOdds" in e for e in errors)

    def test_field_map_override_for_qwen_schema(self):
        # Fase 3: schema Qwen pode usar "explanation" direto
        payload = {"confidence": 60, "explanation": "ok", "auditOdds": 1.9}
        ok, errors = validate_ai_output(payload, field_map={"explanation": "explanation"})
        assert ok is True, errors

    def test_non_dict_output(self):
        ok, errors = validate_ai_output(None)  # type: ignore[arg-type]
        assert ok is False and errors


# ──────────────────────────────────────────────
# 2. Storage (SQLite fallback) — roundtrip
# ──────────────────────────────────────────────


@pytest.fixture
def sqlite_env(tmp_path, monkeypatch):
    """Força o fallback SQLite num arquivo temporário."""
    db = tmp_path / "ai_audit_test.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AI_AUDIT_SQLITE_PATH", str(db))
    return db


class TestSqliteStorage:

    def _log_one(self, *, match_id="brasileirao-serie-a-A-B-123.0", valid=True, stage=STAGE_PRODUCTION):
        return log_ai_audit(
            provider="mistral",
            model="mistral-large-latest",
            stage=stage,
            match_id=match_id,
            league_id="brasileirao-serie-a",
            home_team="A",
            away_team="B",
            prompt_version="3.0",
            prompt_sha256="abc123",
            prompt_chars=4200,
            inputs={"match_stats": {"lambdaHome": 1.2}, "odds": {"home": 1.9}},
            output={"confidence": 70, "resumo_analitico": "ok"} if valid else None,
            confidence=70.0 if valid else None,
            valid_json=valid,
            validation_errors=[] if valid else ["JSONDecodeError: x"],
            latency_ms=1234,
            error=None if valid else "JSONDecodeError: x",
        )

    def test_roundtrip_insert(self, sqlite_env):
        assert self._log_one() is True
        conn = sqlite3.connect(sqlite_env)
        row = conn.execute(
            "SELECT provider, stage, confidence, valid_json, inputs, actual_result "
            "FROM ai_audit_log"
        ).fetchone()
        conn.close()
        assert row[0] == "mistral"
        assert row[1] == STAGE_PRODUCTION
        assert row[2] == 70.0
        assert row[3] == 1
        assert json.loads(row[4])["odds"]["home"] == 1.9
        assert row[5] is None  # actualResult reservado para pós-jogo

    def test_fill_actual_result_idempotent(self, sqlite_env):
        self._log_one()
        result = {"total_goals": 3, "btts": True, "result_1x2": "1",
                  "total_corners": 9, "total_cards": 4}
        n1 = fill_actual_result("brasileirao-serie-a-A-B-123.0", result)
        n2 = fill_actual_result("brasileirao-serie-a-A-B-123.0", result)
        assert n1 == 1
        assert n2 == 0  # só linhas com actual_result IS NULL
        conn = sqlite3.connect(sqlite_env)
        stored = conn.execute("SELECT actual_result FROM ai_audit_log").fetchone()[0]
        conn.close()
        assert json.loads(stored)["total_goals"] == 3

    def test_pending_match_ids(self, sqlite_env):
        self._log_one(match_id="m1")
        self._log_one(match_id="m2")
        fill_actual_result("m1", {"total_goals": 1})
        pending = get_pending_result_match_ids()
        assert pending == ["m2"]

    def test_invalid_json_rate(self, sqlite_env):
        self._log_one(valid=True)
        self._log_one(valid=True)
        self._log_one(valid=False, stage=STAGE_FALLBACK)
        rate = get_invalid_json_rate(days=1)
        assert rate["total"] == 3
        assert rate["invalid"] == 1
        assert rate["rate"] == round(1 / 3, 4)
        key = f"mistral/{STAGE_FALLBACK}"
        assert rate["by_stage"][key]["invalid"] == 1


# ──────────────────────────────────────────────
# 3. Nunca levanta (log-and-degrade)
# ──────────────────────────────────────────────


class TestNeverRaises:

    def test_log_with_broken_storage_returns_false(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Caminho de SQLite impossível → insert falha → False, sem exceção
        monkeypatch.setenv("AI_AUDIT_SQLITE_PATH", "Z:/caminho/inexistente/x.db")
        ok = log_ai_audit(provider="mistral", stage=STAGE_PRODUCTION, valid_json=True)
        assert ok is False

    def test_metrics_with_broken_storage_return_zero(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("AI_AUDIT_SQLITE_PATH", "Z:/caminho/inexistente/x.db")
        assert get_invalid_json_rate()["total"] == 0
        assert get_pending_result_match_ids() == []
        assert fill_actual_result("x", {}) == 0


# ──────────────────────────────────────────────
# 4. extract_actual_result (script de backfill)
# ──────────────────────────────────────────────


class TestAnalyzeMatchInstrumentation:
    """Fim-a-fim: os hooks do analyze_match gravam o registro certo em cada
    caminho e jamais alteram a resposta devolvida ao chamador."""

    def _service(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
        from backend.services.mistral_analysis import MistralAnalysisService
        return MistralAnalysisService()

    def _rows(self, db):
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT stage, valid_json, error, confidence, match_id, latency_ms, prompt_sha256 "
            "FROM ai_audit_log"
        ).fetchall()
        conn.close()
        return rows

    def _run(self, service, **kw):
        return asyncio.run(service.analyze_match(
            home_team="A", away_team="B", league="Liga X",
            match_stats={"lambdaHome": 1.2}, odds={"home": 1.9},
            audit_meta={"match_id": "liga-x-A-B-1.0", "league_id": "liga-x"},
            **kw,
        ))

    def test_timeout_logs_fallback_static_and_returns_fallback(self, sqlite_env, monkeypatch):
        import httpx
        service = self._service(monkeypatch)

        async def _boom(prompt):
            raise httpx.TimeoutException("connect timeout")

        monkeypatch.setattr(service, "_call_mistral_api", _boom)
        result = self._run(service)
        # Resposta de fallback continua sendo devolvida (comportamento intacto)
        assert result.confidence == 0 or result.nivel_confianca in ("Baixo", "Alto", "Médio")
        rows = self._rows(sqlite_env)
        assert len(rows) == 1
        stage, valid, error, conf, mid, latency, _sha = rows[0]
        assert stage == "fallback_static"
        assert valid == 0
        assert "TimeoutException" in error
        assert conf is None
        assert mid == "liga-x-A-B-1.0"
        assert latency is not None and latency >= 0

    def test_invalid_json_counts_as_invalid_in_production_path(self, sqlite_env, monkeypatch):
        """JSON inválido é engolido por _parse_analysis (devolve fallback SEM
        levantar) — logo fica no caminho de produção. O log DEVE marcá-lo
        valid_json=False mesmo assim (#188: sem o marcador _last_parse_error,
        contaria como sucesso e a taxa de JSON inválido ficaria cega)."""
        service = self._service(monkeypatch)

        async def _bad_json(prompt):
            return "not-a-json{{{"

        monkeypatch.setattr(service, "_call_mistral_api", _bad_json)
        result = self._run(service)
        assert result is not None  # UI continua recebendo o fallback
        rows = self._rows(sqlite_env)
        assert len(rows) == 1
        stage, valid, error, _conf, _mid, _lat, _sha = rows[0]
        assert stage == "production"  # resposta servida veio do caminho normal
        assert valid == 0             # ...mas conta na taxa de JSON inválido
        assert "JSONDecodeError" in error

    def test_success_logs_production_with_hash_and_latency(self, sqlite_env, monkeypatch):
        from backend.services.mistral_analysis import MistralAnalysisService
        service = self._service(monkeypatch)
        valid_response = MistralAnalysisService._get_fallback_static()

        async def _ok(prompt):
            return "{}"

        monkeypatch.setattr(service, "_call_mistral_api", _ok)
        monkeypatch.setattr(service, "_parse_analysis", lambda raw: valid_response)
        result = self._run(service)
        assert result is valid_response
        rows = self._rows(sqlite_env)
        assert len(rows) == 1
        stage, valid, error, conf, _mid, latency, sha = rows[0]
        assert stage == "production"
        assert error is None
        assert conf == float(valid_response.confidence)
        assert latency is not None and latency >= 0
        assert sha is not None and len(sha) == 64  # sha256 do prompt

    def test_audit_log_exploding_never_breaks_analysis(self, sqlite_env, monkeypatch):
        from backend.services.mistral_analysis import MistralAnalysisService
        import backend.ai.audit_log as audit_mod
        service = self._service(monkeypatch)
        valid_response = MistralAnalysisService._get_fallback_static()

        async def _ok(prompt):
            return "{}"

        def _explode(**kwargs):
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(service, "_call_mistral_api", _ok)
        monkeypatch.setattr(service, "_parse_analysis", lambda raw: valid_response)
        monkeypatch.setattr(audit_mod, "log_ai_audit", _explode)
        result = self._run(service)  # não pode levantar
        assert result is valid_response


class TestPostgresUnreachableFallsBack:
    """DATABASE_URL setada mas PG fora do ar → registro cai no SQLite."""

    def test_pg_connect_failure_falls_back_to_sqlite(self, sqlite_env, monkeypatch):
        fake_pg = types.ModuleType("psycopg2")

        def _refuse(*a, **kw):
            raise ConnectionRefusedError("PG down")

        fake_pg.connect = _refuse
        monkeypatch.setitem(sys.modules, "psycopg2", fake_pg)
        monkeypatch.setenv("DATABASE_URL", "postgres://fake:5432/db")
        # garante que nenhuma conexão warm de teste anterior seja reutilizada
        import backend.ai.audit_log as audit_mod
        monkeypatch.setattr(audit_mod, "_pg_conn", None)

        ok = log_ai_audit(provider="mistral", stage=STAGE_PRODUCTION,
                          match_id="m-pg-down", valid_json=True)
        assert ok is True  # gravou — no fallback SQLite
        conn = sqlite3.connect(sqlite_env)
        row = conn.execute(
            "SELECT match_id FROM ai_audit_log WHERE match_id = 'm-pg-down'"
        ).fetchone()
        conn.close()
        assert row is not None


class TestRetention:

    def test_purge_keeps_unresolved_by_default(self, sqlite_env):
        log_ai_audit(provider="mistral", stage=STAGE_PRODUCTION,
                     match_id="old-resolved", valid_json=True)
        log_ai_audit(provider="mistral", stage=STAGE_PRODUCTION,
                     match_id="old-unresolved", valid_json=True)
        fill_actual_result("old-resolved", {"total_goals": 2})
        # Envelhece os registros para além da janela
        conn = sqlite3.connect(sqlite_env)
        conn.execute("UPDATE ai_audit_log SET created_at = '2020-01-01T00:00:00+00:00'")
        conn.commit()
        conn.close()

        from backend.ai.audit_log import purge_old_records
        n = purge_old_records(days=90)
        assert n == 1  # só o resolvido; o não-resolvido fica para o backfill
        conn = sqlite3.connect(sqlite_env)
        remaining = [r[0] for r in conn.execute("SELECT match_id FROM ai_audit_log")]
        conn.close()
        assert remaining == ["old-unresolved"]


class TestGetAuditStats:
    """Endpoint de baseline (#188): volume por liga + hashes de prompt."""

    def test_stats_aggregate_by_league_and_prompt(self, sqlite_env):
        for i, (league, sha) in enumerate([
            ("brazil-serie-a", "aaa111"), ("brazil-serie-a", "aaa111"),
            ("brazil-serie-b", "aaa111"),
        ]):
            log_ai_audit(provider="mistral", stage=STAGE_PRODUCTION,
                         match_id=f"m{i}", league_id=league,
                         prompt_sha256=sha, valid_json=True)
        from backend.ai.audit_log import get_audit_stats
        stats = get_audit_stats(days=1)
        assert stats["totals"]["total"] == 3
        assert stats["by_league"][0] == {"league_id": "brazil-serie-a", "n": 2}
        assert stats["by_league"][1] == {"league_id": "brazil-serie-b", "n": 1}
        assert len(stats["by_prompt"]) == 1  # UM hash de prompt = baseline limpo
        assert stats["by_prompt"][0]["prompt_sha256"] == "aaa111"
        assert stats["by_prompt"][0]["n"] == 3
        assert stats["pending_results"] == 3  # nenhum actual_result ainda

    def test_stats_never_raise_with_broken_storage(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("AI_AUDIT_SQLITE_PATH", "Z:/caminho/inexistente/x.db")
        from backend.ai.audit_log import get_audit_stats
        stats = get_audit_stats(days=7)
        assert stats["totals"]["total"] == 0
        assert stats["by_league"] == []


class TestThreadSafetySmoke:
    """psycopg2 module-level: acesso serializado por _PG_LOCK; SQLite abre
    conexão por chamada. Smoke: escrita concorrente não corrompe nem levanta."""

    def test_concurrent_writes_all_succeed(self, sqlite_env):
        import threading as _th
        results = []

        def _write(i):
            results.append(log_ai_audit(
                provider="mistral", stage=STAGE_PRODUCTION,
                match_id=f"concurrent-{i}", valid_json=True,
            ))

        threads = [_th.Thread(target=_write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(results) and len(results) == 10
        conn = sqlite3.connect(sqlite_env)
        n = conn.execute(
            "SELECT COUNT(*) FROM ai_audit_log WHERE match_id LIKE 'concurrent-%'"
        ).fetchone()[0]
        conn.close()
        assert n == 10


class TestExtractActualResult:

    def _record(self, **over):
        r = {
            "score": {"home": 2, "away": 1},
            "stats": {
                "homeCornersCount": 5, "awayCornersCount": 4,
                "homeYellowCards": 2, "awayYellowCards": 1,
                "homeRedCards": 0, "awayRedCards": 1,
            },
        }
        r.update(over)
        return r

    def test_extracts_full_result(self):
        from scripts.fill_ai_audit_results import extract_actual_result
        res = extract_actual_result(self._record())
        assert res == {
            "home_goals": 2, "away_goals": 1, "total_goals": 3,
            "btts": True, "result_1x2": "1",
            "total_corners": 9, "total_cards": 4,
        }

    def test_no_verified_score_returns_none(self):
        from scripts.fill_ai_audit_results import extract_actual_result
        assert extract_actual_result({"score": {}, "stats": {}}) is None

    def test_zero_is_valid_value_not_missing(self):
        # 0 cartões/escanteios é dado válido, não ausência (#078v)
        from scripts.fill_ai_audit_results import extract_actual_result
        rec = self._record(score={"home": 0, "away": 0})
        rec["stats"] = {"homeCornersCount": 0, "awayCornersCount": 0,
                       "homeYellowCards": 0, "awayYellowCards": 0,
                       "homeRedCards": 0, "awayRedCards": 0}
        res = extract_actual_result(rec)
        assert res["btts"] is False
        assert res["result_1x2"] == "X"
        assert res["total_corners"] == 0
        assert res["total_cards"] == 0
