"""
Módulo de Detecção de Caos

Este módulo implementa a detecção de jogos imprevisíveis ("caos") conforme
especificação FUT-PRÉ-JOGO v5.5-ML.

ESPECIFICAÇÃO v5.5-ML:
- Caos = Alta variância em xG ou resultados inconsistentes
- Threshold: Coeficiente de Variação (CV) > 30%
- Jogos em caos devem ser filtrados ou ter confiança reduzida

Autor: SportsBankPro Team
Data: Janeiro 2026
Versão: 1.0 (S4 - Detecção de Caos)
"""

from typing import Dict, List, Tuple, Optional
import logging
import math

logger = logging.getLogger(__name__)

# Constantes de Detecção de Caos
CHAOS_CV_THRESHOLD = 0.30  # 30% de Coeficiente de Variação
CHAOS_MIN_SAMPLE_SIZE = 5  # Mínimo de jogos para detectar caos
CHAOS_CONFIDENCE_PENALTY = 0.50  # Redução de 50% na confiança


def calcular_coeficiente_variacao(
    valores: List[float]
) -> float:
    """
    Calcula Coeficiente de Variação (CV = desvio_padrão / média).
    
    Args:
        valores: Lista de valores numéricos
    
    Returns:
        float: Coeficiente de Variação (0.0 a infinito)
    
    Examples:
        >>> calcular_coeficiente_variacao([1.0, 1.1, 0.9, 1.0, 1.05])
        0.08  # Baixa variação (8%)
        
        >>> calcular_coeficiente_variacao([0.5, 2.0, 0.3, 3.0, 1.0])
        0.75  # Alta variação (75%)
    """
    if len(valores) < 2:
        logger.warning("Menos de 2 valores para calcular CV. Retornando 0.")
        return 0.0
    
    # Calcular média
    media = sum(valores) / len(valores)
    
    if media == 0:
        logger.warning("Média zero. Retornando CV infinito.")
        return float('inf')
    
    # Calcular desvio padrão
    variancia = sum((x - media) ** 2 for x in valores) / len(valores)
    desvio_padrao = math.sqrt(variancia)
    
    # Coeficiente de Variação
    cv = desvio_padrao / media
    
    return cv


def detectar_caos_xg(
    xg_values: List[float],
    threshold: float = CHAOS_CV_THRESHOLD
) -> Tuple[bool, float, str]:
    """
    Detecta caos baseado em variação de xG.
    
    Args:
        xg_values: Lista de xG por jogo
        threshold: Threshold de CV para considerar caos (padrão: 0.30)
    
    Returns:
        Tuple[bool, float, str]:
            - bool: True se detectou caos
            - float: Coeficiente de Variação
            - str: Classificação ('ESTAVEL', 'MODERADO', 'CAOS')
    
    Examples:
        >>> detectar_caos_xg([1.5, 1.6, 1.4, 1.5, 1.55])
        (False, 0.05, 'ESTAVEL')
        
        >>> detectar_caos_xg([0.5, 3.0, 0.8, 2.5, 1.0])
        (True, 0.65, 'CAOS')
    """
    # Validar sample size
    if len(xg_values) < CHAOS_MIN_SAMPLE_SIZE:
        logger.debug(
            f"Sample size insuficiente ({len(xg_values)} < {CHAOS_MIN_SAMPLE_SIZE}). "
            f"Caos não detectado."
        )
        return False, 0.0, 'INSUFFICIENT_DATA'
    
    # Calcular CV
    cv = calcular_coeficiente_variacao(xg_values)
    
    # Classificar
    if cv <= threshold:
        classification = 'ESTAVEL'
        has_chaos = False
    elif cv <= threshold * 1.5:
        classification = 'MODERADO'
        has_chaos = False
    else:
        classification = 'CAOS'
        has_chaos = True
    
    logger.debug(
        f"Caos xG | CV: {cv:.2f} | Threshold: {threshold:.2f} | "
        f"Classificação: {classification} | Caos: {has_chaos}"
    )
    
    return has_chaos, cv, classification


def detectar_caos_resultados(
    goals_scored: List[int],
    threshold: float = CHAOS_CV_THRESHOLD
) -> Tuple[bool, float, str]:
    """
    Detecta caos baseado em variação de gols marcados.
    
    Args:
        goals_scored: Lista de gols por jogo
        threshold: Threshold de CV para considerar caos
    
    Returns:
        Tuple[bool, float, str]:
            - bool: True se detectou caos
            - float: Coeficiente de Variação
            - str: Classificação
    
    Examples:
        >>> detectar_caos_resultados([2, 2, 1, 2, 2])
        (False, 0.24, 'ESTAVEL')
        
        >>> detectar_caos_resultados([0, 4, 0, 5, 1])
        (True, 0.89, 'CAOS')
    """
    # Converter para float
    goals_float = [float(g) for g in goals_scored]
    
    return detectar_caos_xg(goals_float, threshold)


def detectar_caos_time(
    team_data: Dict,
    threshold: float = CHAOS_CV_THRESHOLD
) -> Tuple[bool, Dict]:
    """
    Detecta caos em dados de um time.
    
    Args:
        team_data: Dados do time (deve conter xg_per_game ou goals_per_game)
        threshold: Threshold de CV
    
    Returns:
        Tuple[bool, Dict]:
            - bool: True se detectou caos
            - Dict: Metadados da detecção
    
    Examples:
        >>> team = {'xg_per_game': [1.5, 1.6, 1.4, 1.5, 1.55]}
        >>> has_chaos, metadata = detectar_caos_time(team)
        >>> has_chaos
        False
    """
    metadata = {
        'has_chaos': False,
        'cv_xg': 0.0,
        'cv_goals': 0.0,
        'classification': 'UNKNOWN',
        'method': 'none'
    }
    
    # Tentar detectar por xG
    xg_values = team_data.get('xg_per_game', [])
    
    if len(xg_values) >= CHAOS_MIN_SAMPLE_SIZE:
        has_chaos_xg, cv_xg, classification_xg = detectar_caos_xg(xg_values, threshold)
        metadata['cv_xg'] = cv_xg
        metadata['classification'] = classification_xg
        metadata['method'] = 'xg'
        
        if has_chaos_xg:
            metadata['has_chaos'] = True
            logger.info(
                f"Caos detectado por xG | CV: {cv_xg:.2f} | "
                f"Classificação: {classification_xg}"
            )
            return True, metadata
    
    # Tentar detectar por gols
    goals_values = team_data.get('goals_per_game', [])
    
    if len(goals_values) >= CHAOS_MIN_SAMPLE_SIZE:
        has_chaos_goals, cv_goals, classification_goals = detectar_caos_resultados(
            goals_values, threshold
        )
        metadata['cv_goals'] = cv_goals
        
        if metadata['method'] == 'none':
            metadata['classification'] = classification_goals
            metadata['method'] = 'goals'
        
        if has_chaos_goals:
            metadata['has_chaos'] = True
            logger.info(
                f"Caos detectado por gols | CV: {cv_goals:.2f} | "
                f"Classificação: {classification_goals}"
            )
            return True, metadata
    
    # Sem caos detectado
    logger.debug(f"Caos não detectado | Método: {metadata['method']}")
    return False, metadata


def detectar_caos_jogo(
    home_team_data: Dict,
    away_team_data: Dict,
    threshold: float = CHAOS_CV_THRESHOLD
) -> Tuple[bool, Dict]:
    """
    Detecta caos em um jogo (ambos os times).
    
    Args:
        home_team_data: Dados do mandante
        away_team_data: Dados do visitante
        threshold: Threshold de CV
    
    Returns:
        Tuple[bool, Dict]:
            - bool: True se detectou caos em qualquer time
            - Dict: Metadados combinados
    
    Examples:
        >>> home = {'xg_per_game': [1.5, 1.5, 1.5]}
        >>> away = {'xg_per_game': [0.5, 3.0, 0.8, 2.5, 1.0]}
        >>> has_chaos, metadata = detectar_caos_jogo(home, away)
        >>> has_chaos
        True  # Away tem caos
    """
    # Detectar caos no mandante
    has_chaos_home, metadata_home = detectar_caos_time(home_team_data, threshold)
    
    # Detectar caos no visitante
    has_chaos_away, metadata_away = detectar_caos_time(away_team_data, threshold)
    
    # Combinar metadados
    combined_metadata = {
        'home': metadata_home,
        'away': metadata_away,
        'any_chaos': has_chaos_home or has_chaos_away,
        'both_chaos': has_chaos_home and has_chaos_away
    }
    
    if combined_metadata['any_chaos']:
        logger.warning(
            f"Caos detectado no jogo | "
            f"Home: {has_chaos_home} | Away: {has_chaos_away}"
        )
    
    return combined_metadata['any_chaos'], combined_metadata


def aplicar_penalidade_confianca(
    confidence: float,
    has_chaos: bool,
    penalty: float = CHAOS_CONFIDENCE_PENALTY
) -> float:
    """
    Aplica penalidade na confiança se caos detectado.
    
    Args:
        confidence: Confiança original (0.0 a 1.0)
        has_chaos: Se caos foi detectado
        penalty: Fator de penalidade (padrão: 0.50 = -50%)
    
    Returns:
        float: Confiança ajustada
    
    Examples:
        >>> aplicar_penalidade_confianca(0.80, False)
        0.80  # Sem caos, mantém
        
        >>> aplicar_penalidade_confianca(0.80, True)
        0.40  # Com caos, reduz 50%
    """
    if not has_chaos:
        return confidence
    
    confidence_adjusted = confidence * (1 - penalty)
    
    logger.info(
        f"Penalidade de caos aplicada | "
        f"Confiança: {confidence:.2f} → {confidence_adjusted:.2f} | "
        f"Redução: -{penalty*100:.0f}%"
    )
    
    return confidence_adjusted


def filtrar_jogos_caos(
    jogos: List[Dict],
    threshold: float = CHAOS_CV_THRESHOLD,
    remove_chaos: bool = True
) -> Tuple[List[Dict], int]:
    """
    Filtra jogos com caos detectado.
    
    Args:
        jogos: Lista de jogos
        threshold: Threshold de CV
        remove_chaos: Se True, remove jogos com caos (padrão: True)
    
    Returns:
        Tuple[List[Dict], int]:
            - List[Dict]: Jogos filtrados
            - int: Número de jogos removidos
    
    Examples:
        >>> jogos = [
        ...     {'home': {...}, 'away': {...}},  # Sem caos
        ...     {'home': {...}, 'away': {...}}   # Com caos
        ... ]
        >>> filtrados, removidos = filtrar_jogos_caos(jogos)
        >>> len(filtrados)
        1
        >>> removidos
        1
    """
    filtrados = []
    removidos = 0
    
    for jogo in jogos:
        home_data = jogo.get('home_team_data', jogo.get('home', {}))
        away_data = jogo.get('away_team_data', jogo.get('away', {}))
        
        has_chaos, metadata = detectar_caos_jogo(home_data, away_data, threshold)
        
        if has_chaos:
            removidos += 1
            if not remove_chaos:
                # Adicionar flag de caos
                jogo['_has_chaos'] = True
                jogo['_chaos_metadata'] = metadata
                filtrados.append(jogo)
        else:
            filtrados.append(jogo)
    
    logger.info(
        f"Filtro de caos | Total: {len(jogos)} | "
        f"Filtrados: {len(filtrados)} | Removidos: {removidos}"
    )
    
    return filtrados, removidos


def obter_info_caos() -> Dict:
    """
    Retorna informações sobre detecção de caos.
    
    Returns:
        Dict com thresholds e configurações
    
    Examples:
        >>> info = obter_info_caos()
        >>> info['threshold']
        0.30
    """
    return {
        'cv_threshold': CHAOS_CV_THRESHOLD,
        'min_sample_size': CHAOS_MIN_SAMPLE_SIZE,
        'confidence_penalty': CHAOS_CONFIDENCE_PENALTY
    }


def validar_dados_caos(
    team_data: Dict,
    team_name: str = "Unknown"
) -> bool:
    """
    Valida se os dados do time contêm campos necessários para detecção de caos.
    
    Args:
        team_data: Dados do time
        team_name: Nome do time (para logging)
    
    Returns:
        bool: True se válido, False caso contrário
    """
    # Verificar se tem xg_per_game ou goals_per_game
    has_xg = 'xg_per_game' in team_data and team_data['xg_per_game']
    has_goals = 'goals_per_game' in team_data and team_data['goals_per_game']
    
    if not has_xg and not has_goals:
        logger.warning(
            f"Time {team_name} não tem dados de xg_per_game ou goals_per_game. "
            f"Detecção de caos não será aplicada."
        )
        return False
    
    return True


# Aliases para compatibilidade
calculate_coefficient_of_variation = calcular_coeficiente_variacao
detect_chaos_xg = detectar_caos_xg
detect_chaos_match = detectar_caos_jogo
apply_chaos_penalty = aplicar_penalidade_confianca
filter_chaos_matches = filtrar_jogos_caos
