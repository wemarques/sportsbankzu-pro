"""#166 — Odds ingestion diagnostic endpoint.
#170 — Corners model structural gap diagnostic (Fase 1).
#171 — Forensic endpoint for the auto-correction cascade incident.

Registered only when ODDS_INGESTION_V2=true (see main.py). Requires
X-Debug-Key header matching ODDS_DEBUG_KEY env var — blocks anonymous
access even when the flag is on.
"""
from __future__ import annotations

import os
import time
from fastapi import APIRouter, Header, HTTPException
from typing import Optional, List, Tuple

router = APIRouter(prefix="/api/debug", tags=["debug"])

# Lazy singletons — avoid eager instantiation at module import time.
# Clients read env vars + open SQLite caches on __init__, so lazy keeps
# module import cheap and matches the pattern used elsewhere in the code.
_afc_singleton = None
_fsc_singleton = None


def _get_afc():
    global _afc_singleton
    if _afc_singleton is None:
        from backend.services.api_football_client import APIFootballClient
        _afc_singleton = APIFootballClient()
    return _afc_singleton


def _get_fsc():
    global _fsc_singleton
    if _fsc_singleton is None:
        from backend.services.footstats_client import FootyStatsClient
        _fsc_singleton = FootyStatsClient()
    return _fsc_singleton


def _pearson(xs: list, ys: list) -> Optional[float]:
    """Simple Pearson correlation; returns None if insufficient / constant data."""
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    xs2, ys2 = zip(*pairs)
    mx = sum(xs2) / n
    my = sum(ys2) / n
    num = sum((xs2[i] - mx) * (ys2[i] - my) for i in range(n))
    dx = sum((xs2[i] - mx) ** 2 for i in range(n))
    dy = sum((ys2[i] - my) ** 2 for i in range(n))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx ** 0.5 * dy ** 0.5), 4)


def _require_debug_key(header_key: Optional[str]) -> None:
    expected = os.getenv("ODDS_DEBUG_KEY", "")
    if not expected:
        raise HTTPException(503, "ODDS_DEBUG_KEY not configured")
    if not header_key or header_key != expected:
        raise HTTPException(401, "invalid X-Debug-Key")


@router.get("/historico-odds")
def historico_odds(
    league_id: str = "championship",
    n: int = 5,
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """#225-a - o historico do league-matches traz odds pre-jogo preenchidas?

    Instrumento DESCARTAVEL. Existe para responder UMA pergunta e sair.

    A pergunta: o `get_all_league_matches` devolve, por partida, estatistica
    completa (placar, cartoes, escanteios) e o manifesto lista `odds_ft_*`
    como CONSUMIDO. Se essas colunas vierem preenchidas no historico, da para
    reconstruir prognostico E EV de temporadas inteiras filtrando os jogos
    anteriores a cada data - milhares de observacoes limpas, sem esperar o
    ledger acumular. Se vierem nulas, sobra so a probabilidade.

    O manifesto diz que os campos EXISTEM. Nao diz que estao POPULADOS nos
    jogos passados, e muitas APIs zeram odds antigas. Sem esta leitura, o
    escopo do #225 seria escolhido por suposicao.

    Query: ?league_id=championship&n=5
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>

    Nao devolve credencial nenhuma - so estatistica de futebol.
    """
    _require_debug_key(x_debug_key)

    from backend.config.leagues_config import LEAGUES_CONFIG
    cfg = next((l for l in LEAGUES_CONFIG if l.get("id") == league_id), None)
    if cfg is None:
        raise HTTPException(404, f"liga desconhecida: {league_id}")

    fsc = _get_fsc()
    t0 = time.time()
    season_ids = fsc.resolve_season_ids(
        cfg.get("country", ""), cfg.get("name", ""),
        alt_names=cfg.get("alt_names"), n_seasons=1,
    )
    if not season_ids:
        raise HTTPException(503, f"sem season_id para {league_id}")
    sid = season_ids[0][0]

    resp = fsc.get_all_league_matches(sid) or {}
    jogos = resp.get("data") or []

    # Só jogos finalizados: odd de jogo futuro estar preenchida nao prova nada
    # sobre o historico, que e o que o backfill vai usar.
    finalizados = [
        j for j in jogos
        if str(j.get("status", "")).lower() in ("complete", "finished", "ft")
    ]

    # #230-h: 1X2 e odds_ft_1 / odds_ft_x / odds_ft_2 na FootyStats. Os nomes
    # antigos (odds_ft_home_team_win...) NAO existem — foi por eles que esta
    # rota mediu "1X2 em 0%" e o #227 tirou o 1X2 do backfill por falta de
    # odd historica. A odd existia; o nome era nosso.
    _CAMPOS_ODDS = [
        "odds_ft_1", "odds_ft_x", "odds_ft_2",
        "odds_ft_over25", "odds_ft_over35", "odds_btts_yes",
        "odds_corners_over_85", "odds_corners_over_95",
    ]
    _CAMPOS_STATS = [
        "date_unix", "homeGoalCount", "awayGoalCount",
        "team_a_yellow_cards", "team_b_yellow_cards",
        "totalCornerCount", "team_a_corners", "team_b_corners",
    ]
    # #225-a (adendo): odd sem DESFECHO nao serve para backfill — nao da para
    # saber se o pick acertou.
    #
    # #226-b: esta lista dizia `home_team_corner_count` / `away_team_corner_count`
    # e mediu escanteios em **0/48**, do que concluimos "escanteios estao fora do
    # backfill". Errado: esses dois nomes **nao existem** na linha de partida da
    # FootyStats. Nao era campo vazio, era campo inexistente — `.get()` devolve
    # None dos dois jeitos, e a rota reportou ausencia de DADO onde havia ausencia
    # de NOME. Medido em 605 finalizadas da championship
    # (`scripts/diagnostico_chaves_escanteios.py`): `totalCornerCount`,
    # `team_a_corners` e `team_b_corners` em **100%**.
    _CAMPOS_DESFECHO = [
        "homeGoalCount", "awayGoalCount",
        "team_a_yellow_cards", "team_b_yellow_cards",
        "totalCornerCount", "team_a_corners", "team_b_corners",
    ]

    def _preenchido(v) -> bool:
        try:
            return v is not None and float(v) > 1.0
        except (TypeError, ValueError):
            return False

    # Cobertura sobre TODOS os finalizados, nao so sobre a amostra exibida:
    # cinco jogos podem mentir sobre a temporada inteira nos dois sentidos.
    cobertura = {
        c: {
            "preenchidos": sum(1 for j in finalizados if _preenchido(j.get(c))),
            "total": len(finalizados),
        }
        for c in _CAMPOS_ODDS
    }
    for c in cobertura.values():
        c["pct"] = round(100.0 * c["preenchidos"] / c["total"], 1) if c["total"] else 0.0

    def _tem_valor(v) -> bool:
        """Desfecho: 0 e valor legitimo (0 escanteios, 0 cartoes). So None nao e."""
        return v is not None

    cobertura_desfechos = {
        c: {
            "preenchidos": sum(1 for j in finalizados if _tem_valor(j.get(c))),
            "total": len(finalizados),
        }
        for c in _CAMPOS_DESFECHO
    }
    for c in cobertura_desfechos.values():
        c["pct"] = round(100.0 * c["preenchidos"] / c["total"], 1) if c["total"] else 0.0

    # #225-a (adendo): o veredito unico saia de UM campo e condenava os oito.
    # Medido em 02/09 na championship: 1X2 em 0%, mas Over 2.5, Over 3.5, BTTS e
    # os dois de escanteios em 100%. Chamar isso de "AUSENTES" mandaria o escopo
    # do #225 para o lado errado — a mesma falacia de amostra pequena que a rota
    # existia para evitar, num eixo diferente: um campo mentindo sobre oito.
    _FAMILIAS = {
        "1X2": ["odds_ft_1", "odds_ft_x", "odds_ft_2"],   # #230-h
        "gols_ou": ["odds_ft_over25", "odds_ft_over35"],
        "btts": ["odds_btts_yes"],
        "escanteios": ["odds_corners_over_85", "odds_corners_over_95"],
    }
    _DESFECHO_DA_FAMILIA = {
        "1X2": ["homeGoalCount", "awayGoalCount"],
        "gols_ou": ["homeGoalCount", "awayGoalCount"],
        "btts": ["homeGoalCount", "awayGoalCount"],
        "escanteios": ["totalCornerCount", "team_a_corners", "team_b_corners"],  # #226-b
    }

    def _min_pct(campos, fonte):
        vals = [fonte.get(c, {}).get("pct", 0.0) for c in campos]
        return min(vals) if vals else 0.0

    por_familia = {}
    for fam, campos in _FAMILIAS.items():
        odd_pct = _min_pct(campos, cobertura)
        desf_pct = _min_pct(_DESFECHO_DA_FAMILIA[fam], cobertura_desfechos)
        # Backfill de EV exige odd E desfecho. So um dos dois nao mede nada.
        if odd_pct >= 50 and desf_pct >= 50:
            estado = "prob + EV"
        elif desf_pct >= 50:
            estado = "so prob (sem odd)"
        elif odd_pct >= 50:
            estado = "INUTIL (odd sem desfecho)"
        else:
            estado = "sem dado"
        por_familia[fam] = {"odd_pct": odd_pct, "desfecho_pct": desf_pct, "backfill": estado}

    _com_ev = sorted(f for f, v in por_familia.items() if v["backfill"] == "prob + EV")
    _so_prob = sorted(f for f, v in por_familia.items() if v["backfill"] == "so prob (sem odd)")

    amostra = [
        {**{k: j.get(k) for k in _CAMPOS_STATS},
         **{k: j.get(k) for k in _CAMPOS_ODDS},
         # #225-a (adendo): a lista ordenada e cortada em 25 mostrava so as
         # chaves de 1o/2o tempo e escondia justamente as `odds_ft_*` que a rota
         # investiga. As relevantes vem primeiro agora.
         "chaves_odds_presentes": (
             sorted(k for k in j.keys()
                    if k.startswith(("odds_ft_", "odds_btts", "odds_corners")))
             + sorted(k for k in j.keys()
                      if k.startswith("odds_")
                      and not k.startswith(("odds_ft_", "odds_btts", "odds_corners")))[:15]
         )}
        for j in finalizados[:max(1, min(int(n), 20))]
    ]

    return {
        "league_id": league_id,
        "season_id": sid,
        "jogos_na_temporada": len(jogos),
        "finalizados": len(finalizados),
        "cobertura_odds": cobertura,
        "cobertura_desfechos": cobertura_desfechos,
        "por_familia": por_familia,
        "amostra": amostra,
        "veredito": (
            (f"backfill com prob + EV em: {', '.join(_com_ev)}" if _com_ev
             else "nenhuma familia tem odd E desfecho")
            + (f" | so probabilidade em: {', '.join(_so_prob)}" if _so_prob else "")
        ),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


@router.get("/odds-coverage")
def odds_coverage(
    fixture_id: int,
    league_id: str = "",
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """Per-bookmaker odds coverage report for a single fixture.

    Query: ?fixture_id=12345&league_id=mls
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>
    """
    _require_debug_key(x_debug_key)
    afc = _get_afc()
    if not afc.is_configured:
        raise HTTPException(503, "API-Football not configured")
    t0 = time.time()
    odds_response = afc.get_odds(int(fixture_id), ttl_minutes=5)
    if not odds_response:
        return {
            "fixture_id": fixture_id,
            "league_id": league_id or None,
            "total_bookmakers": 0,
            "bookmakers": [],
            "extracted": {},
            "missing": ["home", "over_25", "btts_yes"],
            "source_bookmaker": None,
            "elapsed_ms": int((time.time() - t0) * 1000),
        }

    per_bk = []
    for entry in odds_response:
        for bk in entry.get("bookmakers", []):
            bets = bk.get("bets", [])
            names = [(b.get("name") or "").lower() for b in bets]
            per_bk.append({
                "name": bk.get("name"),
                "bets_count": len(bets),
                "has_1x2": any("match winner" in n or n == "1x2" for n in names),
                "has_ou": any(
                    ("over/under" in n or "goals" in n)
                    and "corner" not in n
                    and "card" not in n
                    and "booking" not in n
                    for n in names
                ),
                "has_btts": any("both teams" in n or "btts" in n for n in names),
            })

    extracted = afc.extract_best_odds(odds_response, league_id=league_id)
    essentials = ["home", "over_25", "btts_yes"]
    missing = [k for k in essentials if k not in extracted]
    return {
        "fixture_id": fixture_id,
        "league_id": league_id or None,
        "total_bookmakers": sum(len(e.get("bookmakers", [])) for e in odds_response),
        "bookmakers": per_bk,
        "extracted": extracted,
        "missing": missing,
        "source_bookmaker": extracted.get("bookmaker"),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


@router.get("/corners-diagnostic")
def corners_diagnostic(
    league: str,
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """#170 Fase 1 — empirical diagnostic for corners model gaps.

    Uses FootyStatsClient PUBLIC methods (get_league_list, get_league_teams,
    get_league_matches). Each method is cache-backed internally (24h/6h/2h
    TTL). A fresh call happens only on expiry, which is acceptable for a
    permanent endpoint.

    Metrics:
    1A  coverage of home_advantage_attack across teams in the league
    1B  Pearson(homeAttackAdvantage, {shots, possession, xg, corners});
        redundant=true if any |r|>0.7 (multicollinearity)
    1C  Pearson(team_a_corners, team_b_corners) across finished matches;
        bivariate_potential=true if r<-0.15
    1D  empirical variance vs NB2 variance predicted using PRODUCTION
        alpha (predictor._get_alpha), not alpha fitted from the same data.
        Ratio > 1.1 → NB2 under-dispersed, < 0.9 → over-dispersed.

    Query: ?league=mls  (internal slug or alias)
    Header: X-Debug-Key: <ODDS_DEBUG_KEY>
    """
    _require_debug_key(x_debug_key)
    t0 = time.time()
    notes: List[str] = []

    from backend.config.leagues_config import LEAGUE_ID_ALIASES, get_league_config

    resolved = LEAGUE_ID_ALIASES.get(league, league)
    cfg = get_league_config(resolved)
    if not cfg:
        raise HTTPException(404, f"unknown league: {league}")

    client = _get_fsc()

    # ── Season resolution via public resolve_season_ids (cached 24h) ──
    # Reuses the same matcher the rest of the codebase uses:
    # substring match on FootyStats league name (which embeds the country),
    # chosen_only=False, cup-filter, most-recent-first. Avoids our diagnostic
    # diverging from production matching logic.
    season_id: Optional[int] = None
    try:
        season_pairs = client.resolve_season_ids(
            cfg["country"], cfg["name"],
            alt_names=cfg.get("alt_names"), n_seasons=1,
        )
    except Exception as e:
        season_pairs = []
        notes.append(f"resolve_season_ids failed: {e}")
    if season_pairs:
        season_id = int(season_pairs[0][0])

    result: dict = {
        "league_id": resolved,
        "league_name": cfg["name"],
        "season_id": season_id,
        "coverage": None,           # 1A
        "correlations": None,       # 1B
        "home_away_corr": None,     # 1C
        "nb2_dispersion": None,     # 1D
        "notes": notes,
    }

    if season_id is None:
        notes.append("No matching season found for this league in get_league_list")
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        return result

    # ── 1A + 1B: public get_league_teams (cached 6h) ──────────────────
    try:
        teams_resp = client.get_league_teams(season_id, include_stats=True)
    except Exception as e:
        teams_resp = None
        notes.append(f"get_league_teams failed: {e}")
    if not teams_resp or not teams_resp.get("data"):
        notes.append("league-teams returned no data — 1A+1B skipped")
    else:
        teams = teams_resp.get("data", []) or []
        haa_col: list = []
        shots_col: list = []
        poss_col: list = []
        xg_col: list = []
        corners_col: list = []
        total_teams = 0
        for t in teams:
            if not isinstance(t, dict):
                continue
            total_teams += 1
            stats = t.get("stats") if isinstance(t.get("stats"), dict) else t
            haa = stats.get("homeAttackAdvantage")
            if haa is None:
                haa = stats.get("homeAttackAdvantagePercentage")
            haa_col.append(haa)
            shots_col.append(
                stats.get("shotsAVG_overall")
                or stats.get("shots_per_match_overall")
                or stats.get("shotsAVG")
                or stats.get("shots_per_match")
            )
            poss_col.append(
                stats.get("possessionAVG_overall")
                or stats.get("average_possession_overall")
                or stats.get("possessionAVG")
            )
            xg_col.append(
                stats.get("xg_for_avg_overall")
                or stats.get("xgForAVG_overall")
                or stats.get("xg_for_avg")
            )
            corners_col.append(
                stats.get("cornersAVG_overall")
                or stats.get("corners_per_match_overall")
                or stats.get("cornersAVG")
            )
        with_data = sum(1 for v in haa_col if v is not None)
        coverage_pct = round(100.0 * with_data / total_teams, 1) if total_teams else 0.0
        result["coverage"] = {
            "total_teams": total_teams,
            "teams_with_data": with_data,
            "coverage_pct": coverage_pct,
        }
        corrs = {
            "shots": _pearson(haa_col, shots_col),
            "possession": _pearson(haa_col, poss_col),
            "xg": _pearson(haa_col, xg_col),
            "corners": _pearson(haa_col, corners_col),
        }
        redundant = any(c is not None and abs(c) > 0.7 for c in corrs.values())
        result["correlations"] = {"pairs": corrs, "redundant": redundant}

    # ── 1C + 1D: public get_league_matches per page (cached 2h) ───────
    pairs: List[Tuple[int, int]] = []
    pages_walked = 0
    for page in range(1, 11):
        try:
            page_resp = client.get_league_matches(season_id, page=page)
        except Exception as e:
            notes.append(f"get_league_matches page={page} failed: {e}")
            break
        if not page_resp or not page_resp.get("success"):
            break
        pages_walked += 1
        data = page_resp.get("data", []) or []
        for m in data:
            a = m.get("team_a_corners")
            b = m.get("team_b_corners")
            try:
                ai, bi = int(a), int(b)
            except (TypeError, ValueError):
                continue
            if ai < 0 or bi < 0:
                continue
            pairs.append((ai, bi))
        pager = page_resp.get("pager", {}) or {}
        if page >= pager.get("max_page", 1) or len(data) == 0:
            break

    if pages_walked == 0:
        notes.append("get_league_matches returned no pages — 1C+1D skipped")
    elif len(pairs) < 10:
        notes.append(f"only {len(pairs)} finished matches with corner data — 1C+1D skipped")
    else:
        homes = [p[0] for p in pairs]
        aways = [p[1] for p in pairs]
        totals = [p[0] + p[1] for p in pairs]
        n = len(pairs)

        # 1C — home × away correlation
        r_ha = _pearson(homes, aways)
        result["home_away_corr"] = {
            "n_matches": n,
            "correlation": r_ha,
            "bivariate_potential": r_ha is not None and r_ha < -0.15,
        }

        # 1D — empirical variance vs PRODUCTION NB2 variance.
        # Uses predictor._get_alpha (same alpha that evaluates live picks)
        # so ratio isn't tautological. alpha_empirical is also reported
        # for informational comparison.
        from backend.modeling.corners.predictor import _get_alpha
        mean_total = sum(totals) / n
        var_total = sum((v - mean_total) ** 2 for v in totals) / (n - 1) if n > 1 else 0.0
        alpha_prod = _get_alpha(resolved, mean_total)
        if var_total > mean_total and mean_total > 0:
            alpha_empirical = (var_total - mean_total) / (mean_total ** 2)
        else:
            alpha_empirical = 0.0
        nb2_var_prod = mean_total + alpha_prod * (mean_total ** 2)
        ratio = round(var_total / nb2_var_prod, 3) if nb2_var_prod > 0 else None
        result["nb2_dispersion"] = {
            "n_matches": n,
            "empirical_mean": round(mean_total, 3),
            "empirical_variance": round(var_total, 3),
            "alpha_production": round(alpha_prod, 4),
            "alpha_empirical": round(alpha_empirical, 4),
            "nb2_variance_production": round(nb2_var_prod, 3),
            "ratio_empirical_to_production": ratio,
            "note": "ratio > 1.1 → production NB2 under-dispersed; < 0.9 → over-dispersed",
        }

    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


@router.get("/corrections-audit")
def corrections_audit(
    days: int = 7,
    limit: int = 200,
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """#171 forensic — list recent corrections + current lambda_corrections per league.

    Reveals what the auto-correction cron applied during the bankroll loss
    incident on 2026-04-26/27. Filter ?days= to widen window.
    """
    _require_debug_key(x_debug_key)
    t0 = time.time()

    from backend.audit import get_recent_corrections
    from backend.config.leagues_config import LEAGUES_CONFIG
    from backend.modeling.lambda_calculator import get_lambda_corrections

    recent = get_recent_corrections(days=days, limit=limit)

    # Tag toxic-looking auto-applied lambda corrections
    toxic_threshold_low = 0.92  # any lambda deflation below this is suspect
    for c in recent:
        c["suspect"] = (
            c.get("applied_by") == "cron_auto"
            and "lambda" in (c.get("parameter") or "").lower()
            and isinstance(c.get("new_value"), (int, float))
            and c["new_value"] < toxic_threshold_low
        )

    # Snapshot current lambda corrections per league
    leagues_state = []
    for cfg in LEAGUES_CONFIG:
        lid = cfg["id"]
        try:
            corrs = get_lambda_corrections(lid)
        except Exception as e:
            leagues_state.append({"league": lid, "error": str(e)})
            continue
        leagues_state.append({
            "league": lid,
            "lambda_multiplier": (corrs.get("lambda_multiplier") or {}).get("value"),
            "btts_multiplier": (corrs.get("btts_multiplier") or {}).get("value"),
            "1x2_multiplier": (corrs.get("1x2_multiplier") or {}).get("value"),
            "corner_multiplier": (corrs.get("corner_multiplier") or {}).get("value"),
            "cards_multiplier": (corrs.get("cards_multiplier") or {}).get("value"),
            "corners_alpha": (corrs.get("corners_alpha") or {}).get("value"),
            "safe_enabled": (corrs.get("safe_enabled") or {}).get("value"),
        })

    suspects = [c for c in recent if c.get("suspect")]
    return {
        "days": days,
        "total_corrections": len(recent),
        "suspect_count": len(suspects),
        "suspects": suspects,
        "all_corrections": recent,
        "leagues_state": leagues_state,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


@router.get("/pick-outcomes")
def pick_outcomes(
    hours: int = 48,
    limit: int = 500,
    until_hours_ago: int = 0,
    x_debug_key: Optional[str] = Header(default=None, alias="X-Debug-Key"),
) -> dict:
    """#171 forensic — pick outcomes from the last N hours.

    Returns: market, league, prob_modelada, odd, ev, pick_type, result,
    stake_pct_estimated. stake_pct is estimated as Quarter-Kelly ×
    STAKE_MULTIPLIER[pick_type] — actual stake is client-side and not
    persisted. Aggregates by market and by league for triage.
    """
    _require_debug_key(x_debug_key)
    t0 = time.time()
    from datetime import datetime, timedelta
    import json as _json

    from backend.audit import init_db, _use_postgres

    # Window: [now - until_hours_ago - hours, now - until_hours_ago]
    end_ts = datetime.now() - timedelta(hours=until_hours_ago)
    start_ts = end_ts - timedelta(hours=hours)
    conn = init_db()
    cur = conn.cursor()
    ph = "%s" if _use_postgres() else "?"
    cur.execute(
        f"SELECT match_id, league, market, predicted_probs, actual_result, "
        f"pick_type, brier_score, ev, context, timestamp "
        f"FROM audit_results WHERE timestamp >= {ph} AND timestamp <= {ph} "
        f"AND actual_result IS NOT NULL "
        f"ORDER BY timestamp DESC LIMIT {ph}",
        (start_ts, end_ts, limit),
    )
    rows = cur.fetchall()
    conn.close()

    _STAKE_MULT = {"SAFE": 1.0, "SAFE*": 1.0,
                   "NEUTRO_QUALIFICADO": 0.6, "NEUTRO": 0.3}
    picks = []
    by_market: dict = {}
    by_league: dict = {}
    total_hits = 0
    total = 0
    for r in rows:
        try:
            probs_dict = _json.loads(r[3]) if isinstance(r[3], str) else (r[3] or {})
        except Exception:
            probs_dict = {}
        try:
            ctx_dict = _json.loads(r[8]) if isinstance(r[8], str) else (r[8] or {})
        except Exception:
            ctx_dict = {}

        prob = probs_dict.get("prob")
        # log_pick stores book_odd in predicted_probs, not context — check both.
        odd = (
            probs_dict.get("book_odd")
            or probs_dict.get("odd")
            or ctx_dict.get("book_odd")
            or ctx_dict.get("odd")
        )
        ev = r[7]
        pick_type = r[5] or "NEUTRO"
        result = r[4]
        is_hit = result == "hit"

        stake_pct = None
        try:
            if prob and odd and float(odd) > 1.0 and 0 < float(prob) < 1:
                kelly = max(0.0, (float(prob) * float(odd) - 1) / (float(odd) - 1))
                stake_pct = round(kelly * 0.25 * _STAKE_MULT.get(pick_type, 0.3), 5)
        except Exception:
            pass

        picks.append({
            "timestamp": r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
            "league": r[1],
            "market": r[2],
            "prob_modelada": prob,
            "odd": odd,
            "ev": ev,
            "pick_type": pick_type,
            "result": result,
            "stake_pct_estimated": stake_pct,
        })

        total += 1
        if is_hit:
            total_hits += 1

        bm_key = r[2] or "?"
        bm = by_market.setdefault(bm_key, {"total": 0, "hits": 0,
                                           "ev_sum": 0.0, "stake_sum": 0.0})
        bm["total"] += 1
        if is_hit:
            bm["hits"] += 1
        if ev is not None:
            bm["ev_sum"] += float(ev)
        if stake_pct:
            bm["stake_sum"] += stake_pct

        bl_key = r[1] or "?"
        bl = by_league.setdefault(bl_key, {"total": 0, "hits": 0,
                                           "stake_sum": 0.0})
        bl["total"] += 1
        if is_hit:
            bl["hits"] += 1
        if stake_pct:
            bl["stake_sum"] += stake_pct

    for v in by_market.values():
        v["hit_rate"] = round(v["hits"] / v["total"], 4) if v["total"] else 0
        v["ev_avg"] = round(v["ev_sum"] / v["total"], 4) if v["total"] else 0
    for v in by_league.values():
        v["hit_rate"] = round(v["hits"] / v["total"], 4) if v["total"] else 0

    return {
        "hours_back": hours,
        "total_picks": total,
        "total_hits": total_hits,
        "overall_hit_rate": round(total_hits / total, 4) if total else 0,
        "by_market": by_market,
        "by_league": by_league,
        "picks_sample": picks[:50],
        "elapsed_ms": int((time.time() - t0) * 1000),
    }
