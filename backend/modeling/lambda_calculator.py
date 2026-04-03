"""
Módulo de Cálculo de Lambda (Taxa de Gols Esperados)

Calcula lambda usando modelo de forças relativas (Dixon-Coles):
  λ = media_liga_per_team × ataque_relativo × defesa_relativa_adversario

Ponderação adaptativa por regime:
  NORMAL:         gols = (Temporada × 0.60) + (Últimos5 × 0.40)
  HIPER-OFENSIVO: gols = (Temporada × 0.30) + (Últimos5 × 0.70)

Correções por liga via audit DB (REGRAS #052).
"""

from typing import Dict, Any, Optional, Tuple, List
import logging
import math

logger = logging.getLogger(__name__)

# Constantes de Ponderação por Regime
PESOS_LAMBDA = {
    'NORMAL': {
        'temporada': 0.60,
        'ultimos5': 0.40
    },
    'HIPER-OFENSIVA': {
        'temporada': 0.30,
        'ultimos5': 0.70
    }
}

# Limites de Lambda (segurança)
LAMBDA_MIN = 0.5  # #063: no real team scores < 0.5 goals/game on average
LAMBDA_MAX = 4.5
FATOR_DEFESA_MIN_HIPER = 0.90


def _get_home_advantage_gamma(league_id: str) -> float:
    """Get calibrated home advantage γ for a league from corrections DB.

    γ is an adjustment factor on top of the implicit home advantage already
    present in home-specific stats. Default 1.0 = no extra adjustment.

    Returns float in [0.85, 1.25] range.
    """
    try:
        corrections = get_lambda_corrections(league_id)
        gamma_corr = corrections.get("home_advantage_gamma")
        if gamma_corr:
            val = float(gamma_corr.get("value", 1.0))
            return max(0.85, min(1.25, val))
    except Exception:
        pass
    return 1.0


def weighted_average_with_decay(values: List[float], half_life_games: float = 20.0) -> float:
    """Exponential decay weighted average (Dixon-Coles temporal weighting).

    More recent values (later indices) get higher weight.
    Utility for future use when per-game data becomes available (Bloco 2).

    Args:
        values: list of values (oldest first, most recent last)
        half_life_games: half-life in games — after this many games, weight = 0.5

    Returns:
        Weighted average, or simple mean if values is empty or half_life is very large.
    """
    if not values:
        return 0.0
    n = len(values)
    if half_life_games <= 0 or half_life_games > 1e6:
        return sum(values) / n

    phi = math.exp(-math.log(2) / half_life_games)
    total_w = 0.0
    total_v = 0.0
    for i, v in enumerate(values):
        # i=0 is oldest, i=n-1 is most recent
        age = n - 1 - i
        w = phi ** age
        total_w += w
        total_v += w * v

    return total_v / total_w if total_w > 0 else sum(values) / n


def half_life_to_weights(half_life_games: float, matches_played: int) -> Tuple[float, float]:
    """Map a half-life parameter to (season_weight, recent_weight) split.

    This provides a bridge between Dixon-Coles temporal decay and the
    existing season/recent weight system used in calcular_lambda_dinamico.

    Args:
        half_life_games: half-life in number of games
        matches_played: total matches played in the season so far

    Returns:
        (season_weight, recent_weight) tuple summing to 1.0.
        Larger half-life → more season weight (data decays slowly).
        Smaller half-life → more recent weight (recent data dominates).
    """
    if matches_played <= 0 or half_life_games <= 0:
        return (0.50, 0.50)

    # Ratio: what fraction of a full season does the half-life cover?
    ratio = half_life_games / max(matches_played, 1)
    # Clamp ratio to [0, 1] range
    ratio = max(0.0, min(1.0, ratio))

    # Map: ratio close to 1.0 → season_weight ≈ 0.70 (slow decay, trust full season)
    #       ratio close to 0.0 → season_weight ≈ 0.30 (fast decay, trust recent)
    season_weight = 0.30 + 0.40 * ratio
    recent_weight = 1.0 - season_weight

    return (round(season_weight, 2), round(recent_weight, 2))


def calcular_lambda_dinamico(
    team_data: Dict[str, Any],
    opponent_data: Dict[str, Any],
    league_data: Dict[str, Any],
    regime: str,
    is_home: bool
) -> float:
    """
    Calcula λ (lambda) usando modelo de forças relativas (Dixon-Coles).

    Fórmula:
        λ = media_liga_per_team × ataque_relativo × defesa_relativa_adversario

    Onde:
        media_liga_per_team = average_goals_per_match / 2
        ataque_relativo = gols_marcados / media_liga_per_team (ponderado por regime)
        defesa_relativa = gols_sofridos_adversario / media_liga_per_team

    Isso elimina a dupla contagem do fator defensivo presente na versão anterior (#053).
    """
    if regime not in PESOS_LAMBDA:
        regime = 'NORMAL'

    peso_temp = PESOS_LAMBDA[regime]['temporada']
    peso_recente = PESOS_LAMBDA[regime]['ultimos5']

    # Liga baseline
    media_liga = league_data.get('average_goals_per_match', 2.5)
    media_liga_per_team = media_liga / 2.0

    if media_liga_per_team <= 0:
        media_liga_per_team = 1.25  # fallback

    # 1. Média de gols do time (temporada, home/away específico)
    if is_home:
        gols_temp = team_data.get('goals_scored_avg_home',
                   team_data.get('goals_scored_avg_overall', media_liga_per_team))
    else:
        gols_temp = team_data.get('goals_scored_avg_away',
                   team_data.get('goals_scored_avg_overall', media_liga_per_team))

    # 2. Últimos 5 jogos
    gols_ult5 = team_data.get('goals_scored_avg_last_5', gols_temp)

    # Fallback
    if gols_temp <= 0 and gols_ult5 <= 0:
        return max(LAMBDA_MIN, min(LAMBDA_MAX, media_liga_per_team))

    # 3. Ataque ponderado — EMA (#108) replaces hardcoded 60/40
    # HIPER-OFENSIVA: shorter half-life (3) = more weight on recent form
    # NORMAL: standard half-life (5)
    try:
        from backend.modeling.ema_weights import ema_from_averages
        _hl = 3.0 if regime == "HIPER-OFENSIVA" else 5.0
        ataque_ponderado = ema_from_averages(
            season_avg=gols_temp,
            last_n_avg=gols_ult5,
            n_recent=5,
            n_season=15,
            half_life=_hl,
        )
        # Safety log: warn if diff > 15% vs old method
        _old = gols_temp * peso_temp + gols_ult5 * peso_recente
        if _old > 0 and abs(ataque_ponderado - _old) / _old > 0.15:
            logger.warning(
                f"[EMA] diff>15%: old={_old:.3f}, ema={ataque_ponderado:.3f}, "
                f"gols_temp={gols_temp:.2f}, gols_ult5={gols_ult5:.2f}"
            )
    except Exception:
        ataque_ponderado = (gols_temp * peso_temp) + (gols_ult5 * peso_recente)

    # 3b. Early season regression to mean (#064)
    # When team has < 5 games, regress attack toward league average
    # to avoid extreme lambdas from insufficient data.
    games_played = team_data.get('games_played')
    if games_played is not None:
        try:
            gp = float(games_played)
            if gp < 5:
                # regress = current season weight: 0.0 = 100% league avg, 1.0 = 100% team data
                regress = gp / 5.0
                ataque_ponderado = ataque_ponderado * regress + media_liga_per_team * (1 - regress)
                logger.info(
                    f"[lambda-regress] Early season regression: gp={gp}, "
                    f"regress_weight={regress:.2f}, ataque_adj={ataque_ponderado:.3f}"
                )
        except (ValueError, TypeError):
            pass

    # 4. FORÇA RELATIVA de ataque (ratio vs liga)
    ataque_relativo = ataque_ponderado / media_liga_per_team

    # 5. Defesa adversária - força relativa
    if is_home:
        def_adversaria = opponent_data.get('goals_conceded_avg_away',
                        opponent_data.get('goals_conceded_avg_overall', media_liga_per_team))
    else:
        def_adversaria = opponent_data.get('goals_conceded_avg_home',
                        opponent_data.get('goals_conceded_avg_overall', media_liga_per_team))

    defesa_relativa = def_adversaria / media_liga_per_team if media_liga_per_team > 0 else 1.0

    # Piso para regime hiper-ofensivo
    if regime == 'HIPER-OFENSIVA' and defesa_relativa < FATOR_DEFESA_MIN_HIPER:
        defesa_relativa = FATOR_DEFESA_MIN_HIPER

    # 6. Lambda final = baseline × ataque_relativo × defesa_relativa
    lambda_final = media_liga_per_team * ataque_relativo * defesa_relativa

    # Limites de segurança
    lambda_final = max(LAMBDA_MIN, min(LAMBDA_MAX, lambda_final))

    logger.info(
        f"Lambda Final: {lambda_final:.3f} | "
        f"Ataque Rel: {ataque_relativo:.3f} | "
        f"Defesa Rel: {defesa_relativa:.3f} | "
        f"Base Liga: {media_liga_per_team:.3f} | "
        f"Regime: {regime} | "
        f"Mando: {'Casa' if is_home else 'Fora'}"
    )

    return lambda_final


def calcular_lambda_jogo(
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any],
    league_data: Dict[str, Any],
    regime: str,
    league_id: str = "",
) -> Tuple[float, float]:
    """
    Calcula lambda para ambos os times em um jogo.

    Args:
        home_team_data: Dados do time mandante
        away_team_data: Dados do time visitante
        league_data: Dados da liga
        regime: Regime da liga ('NORMAL' ou 'HIPER-OFENSIVA')
        league_id: ID da liga (opcional). Quando fornecido, aplica correções de
            lambda armazenadas no DB de auditoria (Gap 2 — feedback loop).

    Returns:
        Tuple[float, float]: (lambda_home, lambda_away)

    Examples:
        >>> home = {
        ...     'goals_scored_avg_home': 2.0,
        ...     'goals_scored_avg_last_5': 2.5
        ... }
        >>> away = {
        ...     'goals_scored_avg_away': 1.5,
        ...     'goals_scored_avg_last_5': 1.8
        ... }
        >>> league = {'average_goals_per_match': 2.7}
        >>> calcular_lambda_jogo(home, away, league, 'NORMAL')
        (2.2, 1.65)
    """
    # Lambda do time mandante
    lambda_home = calcular_lambda_dinamico(
        team_data=home_team_data,
        opponent_data=away_team_data,
        league_data=league_data,
        regime=regime,
        is_home=True
    )

    # Lambda do time visitante
    lambda_away = calcular_lambda_dinamico(
        team_data=away_team_data,
        opponent_data=home_team_data,
        league_data=league_data,
        regime=regime,
        is_home=False
    )

    # Apply home advantage γ (#078 — Dixon-Coles explicit home factor)
    if league_id:
        gamma = _get_home_advantage_gamma(league_id)
        if gamma != 1.0:
            lambda_home = max(LAMBDA_MIN, min(LAMBDA_MAX, lambda_home * gamma))
            logger.info(f"[DC-γ] Home advantage γ={gamma:.3f} applied → λH={lambda_home:.3f}")

    # Apply audit corrections from DB (Gap 2)
    if league_id:
        try:
            corrections = get_lambda_corrections(league_id)
            if corr := corrections.get("lambda_home_multiplier"):
                mult = float(corr.get("value", 1.0))
                lambda_home = max(LAMBDA_MIN, min(LAMBDA_MAX, lambda_home * mult))
                logger.info(f"[Gap2] lambda_home correction applied: ×{mult:.3f} → {lambda_home:.3f}")
            if corr := corrections.get("lambda_away_multiplier"):
                mult = float(corr.get("value", 1.0))
                lambda_away = max(LAMBDA_MIN, min(LAMBDA_MAX, lambda_away * mult))
                logger.info(f"[Gap2] lambda_away correction applied: ×{mult:.3f} → {lambda_away:.3f}")
        except Exception as e:
            logger.debug(f"[Gap2] Lambda corrections skipped for {league_id}: {e}")

    return lambda_home, lambda_away


def calcular_lambda_legado(
    home_attack: float,
    away_defense: float,
    away_attack: float,
    home_defense: float,
    league_avg: float
) -> Tuple[float, float]:
    """
    Calcula lambda usando método legado (compatibilidade com código antigo).
    
    NOTA: Esta função mantém compatibilidade com o código existente.
    Para novos desenvolvimentos, use calcular_lambda_dinamico().
    
    Args:
        home_attack: Força de ataque do mandante (relativa)
        away_defense: Força de defesa do visitante (relativa)
        away_attack: Força de ataque do visitante (relativa)
        home_defense: Força de defesa do mandante (relativa)
        league_avg: Média de gols da liga
    
    Returns:
        Tuple[float, float]: (lambda_home, lambda_away)
    """
    lam_home = league_avg * home_attack * away_defense
    lam_away = league_avg * away_attack * home_defense
    
    # Aplicar limites
    lam_home = max(LAMBDA_MIN, min(LAMBDA_MAX, lam_home))
    lam_away = max(LAMBDA_MIN, min(LAMBDA_MAX, lam_away))
    
    logger.debug(
        f"Lambda Legado | Home: {lam_home:.3f} | Away: {lam_away:.3f}"
    )
    
    return lam_home, lam_away


def validar_dados_time(team_data: Dict[str, Any], team_name: str = "Unknown") -> bool:
    """
    Valida se os dados do time contêm campos mínimos necessários.
    
    Args:
        team_data: Dados do time
        team_name: Nome do time (para logging)
    
    Returns:
        bool: True se válido, False caso contrário
    """
    campos_obrigatorios = [
        'goals_scored_avg_overall',
        'goals_conceded_avg_overall'
    ]
    
    for campo in campos_obrigatorios:
        if campo not in team_data:
            logger.warning(
                f"Campo obrigatório '{campo}' ausente nos dados de {team_name}"
            )
            return False
        
        if team_data[campo] is None:
            logger.warning(
                f"Campo '{campo}' é None nos dados de {team_name}"
            )
            return False
    
    return True


def obter_info_ponderacao(regime: str) -> Dict[str, float]:
    """
    Retorna informações de ponderação para um regime.
    
    Args:
        regime: Regime da liga
    
    Returns:
        Dict com pesos de temporada e últimos 5 jogos
    
    Examples:
        >>> obter_info_ponderacao('NORMAL')
        {'temporada': 0.6, 'ultimos5': 0.4}
    """
    return PESOS_LAMBDA.get(regime, PESOS_LAMBDA['NORMAL']).copy()


def get_lambda_corrections(league: str) -> Dict[str, Any]:
    """
    Fetch active lambda/weight corrections from the audit corrections table.

    Returns a dict keyed by parameter_name with the corrected value.
    These can be applied as multipliers or weight overrides in calcular_lambda_dinamico().
    """
    try:
        from backend.audit import get_active_corrections
        return get_active_corrections(league)
    except Exception as e:
        logger.warning(f"Could not load lambda corrections for {league}: {e}")
        return {}


# Aliases para compatibilidade
expected_goals = calcular_lambda_legado
calculate_lambda = calcular_lambda_dinamico
