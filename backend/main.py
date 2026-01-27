from fastapi import FastAPI, Query, HTTPException
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os
import math
import random
import importlib.util
import logging
from io import BytesIO
from backend.services.math_service import implied_probs, poisson_pmf, poisson_cdf
from backend.modeling.lambda_calculator import (
    calcular_lambda_dinamico,
    calcular_lambda_jogo,
    calcular_lambda_legado,
)
from backend.modeling.xg_filter import aplicar_filtro_completo
from backend.modeling.market_validator import (
    validar_prognostico,
    filtrar_mercados_permitidos,
)
from backend.modeling.chaos_detector import (
    detectar_caos_jogo,
)
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # fallback when pandas isn't available
try:
    import boto3  # type: ignore
except Exception:
    boto3 = None  # type: ignore
try:
    from mangum import Mangum  # type: ignore
except Exception:
    Mangum = None  # type: ignore

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sportsbank")

app = FastAPI(title="SportsBank Pro Backend", version="0.1.0")
try:
    from backend.routes import matches as _r_matches
    app.include_router(_r_matches.router)
except Exception:
    pass
try:
    from backend.routes import predictions as _r_predictions
    app.include_router(_r_predictions.router)
except Exception:
    pass
try:
    from backend.routes import health as _r_health
    app.include_router(_r_health.router)
except Exception:
    pass
try:
    from backend.routes import leagues as _r_leagues
    app.include_router(_r_leagues.router)
except Exception:
    pass
try:
    from backend.routes import fixtures as _r_fixtures
    app.include_router(_r_fixtures.router)
except Exception:
    pass
try:
    from backend.routes import decision as _r_decision
    app.include_router(_r_decision.router)
except Exception:
    pass
try:
    from backend.routes import quadro as _r_quadro
    app.include_router(_r_quadro.router)
except Exception:
    pass
try:
    from backend.routes import discover as _r_discover
    app.include_router(_r_discover.router)
except Exception:
    pass

def get_base_root() -> str:
    return os.getenv("FUTEBOL_ROOT") or os.getenv("DATA_ROOT") or r"C:\Users\wxamb\futebol"

def get_data_dir() -> str:
    return os.getenv("FUTEBOL_DATA_DIR") or os.path.join(get_base_root(), "data")

def mock_match(league_id: str, i: int) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "id": f"{league_id}-m{i}",
        "leagueId": league_id,
        "leagueName": league_id.replace("-", " ").title(),
        "homeTeam": "Team A",
        "awayTeam": "Team B",
        "datetime": now,
        "stadium": "Stadium Alpha",
        "status": "scheduled",
        "odds": { "home": 1.9, "draw": 3.4, "away": 2.2, "over25": 1.85, "under25": 1.95, "bttsYes": 1.80, "bttsNo": 2.00 },
        "stats": { "homeWinProb": 52, "drawProb": 24, "awayWinProb": 24, "avgGoals": 2.6, "bttsProb": 55, "over25Prob": 57 },
        "h2h": { "totalMatches": 5, "homeWins": 2, "draws": 1, "awayWins": 2, "avgGoals": 2.8 },
        "source": "packball",
        "lastUpdated": now,
    }

def generate_mock_fixtures(league_id: str, date_filter: str) -> List[Dict[str, Any]]:
    """Gera dados mock realistas para demonstração quando S3/CSV não estão disponíveis."""
    teams_by_league = {
        "premier-league": [
            ("Manchester City", "Wolverhampton Wanderers"),
            ("Arsenal", "Manchester United"),
            ("Liverpool", "Chelsea"),
            ("Tottenham Hotspur", "Newcastle United"),
            ("Brighton & Hove Albion", "Fulham"),
            ("West Ham United", "Sunderland"),
            ("Burnley", "AFC Bournemouth"),
            ("Brentford", "Nottingham Forest"),
            ("Crystal Palace", "Aston Villa"),
            ("Everton", "Leeds United"),
        ],
    }
    teams = teams_by_league.get(league_id, [("Team A", "Team B"), ("Team C", "Team D")])
    now = datetime.utcnow()
    start_date = now.replace(hour=12, minute=0, second=0, microsecond=0)
    fixtures = []
    for i, (home, away) in enumerate(teams[:10]):
        game_time = start_date + timedelta(hours=(i % 3) * 3)
        fixtures.append({
            "id": f"{league_id}-mock-{i}",
            "leagueId": league_id,
            "leagueName": league_id.replace("-", " ").title(),
            "homeTeam": home,
            "awayTeam": away,
            "datetime": game_time.isoformat(),
            "stadium": f"{home} Stadium",
            "status": "scheduled",
            "odds": {"home": 1.9, "draw": 3.4, "away": 2.2, "over15": 1.15, "over25": 1.85, "over35": 3.50, "over45": 7.00, "under25": 1.95, "bttsYes": 1.80, "bttsNo": 2.00},
            "stats": {"homeWinProb": 52.0, "drawProb": 24.0, "awayWinProb": 24.0, "avgGoals": 2.6, "bttsProb": 55.0, "over05Prob": 95.0, "over15Prob": 87.0, "over25Prob": 57.0, "over35Prob": 28.0, "over45Prob": 14.0, "under15Prob": 13.0, "under25Prob": 43.0, "under35Prob": 72.0, "under45Prob": 86.0, "lambdaHome": 1.4, "lambdaAway": 1.2, "lambdaTotal": 2.6, "leagueAvgGoals": 2.7, "totalGoals": None, "leagueRegime": "NORMAL", "leagueVolatility": "BAIXA", "homePossession": 52.0, "awayPossession": 48.0, "homeXG": 1.4, "awayXG": 1.2, "homeForm": ["W", "D", "W", "W", "L"], "awayForm": ["L", "W", "D", "L", "W"]}
        })
    return fixtures


def date_range(filter_type: str) -> Tuple[datetime, datetime]:
    now = datetime.utcnow()
    if filter_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(milliseconds=1)
        return start, end
    if filter_type == "tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(milliseconds=1)
        return start, end
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7) - timedelta(milliseconds=1)
    return start, end

 

def expected_goals_v2(
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any],
    league_data: Dict[str, Any],
    regime: str,
    xg_home: Optional[float] = None,
    xg_away: Optional[float] = None
) -> Tuple[float, float]:
    """
    Calcula lambda usando metodo v5.5-ML (Peso Dinamico).
    """
    lam_home, lam_away = calcular_lambda_jogo(
        home_team_data=home_team_data,
        away_team_data=away_team_data,
        league_data=league_data,
        regime=regime,
    )

    if xg_home is not None and xg_home > 0:
        lam_home = 0.7 * lam_home + 0.3 * xg_home
    if xg_away is not None and xg_away > 0:
        lam_away = 0.7 * lam_away + 0.3 * xg_away

    lam_home = max(0.2, min(4.5, lam_home))
    lam_away = max(0.2, min(4.5, lam_away))

    logger.info(
        "Lambda v5.5 | Home: %.3f | Away: %.3f | Regime: %s",
        lam_home,
        lam_away,
        regime,
    )
    return lam_home, lam_away

def expected_goals(home_attack: float, away_defense: float, away_attack: float, home_defense: float, league_avg: float, xg_home: Optional[float], xg_away: Optional[float]) -> Tuple[float, float]:
    lam_home = league_avg * home_attack * away_defense
    lam_away = league_avg * away_attack * home_defense
    if xg_home is not None and xg_home > 0:
        lam_home = 0.7 * lam_home + 0.3 * xg_home
    if xg_away is not None and xg_away > 0:
        lam_away = 0.7 * lam_away + 0.3 * xg_away
    lam_home = max(0.2, min(3.5, lam_home))
    lam_away = max(0.2, min(3.5, lam_away))
    return lam_home, lam_away

def aggregate_team_xg(players_df: Optional["pd.DataFrame"], team_name: str) -> Optional[float]:
    if players_df is None or team_name is None:
        return None
    candidates = ["team_name", "team", "club"]
    xg_cols = ["xg", "expected_goals", "xG"]
    minutes_cols = ["minutes", "mins"]
    name_col = None
    for c in candidates:
        if c in players_df.columns:
            name_col = c
            break
    if name_col is None:
        return None
    df = players_df[players_df[name_col] == team_name]
    if len(df) == 0:
        return None
    xg_col = None
    for c in xg_cols:
        if c in df.columns:
            xg_col = c
            break
    if xg_col is None:
        return None
    minutes_col = None
    for c in minutes_cols:
        if c in df.columns:
            minutes_col = c
            break
    try:
        if minutes_col:
            w = df[minutes_col].astype(float)
            xg = df[xg_col].astype(float)
            total_minutes = w.sum()
            if total_minutes <= 0:
                return float(xg.mean())
            return float((xg * w).sum() / total_minutes)
        else:
            return float(df[xg_col].astype(float).mean())
    except Exception:
        return None

 

def load_fixtures_from_csv(league_id: str, date_filter: str) -> List[Dict[str, Any]]:
    if pd is None:
        return []

    bucket = os.getenv("S3_BUCKET")
    use_s3 = bucket and boto3 is not None
    
    # Se S3 não estiver configurado, tentar usar dados locais ou retornar mock
    if use_s3:
        prefix = (os.getenv("S3_PREFIX") or "data").strip("/")
        base = f"{prefix}/{league_id}"
        s3 = boto3.client("s3")

        def s3_key_exists(key: str) -> bool:
            try:
                s3.head_object(Bucket=bucket, Key=key)
                return True
            except Exception:
                return False

        def resolve_s3_base() -> str:
            for cand in (league_id, f"PRE {league_id}"):
                key = f"{prefix}/{cand}/matches.csv"
                if s3_key_exists(key):
                    return f"{prefix}/{cand}"
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/", Delimiter="/")
                for item in resp.get("CommonPrefixes", []):
                    name = item.get("Prefix", "").replace(f"{prefix}/", "").strip("/")
                    if league_id in name and s3_key_exists(f"{prefix}/{name}/matches.csv"):
                        return f"{prefix}/{name}"
            except Exception:
                pass
            return base

        def read_csv_s3(key: str) -> Optional["pd.DataFrame"]:
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                return pd.read_csv(BytesIO(obj["Body"].read()))
            except Exception:
                return None

        def list_s3_keys(base_prefix: str) -> List[Dict[str, Any]]:
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{base_prefix}/")
                return resp.get("Contents", [])
            except Exception:
                return []

        def pick_key(items: List[Dict[str, Any]], include: List[str], exclude: Optional[List[str]] = None) -> Optional[str]:
            exclude = exclude or []
            candidates = []
            for obj in items:
                key = obj.get("Key", "")
                if not key.endswith(".csv"):
                    continue
                low = key.lower()
                if any(tok in low for tok in include) and not any(tok in low for tok in exclude):
                    candidates.append(obj)
            if not candidates:
                return None
            candidates.sort(key=lambda x: x.get("LastModified") or "")
            return candidates[-1].get("Key")

        base = resolve_s3_base()
        keys = list_s3_keys(base)
        matches_key = f"{base}/matches.csv" if s3_key_exists(f"{base}/matches.csv") else pick_key(keys, ["matches", "match"])
        teams2_key = f"{base}/teams2.csv" if s3_key_exists(f"{base}/teams2.csv") else pick_key(keys, ["teams2", "team2"])
        teams_key = f"{base}/teams.csv" if s3_key_exists(f"{base}/teams.csv") else pick_key(keys, ["teams"], exclude=["teams2", "team2"])
        league_key = f"{base}/league.csv" if s3_key_exists(f"{base}/league.csv") else pick_key(keys, ["league"])
        players_key = f"{base}/players.csv" if s3_key_exists(f"{base}/players.csv") else pick_key(keys, ["players", "player"])

        matches = read_csv_s3(matches_key) if matches_key else None
        if matches is None:
            return []
        teams = read_csv_s3(teams_key) if teams_key else None
        teams2 = read_csv_s3(teams2_key) if teams2_key else None
        league_df = read_csv_s3(league_key) if league_key else None
        players = read_csv_s3(players_key) if players_key else None
    else:
        # S3 não configurado - tentar dados locais se existirem
        base = get_data_dir()
        if not os.path.exists(base):
            # Diretório local não existe - retornar dados mock para demonstração
            logger.warning(f"S3 não configurado e diretório local {base} não existe. Retornando dados mock.")
            return generate_mock_fixtures(league_id, date_filter)
        
        league_dir = resolve_league_dir(base, league_id)
        matches_path = os.path.join(league_dir, "matches.csv")
        teams_path = os.path.join(league_dir, "teams.csv")
        teams2_path = os.path.join(league_dir, "teams2.csv")
        league_path = os.path.join(league_dir, "league.csv")
        players_path = os.path.join(league_dir, "players.csv")
        if not os.path.exists(matches_path):
            logger.warning(f"Arquivo {matches_path} não encontrado. Retornando dados mock.")
            return generate_mock_fixtures(league_id, date_filter)
        try:
            matches = pd.read_csv(matches_path)
            teams = pd.read_csv(teams_path) if os.path.exists(teams_path) else None
            teams2 = pd.read_csv(teams2_path) if os.path.exists(teams2_path) else None
            league_df = pd.read_csv(league_path) if os.path.exists(league_path) else None
            players = pd.read_csv(players_path) if os.path.exists(players_path) else None
        except Exception as e:
            logger.error(f"Erro ao ler CSVs: {e}. Retornando dados mock.")
            return generate_mock_fixtures(league_id, date_filter)
    from backend.services.fixtures_service import build_records_from_matches
    return build_records_from_matches(
        league_id=league_id,
        matches=matches,
        teams=teams,
        teams2=teams2,
        league_df=league_df,
        players=players,
        date_filter=date_filter,
    )

def load_config_module() -> Optional[Any]:
    cfg_path = os.path.join(get_base_root(), "config.py")
    if not os.path.exists(cfg_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("futebol_config", cfg_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            return mod
    except Exception:
        return None
    return None

def resolve_league_dir(base: str, league_id: str) -> str:
    direct = os.path.join(base, league_id)
    if os.path.isdir(direct):
        return direct
    mod = load_config_module()
    if mod and hasattr(mod, "LEAGUES_CONFIG"):
        conf = getattr(mod, "LEAGUES_CONFIG")
        item = conf.get(league_id)
        if item:
            # Try by code or normalized name
            code = str(item.get("code", "")).lower()
            name = str(item.get("name", "")).lower().replace(" ", "-")
            for candidate in (code, name):
                cand_dir = os.path.join(base, candidate)
                if os.path.isdir(cand_dir):
                    return cand_dir
    # fallback: first dir matching league_id substring
    for d in os.listdir(base):
        cand = os.path.join(base, d)
        if os.path.isdir(cand) and league_id in d:
            return cand
    return direct

def formatar_nome_liga(liga: str) -> str:
    mapeamento = {
        "premier-league": "INGLATERRA — PREMIER LEAGUE",
        "championship": "INGLATERRA — CHAMPIONSHIP",
        "la-liga": "ESPANHA — LA LIGA",
        "serie-a": "ITÁLIA — SERIE A",
        "bundesliga": "ALEMANHA — BUNDESLIGA",
        "ligue-1": "FRANÇA — LIGUE 1",
        "brazil-serie-a": "BRASIL — SÉRIE A",
        "brazil-serie-b": "BRASIL — SÉRIE B",
        "champions-league": "UEFA — CHAMPIONS LEAGUE",
    }
    return mapeamento.get(liga, liga.upper().replace("-", " "))

def formatar_liga_curta(liga: str) -> str:
    nome = formatar_nome_liga(liga)
    if "—" in nome:
        return nome.split("—", 1)[1].strip()
    return nome.strip()

def _normalize_prob(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v > 1.0:
        v = v / 100.0
    if v < 0:
        return None
    return min(max(v, 0.0), 1.0)

def calcular_odd_under(odd_over: float) -> Optional[float]:
    """Calcula odd Under aproximada a partir da odd Over."""
    if not odd_over or odd_over <= 1.0:
        return None
    prob_over = 1.0 / odd_over
    prob_under = 1.0 - prob_over
    if prob_under <= 0:
        return None
    return round(1.0 / prob_under, 2)

def selecionar_mercados_jogo(jogo: Dict[str, Any], regime: str, volatilidade: str) -> List[Dict[str, Any]]:
    mercados: List[Dict[str, Any]] = []
    stats = jogo.get("stats", {})
    odds = jogo.get("odds", {})
    
    # Usar dados pré-calculados do CSV (já em %)
    prob_over25 = _normalize_prob(stats.get("over25Prob"))
    prob_btts = _normalize_prob(stats.get("bttsProb"))
    prob_under35 = _normalize_prob(stats.get("under35Prob"))
    prob_under45 = _normalize_prob(stats.get("under45Prob"))
    
    # DEBUG: Log valores para diagnóstico
    home = jogo.get("homeTeam", "?")
    away = jogo.get("awayTeam", "?")
    logger.info(f"[DEBUG] {home} vs {away}:")
    logger.info(f"  under35Prob raw={stats.get('under35Prob')}, normalized={prob_under35}")
    logger.info(f"  under45Prob raw={stats.get('under45Prob')}, normalized={prob_under45}")
    logger.info(f"  regime={regime}, volatilidade={volatilidade}")
    logger.info(f"  leagueAvgGoals={stats.get('leagueAvgGoals')}")
    logger.info(f"  odds: over35={odds.get('over35')}, over45={odds.get('over45')}")
    
    prob_dc = None
    if stats.get("homeWinProb") is not None and stats.get("drawProb") is not None:
        prob_dc = _normalize_prob(float(stats.get("homeWinProb", 0)) + float(stats.get("drawProb", 0)))
    
    # Obter odds reais
    odd_over35 = odds.get("over35")
    odd_over45 = odds.get("over45")
    odd_btts_yes = odds.get("bttsYes")
    
    # Calcular odds Under
    odd_under35 = calcular_odd_under(odd_over35) if odd_over35 else None
    odd_under45 = calcular_odd_under(odd_over45) if odd_over45 else None
    
    def add_mercado(nome: str, status: str, prob: float, odd_real: Optional[float] = None, alerta: Optional[str] = None) -> None:
        prob_min = max(0, int(prob * 100) - 2)
        prob_max = max(0, int(prob * 100))
        odd_minima = round(1.0 / prob, 2) if prob > 0 else None
        odd_display = odd_real if odd_real else odd_minima
        item: Dict[str, Any] = {
            "mercado": nome,
            "status": status,
            "prob_min": prob_min,
            "prob_max": prob_max,
            "odd_minima": odd_display,
        }
        if alerta:
            item["alerta"] = alerta
        mercados.append(item)
    
    # Thresholds dinâmicos baseados na liga
    league_avg_goals = stats.get("leagueAvgGoals", 2.7)
    if league_avg_goals < 2.5:
        threshold_u35 = 0.55
        threshold_u45 = 0.65
    elif league_avg_goals < 3.0:
        threshold_u35 = 0.60
        threshold_u45 = 0.70
    else:
        threshold_u35 = 0.65
        threshold_u45 = 0.75
    
    logger.info(f"  thresholds: u35={threshold_u35}, u45={threshold_u45}")
    logger.info(f"  checks: u35({prob_under35} >= {threshold_u35})={prob_under35 >= threshold_u35 if prob_under35 else False}")
    logger.info(f"  checks: u45({prob_under45} >= {threshold_u45})={prob_under45 >= threshold_u45 if prob_under45 else False}")
    
    # Priorizar Under 3.5 sobre Under 4.5
    if regime in ["NORMAL", "DEFENSIVA"]:
        # 1º: Under 3.5 (melhor EV)
        if prob_under35 is not None and prob_under35 >= threshold_u35:
            if odd_under35 and odd_under35 >= 1.25:
                add_mercado("Under 3.5 gols", "SAFE", prob_under35, odd_under35)
            elif odd_under35 and odd_under35 >= 1.20:
                add_mercado("Under 3.5 gols", "SAFE*", prob_under35, odd_under35, alerta="Odd baixa")
            else:
                add_mercado("Under 3.5 gols", "SAFE*", prob_under35, odd_under35, alerta="Odd muito baixa")
        # 2º: Se Under 3.5 não foi adicionado, tentar Under 4.5
        elif prob_under45 is not None and prob_under45 >= threshold_u45:
            if odd_under45 and odd_under45 >= 1.15:
                add_mercado("Under 4.5 gols", "SAFE", prob_under45, odd_under45)
            elif odd_under45 and odd_under45 >= 1.10:
                add_mercado("Under 4.5 gols", "SAFE*", prob_under45, odd_under45, alerta="Odd baixa")
            else:
                add_mercado("Under 4.5 gols", "SAFE*", prob_under45, odd_under45, alerta="Odd muito baixa")
    else:  # HIPER-OFENSIVA
        if prob_over25 is not None and prob_over25 >= 0.72:
            add_mercado("Over 2.5 gols", "SAFE", prob_over25, odds.get("over25"))
    
    # BTTS
    if prob_btts is not None and prob_btts >= 0.60:
        status = "SAFE" if prob_btts >= 0.68 else "NEUTRO"
        add_mercado("BTTS — SIM", status, prob_btts, odd_btts_yes)
    
    # Double Chance
    if prob_dc is not None and prob_dc >= 0.65:
        home = str(jogo.get("homeTeam", ""))[:3].upper()
        add_mercado(f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc)
    
    # Fallback: se nenhum mercado foi adicionado
    if not mercados:
        candidatos = []
        if prob_under35:
            candidatos.append(("Under 3.5 gols", "NEUTRO", prob_under35, odd_under35))
        if prob_under45:
            candidatos.append(("Under 4.5 gols", "NEUTRO", prob_under45, odd_under45))
        if prob_over25:
            candidatos.append(("Over 2.5 gols", "NEUTRO", prob_over25, odds.get("over25")))
        if prob_btts and prob_btts >= 0.50:
            candidatos.append(("BTTS — SIM", "NEUTRO", prob_btts, odd_btts_yes))
        if prob_dc and prob_dc >= 0.60:
            home = str(jogo.get("homeTeam", ""))[:3].upper()
            candidatos.append((f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc, None))
        candidatos.sort(key=lambda x: x[2], reverse=True)
        for nome, status, prob, odd in candidatos[:3]:
            add_mercado(nome, status, prob, odd)

    def normalizar_mercado(nome: str) -> str:
        base = nome.replace(" gols", "").strip()
        if base.startswith("DC 1X"):
            return "Double Chance 1X"
        if base.startswith("DC X2"):
            return "Double Chance X2"
        if base.startswith("DC 12"):
            return "Double Chance 12"
        if base.startswith("BTTS"):
            return "BTTS"
        return base

    if mercados:
        mercados_normalizados = [normalizar_mercado(m.get("mercado", "")) for m in mercados]
        is_valid, invalidos = validar_prognostico({"markets": mercados_normalizados}, regime)
        if not is_valid:
            permitidos = filtrar_mercados_permitidos(mercados_normalizados, regime)
            mercados = [
                m for m, nome_norm in zip(mercados, mercados_normalizados)
                if nome_norm in permitidos
            ]
            logger.warning(
                "Prognóstico removido por mercados inválidos: %s | Regime: %s",
                invalidos,
                regime,
            )
        logger.info(
            "Validação de mercados | Total: %s | Válidos: %s | Removidos: %s",
            len(mercados_normalizados),
            len(mercados),
            len(mercados_normalizados) - len(mercados),
        )
    
    # Atualizar stats do jogo
    if mercados:
        principal = mercados[0]
        stats["status"] = "SAFE" if principal.get("status") == "SAFE" else principal.get("status", "NEUTRO")
        stats["mercado_principal"] = principal.get("mercado")
        stats["odd_minima"] = principal.get("odd_minima")
    
    return mercados

def identificar_duplas_safe(jogos: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    duplas: List[Dict[str, Any]] = []
    status_map = {j.get("id"): (j.get("stats", {}).get("status") or "").upper() for j in jogos}
    jogos_safe = [j for j in jogos if status_map.get(j.get("id")) in ("SAFE", "SAFE*")]
    jogos_neutro = [j for j in jogos if status_map.get(j.get("id")) in ("NEUTRO", "NEUTRAL")]
    jogos_com_mercado = [j for j in jogos if j.get("stats", {}).get("mercado_principal")]
    if jogos_safe:
        pool = jogos_safe
        modo = "SAFE"
    elif jogos_neutro:
        pool = jogos_neutro
        modo = "NEUTRO"
    elif jogos_com_mercado:
        pool = jogos_com_mercado
        modo = "QUALQUER"
    else:
        pool = []
        modo = "NENHUM"

    missing_market = 0
    missing_odd = 0
    for j in pool:
        stats = j.get("stats", {})
        if not stats.get("mercado_principal"):
            missing_market += 1
        if not stats.get("odd_minima"):
            missing_odd += 1

    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            jogo1 = pool[i]
            jogo2 = pool[j]
            mercado1 = jogo1.get("stats", {}).get("mercado_principal")
            mercado2 = jogo2.get("stats", {}).get("mercado_principal")
            if mercado1 and mercado2 and mercado1 == mercado2:
                odd1 = jogo1.get("stats", {}).get("odd_minima", 1.0) or 1.0
                odd2 = jogo2.get("stats", {}).get("odd_minima", 1.0) or 1.0
                duplas.append({
                    "jogo1": f"{jogo1.get('homeTeam')} x {jogo1.get('awayTeam')}",
                    "mercado1": mercado1,
                    "jogo2": f"{jogo2.get('homeTeam')} x {jogo2.get('awayTeam')}",
                    "mercado2": mercado2,
                    "odd_minima": round(odd1 * odd2, 2),
                })
    duplas.sort(key=lambda x: x["odd_minima"])
    motivo = {
        "modo": modo,
        "missing_market": missing_market,
        "missing_odd": missing_odd,
        "total_pool": len(pool),
    }
    return duplas[:4], motivo

def identificar_triplas_safe(jogos: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    triplas: List[Dict[str, Any]] = []
    status_map = {j.get("id"): (j.get("stats", {}).get("status") or "").upper() for j in jogos}
    jogos_safe = [j for j in jogos if status_map.get(j.get("id")) in ("SAFE", "SAFE*")]
    jogos_neutro = [j for j in jogos if status_map.get(j.get("id")) in ("NEUTRO", "NEUTRAL")]
    jogos_com_mercado = [j for j in jogos if j.get("stats", {}).get("mercado_principal")]
    if jogos_safe:
        pool = jogos_safe
        modo = "SAFE"
    elif jogos_neutro:
        pool = jogos_neutro
        modo = "NEUTRO"
    elif jogos_com_mercado:
        pool = jogos_com_mercado
        modo = "QUALQUER"
    else:
        pool = []
        modo = "NENHUM"

    missing_market = 0
    missing_odd = 0
    for j in pool:
        stats = j.get("stats", {})
        if not stats.get("mercado_principal"):
            missing_market += 1
        if not stats.get("odd_minima"):
            missing_odd += 1

    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            for k in range(j + 1, len(pool)):
                jogo1 = pool[i]
                jogo2 = pool[j]
                jogo3 = pool[k]
                mercado1 = jogo1.get("stats", {}).get("mercado_principal")
                mercado2 = jogo2.get("stats", {}).get("mercado_principal")
                mercado3 = jogo3.get("stats", {}).get("mercado_principal")
                if mercado1 and mercado2 and mercado3 and mercado1 == mercado2 == mercado3:
                    odd1 = jogo1.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    odd2 = jogo2.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    odd3 = jogo3.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    triplas.append({
                        "jogo1": f"{jogo1.get('homeTeam')} x {jogo1.get('awayTeam')}",
                        "mercado1": mercado1,
                        "jogo2": f"{jogo2.get('homeTeam')} x {jogo2.get('awayTeam')}",
                        "mercado2": mercado2,
                        "jogo3": f"{jogo3.get('homeTeam')} x {jogo3.get('awayTeam')}",
                        "mercado3": mercado3,
                        "odd_minima": round(odd1 * odd2 * odd3, 2),
                    })
    triplas.sort(key=lambda x: x["odd_minima"])
    motivo = {
        "modo": modo,
        "missing_market": missing_market,
        "missing_odd": missing_odd,
        "total_pool": len(pool),
    }
    return triplas[:3], motivo

def calcular_regime_e_volatilidade(liga: str, jogos: List[Dict[str, Any]]) -> Tuple[str, str]:
    totais = []
    league_avgs = []
    for j in jogos:
        stats = j.get("stats", {})
        total = stats.get("lambdaTotal") or stats.get("avgGoals")
        try:
            total = float(total)
        except Exception:
            total = None
        if total is not None:
            totais.append(total)
        avg_goal = stats.get("leagueAvgGoals")
        try:
            avg_goal = float(avg_goal) if avg_goal is not None else None
        except Exception:
            avg_goal = None
        if avg_goal is not None:
            league_avgs.append(avg_goal)
    media_gols = sum(league_avgs) / len(league_avgs) if league_avgs else (sum(totais) / len(totais) if totais else 0)
    regime = "HIPER-OFENSIVA" if media_gols > 3.0 else "NORMAL"
    volatilidade_base = totais if len(totais) > 1 else league_avgs
    if len(volatilidade_base) > 1:
        media = sum(volatilidade_base) / len(volatilidade_base)
        variancia = sum((g - media) ** 2 for g in volatilidade_base) / len(volatilidade_base)
        desvio = variancia ** 0.5
        if desvio < 1.0:
            volatilidade = "BAIXA"
        elif desvio < 1.5:
            volatilidade = "MODERADA"
        else:
            volatilidade = "ALTA"
    else:
        volatilidade = "MODERADA"
    return regime, volatilidade

def gerar_quadro_resumo(
    liga: str,
    jogos: List[Dict[str, Any]],
    regime: str,
    volatilidade: str,
    incluir_simples: bool = True,
    incluir_duplas: bool = True,
    incluir_triplas: bool = False,
    incluir_governanca: bool = True,
) -> str:
    linhas: List[str] = []
    sep = "═" * 67
    liga_formatada = formatar_nome_liga(liga)
    linhas.append(sep)
    linhas.append(f"{liga_formatada} | QUADRO-RESUMO PRÉ-JOGO v5.5-ML")
    linhas.append(sep)
    linhas.append("")
    mercado_ancora = "UNDER 4.5" if regime == "NORMAL" else "OVER 2.5"
    mercado_proibido = "Over 3.5 / Over 4.5" if regime == "NORMAL" else "Under 3.5 / Under 4.5"
    linhas.append(f"Regime da Liga: {regime}")
    linhas.append(f"Mercado Âncora permitido: {mercado_ancora}")
    linhas.append(f"Mercado proibido (SAFE): {mercado_proibido}")
    linhas.append(f"Volatilidade: {volatilidade}")
    linhas.append("")
    linhas.append(sep)
    linhas.append("")

    if incluir_simples:
        for jogo in jogos:
            home = jogo.get("homeTeam")
            away = jogo.get("awayTeam")
            dt = datetime.fromisoformat(jogo.get("datetime"))
            data_hora = dt.strftime("%d/%m — %H:%M")
            linhas.append(f"{home} vs {away} ({data_hora})")
            from backend.services.market_service import selecionar_mercados_jogo as _sel_merc
            mercados = _sel_merc(jogo, regime, volatilidade)
            for i, mercado in enumerate(mercados):
                simbolo = "├─" if i < len(mercados) - 1 else "└─"
                mercado_nome = str(mercado["mercado"]).ljust(20)
                status = str(mercado["status"]).ljust(8)
                prob_range = f"prob≈{mercado['prob_min']}-{mercado['prob_max']}%"
                odd_min = f"odd mín. EV+ ≈{mercado['odd_minima']}"
                linha_mercado = f"{simbolo} {mercado_nome} {status} {prob_range.ljust(16)} {odd_min}"
                if mercado.get("alerta"):
                    linha_mercado += f"  △ {mercado['alerta']}"
                linhas.append(linha_mercado)
            linhas.append("")

    if incluir_duplas:
        duplas, motivo_duplas = identificar_duplas_safe(jogos)
        if duplas:
            linhas.append(sep)
            linhas.append("")
            linhas.append("DUPLAS SAFE (v5.5 — correlação controlada)")
            if motivo_duplas.get("modo") == "NEUTRO":
                linhas.append("⚠️ Sem jogos SAFE suficientes; usando NEUTRO para combinar")
            if motivo_duplas.get("modo") == "QUALQUER":
                linhas.append("⚠️ Sem SAFE/NEUTRO; usando qualquer jogo com mercado")
            linhas.append("")
            for dupla in duplas:
                linhas.append(f"• {dupla['jogo1']} → {dupla['mercado1']}")
                linhas.append(f"  + {dupla['jogo2']} → {dupla['mercado2']}")
                linhas.append(f"  Odd mín. EV+ ≈ {dupla['odd_minima']}")
                linhas.append("")
        else:
            linhas.append(sep)
            linhas.append("")
            linhas.append("DUPLAS SAFE (v5.5 — correlação controlada)")
            linhas.append("")
            linhas.append("Nenhuma dupla gerada.")
            linhas.append(f"Motivo: modo={motivo_duplas.get('modo')}, sem mercado={motivo_duplas.get('missing_market')}, sem odd={motivo_duplas.get('missing_odd')}")
            linhas.append("")

    if incluir_triplas:
        triplas, motivo_triplas = identificar_triplas_safe(jogos)
        if triplas:
            linhas.append(sep)
            linhas.append("")
            linhas.append("TRIPLAS SAFE (v5.5 — correlação controlada)")
            if motivo_triplas.get("modo") == "NEUTRO":
                linhas.append("⚠️ Sem jogos SAFE suficientes; usando NEUTRO para combinar")
            if motivo_triplas.get("modo") == "QUALQUER":
                linhas.append("⚠️ Sem SAFE/NEUTRO; usando qualquer jogo com mercado")
            linhas.append("")
            for tripla in triplas:
                linhas.append(f"• {tripla['jogo1']} → {tripla['mercado1']}")
                linhas.append(f"  + {tripla['jogo2']} → {tripla['mercado2']}")
                linhas.append(f"  + {tripla['jogo3']} → {tripla['mercado3']}")
                linhas.append(f"  Odd mín. EV+ ≈ {tripla['odd_minima']}")
                linhas.append("")
        else:
            linhas.append(sep)
            linhas.append("")
            linhas.append("TRIPLAS SAFE (v5.5 — correlação controlada)")
            linhas.append("")
            linhas.append("Nenhuma tripla gerada.")
            linhas.append(f"Motivo: modo={motivo_triplas.get('modo')}, sem mercado={motivo_triplas.get('missing_market')}, sem odd={motivo_triplas.get('missing_odd')}")
            linhas.append("")

    if incluir_governanca:
        linhas.append(sep)
        linhas.append("")
        linhas.append("GOVERNANÇA v5.5")
        if regime == "NORMAL":
            under45_ok = 0
            for j in jogos:
                stats = j.get("stats", {})
                lam_total = stats.get("lambdaTotal")
                try:
                    lam_total = float(lam_total) if lam_total is not None else None
                except Exception:
                    lam_total = None
                prob_under45 = poisson_cdf(4, lam_total) if lam_total and lam_total > 0 else None
                if prob_under45 is not None and prob_under45 >= 0.75:
                    under45_ok += 1
            linhas.append(f"• Under 4.5 exige prob ≥ 75% → {under45_ok}/{len(jogos)} jogos atendem")
            linhas.append("• Under 3.5 rebaixado para SAFE* por EV comprometido")
            linhas.append("• Nenhum jogo classificado como CAÓTICO")
            linhas.append("• Over 3.5 / Over 4.5 → BLOQUEADOS (liga NORMAL)")
        else:
            over25_ok = 0
            for j in jogos:
                stats = j.get("stats", {})
                prob_over25 = _normalize_prob(stats.get("over25Prob"))
                if prob_over25 is not None and prob_over25 >= 0.72:
                    over25_ok += 1
            linhas.append(f"• Over 2.5 exige prob ≥ 72% → {over25_ok}/{len(jogos)} jogos atendem")
            linhas.append("• BTTS — SIM promovido para SAFE quando prob ≥ 68%")
            linhas.append(f"• Alerta: Volatilidade {volatilidade} (cautela recomendada)")
            linhas.append("• Under 3.5 / Under 4.5 → BLOQUEADOS (liga HIPER-OFENSIVA)")
        linhas.append("")
    linhas.append(sep)
    return "\n".join(linhas)

def gerar_quadro_resumo_whatsapp(
    liga: str,
    jogos: List[Dict[str, Any]],
    regime: str,
    volatilidade: str,
    incluir_simples: bool = True,
    incluir_duplas: bool = True,
) -> str:
    linhas: List[str] = []
    if not jogos:
        return "Nenhum jogo encontrado para os filtros selecionados."
    try:
        dt = datetime.fromisoformat(jogos[0].get("datetime"))
        data_ref = dt.strftime("%d/%m")
    except Exception:
        data_ref = datetime.utcnow().strftime("%d/%m")

    liga_curta = formatar_liga_curta(liga)
    linhas.append(f"{liga_curta} – {data_ref}")
    linhas.append("────────────────────────────")

    if incluir_simples:
        for jogo in jogos:
            home = jogo.get("homeTeam")
            away = jogo.get("awayTeam")
            linhas.append(f"{home} x {away}")
            mercados = selecionar_mercados_jogo(jogo, regime, volatilidade)
            if mercados:
                mercado = mercados[0]
                odd = mercado.get("odd_minima")
                odd_txt = f" @{odd}" if odd else ""
                status = mercado.get("status", "NEUTRO")
                linhas.append(f"→ {mercado.get('mercado')}{odd_txt}  [{status}]")
            else:
                linhas.append("→ Sem mercado sugerido")
            linhas.append("")

    if incluir_duplas:
        duplas, motivo_duplas = identificar_duplas_safe(jogos)
        if duplas:
            linhas.append("🔗 DUPLA SAFE SUGERIDA (intra-liga)")
            linhas.append("")
            dupla = duplas[0]
            linhas.append(f"{dupla['jogo1']} → {dupla['mercado1']}")
            linhas.append(f"{dupla['jogo2']} → {dupla['mercado2']}")
            linhas.append(f"Odd combinada ≈ {dupla['odd_minima']}")
            modo = motivo_duplas.get("modo")
            classe = "SAFE" if modo == "SAFE" else "NEUTRO"
            linhas.append(f"Classificação: {classe} (perfil conservador)")
    return "\n".join(linhas)

 

 

@app.get("/odds")
def odds(league: str) -> Dict[str, Any]:
    return {
        "league": league,
        "odds": [
            { "event": "Team A vs Team B", "home": 1.95, "draw": 3.30, "away": 2.25 },
            { "event": "Team C vs Team D", "home": 2.20, "draw": 3.10, "away": 2.75 },
        ],
    }

@app.post("/probabilities")
def probabilities(payload: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder combining Poisson/heuristics later
    return { "probs": { "homeWin": 0.52, "draw": 0.24, "awayWin": 0.24, "bttsYes": 0.55, "over25": 0.57 } }

 

@app.post("/ml/predict")
def ml_predict(payload: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder until models are trained
    return {
        "result": { "prediction": "HOME", "probability": 0.62 },
        "over_under_2_5": { "prediction": "OVER", "probability": 0.58 },
        "btts": { "prediction": "YES", "probability": 0.60 },
    }

 

if Mangum is not None:
    handler = Mangum(app)
