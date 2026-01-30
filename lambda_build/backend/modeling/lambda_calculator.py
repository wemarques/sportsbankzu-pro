"""
Módulo de Cálculo de Lambda (Taxa de Gols Esperados)

Este módulo implementa o cálculo dinâmico de lambda conforme especificação
FUT-PRÉ-JOGO v5.5-ML, aplicando ponderação adaptativa baseada no regime da liga.

ESPECIFICAÇÃO v5.5-ML:
- REGIME NORMAL:         λ = (Média_Temporada × 0.60) + (Média_Últimos5 × 0.40)
- REGIME HIPER-OFENSIVO: λ = (Média_Temporada × 0.30) + (Média_Últimos5 × 0.70)

Autor: SportsBankPro Team
Data: Janeiro 2026
Versão: 1.0 (S1 - Peso Dinâmico de Lambda)
"""

from typing import Dict, Any, Optional, Tuple
import logging

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
LAMBDA_MIN = 0.2
LAMBDA_MAX = 4.5
FATOR_DEFESA_MIN_HIPER = 0.90


def calcular_lambda_dinamico(
    team_data: Dict[str, Any],
    opponent_data: Dict[str, Any],
    league_data: Dict[str, Any],
    regime: str,
    is_home: bool
) -> float:
    """
    Calcula λ (lambda) com ponderação adaptativa ao regime da liga.
    
    Implementa a especificação v5.5-ML:
    - REGIME NORMAL:         λ = (Média_Temp × 0.60) + (Média_Ult5 × 0.40)
    - REGIME HIPER-OFENSIVO: λ = (Média_Temp × 0.30) + (Média_Ult5 × 0.70)
    
    Args:
        team_data: Dados estatísticos do time atacante
            Campos esperados:
            - goals_scored_avg_home: Média de gols em casa (temporada)
            - goals_scored_avg_away: Média de gols fora (temporada)
            - goals_scored_avg_overall: Média geral de gols (fallback)
            - goals_scored_avg_last_5: Média de gols nos últimos 5 jogos
            
        opponent_data: Dados estatísticos do adversário
            Campos esperados:
            - goals_conceded_avg_home: Média de gols sofridos em casa
            - goals_conceded_avg_away: Média de gols sofridos fora
            - goals_conceded_avg_overall: Média geral de gols sofridos (fallback)
            
        league_data: Dados estatísticos da liga
            Campos esperados:
            - average_goals_per_match: Média de gols por jogo da liga
            
        regime: Regime da liga ('NORMAL' ou 'HIPER-OFENSIVA')
        is_home: True se o time é mandante, False se visitante
    
    Returns:
        float: Lambda (taxa de gols esperados) calculado
    
    Raises:
        ValueError: Se regime inválido ou dados insuficientes
    
    Examples:
        >>> team = {
        ...     'goals_scored_avg_overall': 2.0,
        ...     'goals_scored_avg_last_5': 2.5
        ... }
        >>> opponent = {'goals_conceded_avg_overall': 1.5}
        >>> league = {'average_goals_per_match': 2.7}
        >>> calcular_lambda_dinamico(team, opponent, league, 'NORMAL', True)
        2.44...
    """
    # Validar regime
    if regime not in PESOS_LAMBDA:
        logger.warning(
            f"Regime '{regime}' inválido. Usando 'NORMAL' como fallback."
        )
        regime = 'NORMAL'
    
    # Obter pesos de ponderação
    peso_temp = PESOS_LAMBDA[regime]['temporada']
    peso_recente = PESOS_LAMBDA[regime]['ultimos5']
    
    # 1. Extrair média de gols da temporada (baseado em mando)
    if is_home:
        gols_temp = team_data.get(
            'goals_scored_avg_home',
            team_data.get('goals_scored_avg_overall', 0.0)
        )
    else:
        gols_temp = team_data.get(
            'goals_scored_avg_away',
            team_data.get('goals_scored_avg_overall', 0.0)
        )
    
    # 2. Extrair média de gols dos últimos 5 jogos
    gols_ult5 = team_data.get('goals_scored_avg_last_5', gols_temp)
    
    # Validar dados
    if gols_temp <= 0 and gols_ult5 <= 0:
        logger.error(
            f"Dados insuficientes para calcular lambda. "
            f"Team: {team_data.get('team_name', 'Unknown')}"
        )
        # Usar média da liga como fallback
        media_liga = league_data.get('average_goals_per_match', 2.5) / 2
        return max(LAMBDA_MIN, min(LAMBDA_MAX, media_liga))
    
    # 3. Calcular lambda de ataque com ponderação dinâmica
    lambda_ataque = (gols_temp * peso_temp) + (gols_ult5 * peso_recente)
    
    logger.debug(
        f"Lambda Ataque (antes ajuste defesa): {lambda_ataque:.3f} | "
        f"Gols Temp: {gols_temp:.2f} (peso {peso_temp}) | "
        f"Gols Ult5: {gols_ult5:.2f} (peso {peso_recente}) | "
        f"Regime: {regime}"
    )
    
    # 4. Ajustar pela defesa adversária
    media_liga = league_data.get('average_goals_per_match', 2.5) / 2
    
    # Defesa adversária (considerar mando oposto)
    if is_home:
        # Time casa ataca defesa visitante fora
        def_adversaria = opponent_data.get(
            'goals_conceded_avg_away',
            opponent_data.get('goals_conceded_avg_overall', media_liga)
        )
    else:
        # Time fora ataca defesa mandante em casa
        def_adversaria = opponent_data.get(
            'goals_conceded_avg_home',
            opponent_data.get('goals_conceded_avg_overall', media_liga)
        )
    
    # Fator de ajuste defensivo
    if media_liga > 0:
        fator_defesa = def_adversaria / media_liga
    else:
        fator_defesa = 1.0

    if regime == 'HIPER-OFENSIVA' and fator_defesa < FATOR_DEFESA_MIN_HIPER:
        fator_defesa = FATOR_DEFESA_MIN_HIPER
    
    # 5. Lambda final ajustado
    lambda_final = lambda_ataque * fator_defesa
    
    # 6. Aplicar limites de segurança
    lambda_final = max(LAMBDA_MIN, min(LAMBDA_MAX, lambda_final))
    
    logger.info(
        f"Lambda Final: {lambda_final:.3f} | "
        f"Ataque: {lambda_ataque:.3f} | "
        f"Fator Defesa: {fator_defesa:.3f} | "
        f"Regime: {regime} | "
        f"Mando: {'Casa' if is_home else 'Fora'}"
    )
    
    return lambda_final


def calcular_lambda_jogo(
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any],
    league_data: Dict[str, Any],
    regime: str
) -> Tuple[float, float]:
    """
    Calcula lambda para ambos os times em um jogo.
    
    Args:
        home_team_data: Dados do time mandante
        away_team_data: Dados do time visitante
        league_data: Dados da liga
        regime: Regime da liga ('NORMAL' ou 'HIPER-OFENSIVA')
    
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


# Aliases para compatibilidade
expected_goals = calcular_lambda_legado
calculate_lambda = calcular_lambda_dinamico
