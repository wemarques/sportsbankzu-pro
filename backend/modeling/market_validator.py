"""
Módulo de Validação de Mercados Proibidos

Este módulo implementa a validação de mercados conforme regime da liga,
seguindo especificação FUT-PRÉ-JOGO v5.5-ML.

ESPECIFICAÇÃO v5.5-ML:
- NORMAL: Proibido Over 3.5, Over 4.5
- DEFENSIVA: Proibido Over 2.5, Over 3.5, Over 4.5
- HIPER-OFENSIVA: Todos permitidos

Autor: SportsBankPro Team
Data: Janeiro 2026
Versão: 1.0 (S3 - Validação de Mercados)
"""

from typing import Dict, List, Set, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Mercados proibidos por regime (v5.5-ML)
MERCADOS_PROIBIDOS: Dict[str, List[str]] = {
    'NORMAL': ['Over 3.5', 'Over 4.5'],
    'DEFENSIVA': ['Over 2.5', 'Over 3.5', 'Over 4.5', 'BTTS'],
    'HIPER-OFENSIVA': []  # Todos permitidos
}

# Todos os mercados possíveis
MERCADOS_VALIDOS: List[str] = [
    'Over 0.5', 'Over 1.5', 'Over 2.5', 'Over 3.5', 'Over 4.5',
    'Under 0.5', 'Under 1.5', 'Under 2.5', 'Under 3.5', 'Under 4.5',
    'BTTS', 'BTTS No',
    '1X2 Home', '1X2 Draw', '1X2 Away',
    'Double Chance 1X', 'Double Chance 12', 'Double Chance X2'
]


def validar_mercado(
    market: str,
    regime: str
) -> Tuple[bool, str]:
    """
    Valida se um mercado é permitido para o regime da liga.
    
    Args:
        market: Nome do mercado (ex: 'Over 2.5', 'BTTS')
        regime: Regime da liga ('NORMAL', 'DEFENSIVA', 'HIPER-OFENSIVA')
    
    Returns:
        Tuple[bool, str]:
            - bool: True se permitido, False se proibido
            - str: Motivo (se proibido) ou 'OK' (se permitido)
    
    Examples:
        >>> validar_mercado('Over 2.5', 'NORMAL')
        (True, 'OK')
        
        >>> validar_mercado('Over 3.5', 'NORMAL')
        (False, 'Mercado proibido para regime NORMAL')
    """
    # Normalizar regime
    regime = regime.upper()
    
    # Validar regime
    if regime not in MERCADOS_PROIBIDOS:
        logger.warning(f"Regime desconhecido: {regime}. Assumindo NORMAL.")
        regime = 'NORMAL'
    
    # Verificar se mercado é válido
    if market not in MERCADOS_VALIDOS:
        return False, f"Mercado inválido: {market}"
    
    # Verificar se mercado está proibido
    proibidos = MERCADOS_PROIBIDOS[regime]
    
    if market in proibidos:
        logger.warning(
            f"Mercado '{market}' PROIBIDO para regime {regime}. "
            f"Mercados proibidos: {proibidos}"
        )
        return False, f"Mercado proibido para regime {regime}"
    
    logger.debug(f"Mercado '{market}' PERMITIDO para regime {regime}")
    return True, 'OK'


def validar_mercados_lista(
    markets: List[str],
    regime: str
) -> Dict[str, Tuple[bool, str]]:
    """
    Valida uma lista de mercados para o regime.
    
    Args:
        markets: Lista de mercados
        regime: Regime da liga
    
    Returns:
        Dict com resultado de validação para cada mercado
    
    Examples:
        >>> validar_mercados_lista(['Over 2.5', 'Over 3.5'], 'NORMAL')
        {'Over 2.5': (True, 'OK'), 'Over 3.5': (False, 'Mercado proibido...')}
    """
    resultados = {}
    
    for market in markets:
        is_valid, reason = validar_mercado(market, regime)
        resultados[market] = (is_valid, reason)
    
    return resultados


def filtrar_mercados_permitidos(
    markets: List[str],
    regime: str
) -> List[str]:
    """
    Filtra lista de mercados, retornando apenas os permitidos.
    
    Args:
        markets: Lista de mercados
        regime: Regime da liga
    
    Returns:
        Lista de mercados permitidos
    
    Examples:
        >>> filtrar_mercados_permitidos(['Over 2.5', 'Over 3.5'], 'NORMAL')
        ['Over 2.5']
    """
    permitidos = []
    
    for market in markets:
        is_valid, _ = validar_mercado(market, regime)
        if is_valid:
            permitidos.append(market)
    
    logger.info(
        f"Filtro de mercados | Regime: {regime} | "
        f"Total: {len(markets)} | Permitidos: {len(permitidos)} | "
        f"Removidos: {len(markets) - len(permitidos)}"
    )
    
    return permitidos


def obter_mercados_permitidos(regime: str) -> List[str]:
    """
    Retorna lista de todos os mercados permitidos para o regime.
    
    Args:
        regime: Regime da liga
    
    Returns:
        Lista de mercados permitidos
    
    Examples:
        >>> obter_mercados_permitidos('NORMAL')
        ['Over 0.5', 'Over 1.5', 'Over 2.5', 'Under 0.5', ...]
    """
    regime = regime.upper()
    
    if regime not in MERCADOS_PROIBIDOS:
        logger.warning(f"Regime desconhecido: {regime}. Assumindo NORMAL.")
        regime = 'NORMAL'
    
    proibidos = set(MERCADOS_PROIBIDOS[regime])
    permitidos = [m for m in MERCADOS_VALIDOS if m not in proibidos]
    
    return permitidos


def obter_mercados_proibidos(regime: str) -> List[str]:
    """
    Retorna lista de mercados proibidos para o regime.
    
    Args:
        regime: Regime da liga
    
    Returns:
        Lista de mercados proibidos
    
    Examples:
        >>> obter_mercados_proibidos('NORMAL')
        ['Over 3.5', 'Over 4.5']
    """
    regime = regime.upper()
    
    if regime not in MERCADOS_PROIBIDOS:
        logger.warning(f"Regime desconhecido: {regime}. Assumindo NORMAL.")
        regime = 'NORMAL'
    
    return MERCADOS_PROIBIDOS[regime]


def validar_prognostico(
    prognostico: Dict,
    regime: str
) -> Tuple[bool, List[str]]:
    """
    Valida um prognóstico completo, verificando todos os mercados sugeridos.
    
    Args:
        prognostico: Dict com prognóstico (deve conter 'markets' ou 'picks')
        regime: Regime da liga
    
    Returns:
        Tuple[bool, List[str]]:
            - bool: True se todos mercados válidos, False se algum inválido
            - List[str]: Lista de mercados inválidos (vazia se todos válidos)
    
    Examples:
        >>> prog = {'markets': ['Over 2.5', 'Over 3.5']}
        >>> validar_prognostico(prog, 'NORMAL')
        (False, ['Over 3.5'])
    """
    # Extrair mercados do prognóstico
    if 'markets' in prognostico:
        markets = prognostico.get('markets', [])
    elif 'picks' in prognostico:
        markets = prognostico.get('picks', [])
    elif 'market' in prognostico:
        markets = [prognostico.get('market')]
    else:
        markets = []
    
    if not markets:
        logger.warning("Prognóstico sem mercados para validar")
        return True, []
    
    # Validar cada mercado
    invalidos = []
    
    for market in markets:
        # Se market é dict, extrair nome
        if isinstance(market, dict):
            market_name = market.get('market', market.get('name', ''))
        else:
            market_name = market
        
        is_valid, reason = validar_mercado(market_name, regime)
        
        if not is_valid:
            invalidos.append(market_name)
            logger.warning(
                f"Prognóstico contém mercado inválido: {market_name} | "
                f"Regime: {regime} | Motivo: {reason}"
            )
    
    is_valid = len(invalidos) == 0
    
    if is_valid:
        logger.debug(f"Prognóstico válido para regime {regime}")
    else:
        logger.error(
            f"Prognóstico INVÁLIDO para regime {regime}. "
            f"Mercados inválidos: {invalidos}"
        )
    
    return is_valid, invalidos


def aplicar_validacao_mercados(
    prognosticos: List[Dict],
    regime: str,
    remove_invalid: bool = True
) -> Tuple[List[Dict], int]:
    """
    Aplica validação de mercados em lista de prognósticos.
    
    Args:
        prognosticos: Lista de prognósticos
        regime: Regime da liga
        remove_invalid: Se True, remove prognósticos inválidos (padrão: True)
    
    Returns:
        Tuple[List[Dict], int]:
            - List[Dict]: Prognósticos válidos
            - int: Número de prognósticos removidos
    
    Examples:
        >>> progs = [
        ...     {'market': 'Over 2.5', 'prob': 0.65},
        ...     {'market': 'Over 3.5', 'prob': 0.45}
        ... ]
        >>> validados, removidos = aplicar_validacao_mercados(progs, 'NORMAL')
        >>> len(validados)
        1
        >>> removidos
        1
    """
    validos = []
    removidos = 0
    
    for prog in prognosticos:
        is_valid, invalidos = validar_prognostico(prog, regime)
        
        if is_valid:
            validos.append(prog)
        else:
            removidos += 1
            if not remove_invalid:
                # Adicionar flag de inválido
                prog['_invalid'] = True
                prog['_invalid_markets'] = invalidos
                validos.append(prog)
    
    logger.info(
        f"Validação de mercados | Regime: {regime} | "
        f"Total: {len(prognosticos)} | Válidos: {len(validos)} | "
        f"Removidos: {removidos}"
    )
    
    return validos, removidos


def obter_info_validacao() -> Dict:
    """
    Retorna informações sobre regras de validação.
    
    Returns:
        Dict com mercados proibidos por regime
    
    Examples:
        >>> info = obter_info_validacao()
        >>> info['NORMAL']
        ['Over 3.5', 'Over 4.5']
    """
    return {
        'mercados_proibidos': MERCADOS_PROIBIDOS.copy(),
        'mercados_validos': MERCADOS_VALIDOS.copy(),
        'regimes_suportados': list(MERCADOS_PROIBIDOS.keys())
    }


# Aliases para compatibilidade
validate_market = validar_mercado
filter_allowed_markets = filtrar_mercados_permitidos
get_allowed_markets = obter_mercados_permitidos
get_forbidden_markets = obter_mercados_proibidos
validate_prediction = validar_prognostico
