"""
Módulo de Filtro de Mentira (xG Adjustment)

Este módulo implementa a detecção de times com "sorte insustentável" conforme
especificação FUT-PRÉ-JOGO v5.5-ML, ajustando lambda quando há discrepância
significativa entre gols marcados e xG (Expected Goals).

ESPECIFICAÇÃO v5.5-ML:
- Se (gols_marcados - xG) > THRESHOLD: Time está com "sorte"
- Ajustar lambda para baixo para corrigir viés otimista
- THRESHOLD padrão: 0.50 gols

Autor: SportsBankPro Team
Data: Janeiro 2026
Versão: 1.0 (S2 - Filtro de Mentira)
"""

from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Constantes do Filtro de Mentira
XG_DISCREPANCY_THRESHOLD = 0.50  # Gols acima do xG para considerar "sorte"
XG_ADJUSTMENT_FACTOR = 0.15      # Percentual de ajuste (15% de redução)
XG_MIN_SAMPLE_SIZE = 5           # Mínimo de jogos para aplicar filtro


def detectar_sorte_insustentavel(
    goals_scored: float,
    xg: float,
    games_played: int,
    threshold: float = XG_DISCREPANCY_THRESHOLD
) -> Tuple[bool, float, str]:
    """
    Detecta se um time está com sorte insustentável (gols >> xG).
    
    Args:
        goals_scored: Total de gols marcados
        xg: Total de xG (Expected Goals)
        games_played: Número de jogos disputados
        threshold: Threshold de discrepância (padrão: 0.50)
    
    Returns:
        Tuple[bool, float, str]:
            - bool: True se detectou sorte insustentável
            - float: Discrepância (gols - xG)
            - str: Classificação ('NORMAL', 'SORTE_LEVE', 'SORTE_ALTA')
    
    Examples:
        >>> detectar_sorte_insustentavel(20, 15, 10)
        (True, 5.0, 'SORTE_ALTA')
        
        >>> detectar_sorte_insustentavel(18, 17.5, 10)
        (False, 0.5, 'NORMAL')
    """
    # Validar dados
    if games_played < XG_MIN_SAMPLE_SIZE:
        logger.debug(
            f"Sample size insuficiente ({games_played} < {XG_MIN_SAMPLE_SIZE}). "
            f"Filtro não aplicado."
        )
        return False, 0.0, 'INSUFFICIENT_DATA'
    
    if xg <= 0:
        logger.warning(f"xG inválido ({xg}). Filtro não aplicado.")
        return False, 0.0, 'INVALID_XG'
    
    # Calcular discrepância
    discrepancy = goals_scored - xg
    
    # Classificar
    if discrepancy <= threshold:
        classification = 'NORMAL'
        has_luck = False
    elif discrepancy <= threshold * 2:
        classification = 'SORTE_LEVE'
        has_luck = True
    else:
        classification = 'SORTE_ALTA'
        has_luck = True
    
    logger.debug(
        f"Sorte Detectada: {has_luck} | "
        f"Gols: {goals_scored:.1f} | xG: {xg:.1f} | "
        f"Discrepância: {discrepancy:.2f} | "
        f"Classificação: {classification}"
    )
    
    return has_luck, discrepancy, classification


def ajustar_lambda_por_xg(
    lambda_original: float,
    goals_scored: float,
    xg: float,
    games_played: int,
    adjustment_factor: float = XG_ADJUSTMENT_FACTOR
) -> Tuple[float, bool, Dict[str, Any]]:
    """
    Ajusta lambda quando detecta sorte insustentável.
    
    Args:
        lambda_original: Lambda calculado originalmente
        goals_scored: Total de gols marcados
        xg: Total de xG
        games_played: Número de jogos
        adjustment_factor: Fator de ajuste (padrão: 0.15 = 15%)
    
    Returns:
        Tuple[float, bool, Dict]:
            - float: Lambda ajustado
            - bool: True se ajuste foi aplicado
            - Dict: Metadados do ajuste
    
    Examples:
        >>> ajustar_lambda_por_xg(2.5, 20, 15, 10)
        (2.125, True, {...})
        
        >>> ajustar_lambda_por_xg(2.5, 18, 17.5, 10)
        (2.5, False, {...})
    """
    # Detectar sorte
    has_luck, discrepancy, classification = detectar_sorte_insustentavel(
        goals_scored, xg, games_played
    )
    
    # Preparar metadados
    metadata = {
        'has_luck': has_luck,
        'discrepancy': discrepancy,
        'classification': classification,
        'adjustment_applied': False,
        'adjustment_factor': 0.0,
        'lambda_original': lambda_original,
        'lambda_adjusted': lambda_original
    }
    
    # Se não detectou sorte, retornar lambda original
    if not has_luck:
        logger.debug(f"Sem sorte detectada. Lambda mantido: {lambda_original:.3f}")
        return lambda_original, False, metadata
    
    # Calcular ajuste
    # Quanto maior a discrepância, maior o ajuste (até o limite do adjustment_factor).
    # Usa uma escala mais ampla para manter proporcionalidade entre "sorte leve" e "sorte alta".
    max_discrepancy = XG_DISCREPANCY_THRESHOLD * 10
    discrepancy_ratio = min(discrepancy / max_discrepancy, 1.0)
    effective_adjustment = adjustment_factor * discrepancy_ratio
    
    # Aplicar ajuste (reduzir lambda)
    lambda_adjusted = lambda_original * (1 - effective_adjustment)
    
    # Atualizar metadados
    metadata['adjustment_applied'] = True
    metadata['adjustment_factor'] = effective_adjustment
    metadata['lambda_adjusted'] = lambda_adjusted
    
    logger.info(
        f"Filtro de Mentira Aplicado | "
        f"Lambda: {lambda_original:.3f} → {lambda_adjusted:.3f} | "
        f"Ajuste: -{effective_adjustment*100:.1f}% | "
        f"Discrepância: {discrepancy:.2f} | "
        f"Classificação: {classification}"
    )
    
    return lambda_adjusted, True, metadata


def ajustar_lambda_jogo_por_xg(
    lambda_home: float,
    lambda_away: float,
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any]
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Ajusta lambdas de ambos os times em um jogo considerando xG.
    
    Args:
        lambda_home: Lambda do time mandante
        lambda_away: Lambda do time visitante
        home_team_data: Dados do mandante (deve conter goals_scored, xg, games_played)
        away_team_data: Dados do visitante (deve conter goals_scored, xg, games_played)
    
    Returns:
        Tuple[float, float, Dict]:
            - float: Lambda home ajustado
            - float: Lambda away ajustado
            - Dict: Metadados combinados
    
    Examples:
        >>> home = {'goals_scored': 20, 'xg': 15, 'games_played': 10}
        >>> away = {'goals_scored': 18, 'xg': 17.5, 'games_played': 10}
        >>> ajustar_lambda_jogo_por_xg(2.5, 2.0, home, away)
        (2.125, 2.0, {...})
    """
    # Extrair dados do mandante
    home_goals = home_team_data.get('goals_scored', 0)
    home_xg = home_team_data.get('xg', 0)
    home_games = home_team_data.get('games_played', 0)
    
    # Extrair dados do visitante
    away_goals = away_team_data.get('goals_scored', 0)
    away_xg = away_team_data.get('xg', 0)
    away_games = away_team_data.get('games_played', 0)
    
    # Ajustar lambda home
    lambda_home_adj, home_adjusted, home_meta = ajustar_lambda_por_xg(
        lambda_home, home_goals, home_xg, home_games
    )
    
    # Ajustar lambda away
    lambda_away_adj, away_adjusted, away_meta = ajustar_lambda_por_xg(
        lambda_away, away_goals, away_xg, away_games
    )
    
    # Combinar metadados
    combined_metadata = {
        'home': home_meta,
        'away': away_meta,
        'any_adjustment': home_adjusted or away_adjusted
    }
    
    logger.info(
        f"Filtro xG Jogo | "
        f"Home: {lambda_home:.3f} → {lambda_home_adj:.3f} ({'ajustado' if home_adjusted else 'mantido'}) | "
        f"Away: {lambda_away:.3f} → {lambda_away_adj:.3f} ({'ajustado' if away_adjusted else 'mantido'})"
    )
    
    return lambda_home_adj, lambda_away_adj, combined_metadata


def calcular_xg_medio(
    xg_total: float,
    games_played: int
) -> float:
    """
    Calcula xG médio por jogo.
    
    Args:
        xg_total: xG total acumulado
        games_played: Número de jogos
    
    Returns:
        float: xG médio por jogo
    
    Examples:
        >>> calcular_xg_medio(15.5, 10)
        1.55
    """
    if games_played <= 0:
        logger.warning(f"games_played inválido ({games_played}). Retornando 0.")
        return 0.0
    
    return xg_total / games_played


def validar_dados_xg(
    team_data: Dict[str, Any],
    team_name: str = "Unknown"
) -> bool:
    """
    Valida se os dados do time contêm campos necessários para filtro xG.
    
    Args:
        team_data: Dados do time
        team_name: Nome do time (para logging)
    
    Returns:
        bool: True se válido, False caso contrário
    """
    campos_obrigatorios = ['goals_scored', 'xg', 'games_played']
    
    for campo in campos_obrigatorios:
        if campo not in team_data:
            logger.warning(
                f"Campo '{campo}' ausente nos dados de {team_name}. "
                f"Filtro xG não será aplicado."
            )
            return False
        
        if team_data[campo] is None:
            logger.warning(
                f"Campo '{campo}' é None nos dados de {team_name}. "
                f"Filtro xG não será aplicado."
            )
            return False
    
    return True


def obter_info_filtro() -> Dict[str, Any]:
    """
    Retorna informações de configuração do filtro xG.
    
    Returns:
        Dict com thresholds e fatores
    
    Examples:
        >>> obter_info_filtro()
        {'threshold': 0.5, 'adjustment_factor': 0.15, 'min_sample': 5}
    """
    return {
        'threshold': XG_DISCREPANCY_THRESHOLD,
        'adjustment_factor': XG_ADJUSTMENT_FACTOR,
        'min_sample_size': XG_MIN_SAMPLE_SIZE
    }


def aplicar_filtro_completo(
    lambda_home: float,
    lambda_away: float,
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any],
    enable_filter: bool = True
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Aplica filtro de mentira completo com validações.
    
    Esta é a função principal que deve ser chamada no backend.
    
    Args:
        lambda_home: Lambda do mandante
        lambda_away: Lambda do visitante
        home_team_data: Dados do mandante
        away_team_data: Dados do visitante
        enable_filter: Se False, retorna lambdas originais (padrão: True)
    
    Returns:
        Tuple[float, float, Dict]:
            - float: Lambda home (ajustado ou original)
            - float: Lambda away (ajustado ou original)
            - Dict: Metadados completos
    
    Examples:
        >>> home = {'goals_scored': 20, 'xg': 15, 'games_played': 10}
        >>> away = {'goals_scored': 18, 'xg': 17.5, 'games_played': 10}
        >>> aplicar_filtro_completo(2.5, 2.0, home, away)
        (2.125, 2.0, {...})
    """
    # Se filtro desabilitado, retornar originais
    if not enable_filter:
        logger.debug("Filtro xG desabilitado. Lambdas mantidos.")
        return lambda_home, lambda_away, {'filter_enabled': False}
    
    # Validar dados
    home_valid = validar_dados_xg(home_team_data, home_team_data.get('team_name', 'Home'))
    away_valid = validar_dados_xg(away_team_data, away_team_data.get('team_name', 'Away'))
    
    if not home_valid and not away_valid:
        logger.warning("Dados xG inválidos para ambos os times. Filtro não aplicado.")
        return lambda_home, lambda_away, {'filter_enabled': True, 'data_valid': False}
    
    # Aplicar filtro
    lambda_home_adj, lambda_away_adj, metadata = ajustar_lambda_jogo_por_xg(
        lambda_home, lambda_away, home_team_data, away_team_data
    )
    
    metadata['filter_enabled'] = True
    metadata['data_valid'] = True
    
    return lambda_home_adj, lambda_away_adj, metadata


# Aliases para compatibilidade
adjust_lambda_by_xg = ajustar_lambda_por_xg
detect_unsustainable_luck = detectar_sorte_insustentavel
apply_xg_filter = aplicar_filtro_completo
