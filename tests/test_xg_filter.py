"""
Testes Unitários para xG Filter (S2)

Testa a implementação do Filtro de Mentira conforme especificação v5.5-ML.

Cobertura:
- Detecção de sorte insustentável
- Ajuste de lambda por xG
- Validação de dados
- Casos extremos e fallbacks
- Integração com lambda_calculator

Autor: SportsBankPro Team
Data: Janeiro 2026
"""

import pytest
from backend.modeling.xg_filter import (
    detectar_sorte_insustentavel,
    ajustar_lambda_por_xg,
    ajustar_lambda_jogo_por_xg,
    calcular_xg_medio,
    validar_dados_xg,
    obter_info_filtro,
    aplicar_filtro_completo,
    XG_DISCREPANCY_THRESHOLD,
    XG_ADJUSTMENT_FACTOR,
    XG_MIN_SAMPLE_SIZE
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def team_com_sorte():
    """Time com sorte alta (gols >> xG)."""
    return {
        'team_name': 'Lucky FC',
        'goals_scored': 20.0,
        'xg': 15.0,
        'games_played': 10
    }


@pytest.fixture
def team_sem_sorte():
    """Time sem sorte (gols ≈ xG)."""
    return {
        'team_name': 'Normal FC',
        'goals_scored': 18.0,
        'xg': 17.5,
        'games_played': 10
    }


@pytest.fixture
def team_azar():
    """Time com azar (gols < xG)."""
    return {
        'team_name': 'Unlucky FC',
        'goals_scored': 12.0,
        'xg': 18.0,
        'games_played': 10
    }


@pytest.fixture
def team_dados_insuficientes():
    """Time com poucos jogos."""
    return {
        'team_name': 'New FC',
        'goals_scored': 5.0,
        'xg': 3.0,
        'games_played': 3  # Menos que XG_MIN_SAMPLE_SIZE
    }


# ============================================================================
# TESTES: Detecção de Sorte
# ============================================================================

class TestDeteccaoSorte:
    """Testa detecção de sorte insustentável."""
    
    def test_detecta_sorte_alta(self, team_com_sorte):
        """Deve detectar sorte quando gols >> xG."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=team_com_sorte['goals_scored'],
            xg=team_com_sorte['xg'],
            games_played=team_com_sorte['games_played']
        )
        
        assert has_luck is True, "Deveria detectar sorte"
        assert discrepancy == 5.0, f"Discrepância deveria ser 5.0, obtido: {discrepancy}"
        assert classification == 'SORTE_ALTA', f"Classificação deveria ser SORTE_ALTA, obtido: {classification}"
    
    def test_nao_detecta_sorte_normal(self, team_sem_sorte):
        """Não deve detectar sorte quando gols ≈ xG."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=team_sem_sorte['goals_scored'],
            xg=team_sem_sorte['xg'],
            games_played=team_sem_sorte['games_played']
        )
        
        assert has_luck is False, "Não deveria detectar sorte"
        assert discrepancy == 0.5, f"Discrepância deveria ser 0.5, obtido: {discrepancy}"
        assert classification == 'NORMAL', f"Classificação deveria ser NORMAL, obtido: {classification}"
    
    def test_nao_detecta_azar(self, team_azar):
        """Não deve detectar sorte quando gols < xG (azar)."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=team_azar['goals_scored'],
            xg=team_azar['xg'],
            games_played=team_azar['games_played']
        )
        
        assert has_luck is False, "Não deveria detectar sorte (é azar)"
        assert discrepancy < 0, "Discrepância deveria ser negativa"
        assert classification == 'NORMAL', f"Classificação deveria ser NORMAL, obtido: {classification}"
    
    def test_sorte_leve(self):
        """Deve detectar sorte leve quando discrepância moderada."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=18.0,
            xg=17.0,
            games_played=10,
            threshold=0.50
        )
        
        # Discrepância = 1.0, threshold = 0.50
        # 0.50 < 1.0 <= 1.00 (threshold * 2)
        assert has_luck is True, "Deveria detectar sorte leve"
        assert classification == 'SORTE_LEVE', f"Classificação deveria ser SORTE_LEVE, obtido: {classification}"
    
    def test_dados_insuficientes(self, team_dados_insuficientes):
        """Não deve aplicar filtro com poucos jogos."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=team_dados_insuficientes['goals_scored'],
            xg=team_dados_insuficientes['xg'],
            games_played=team_dados_insuficientes['games_played']
        )
        
        assert has_luck is False, "Não deveria detectar sorte (dados insuficientes)"
        assert classification == 'INSUFFICIENT_DATA', f"Classificação deveria ser INSUFFICIENT_DATA, obtido: {classification}"


# ============================================================================
# TESTES: Ajuste de Lambda
# ============================================================================

class TestAjusteLambda:
    """Testa ajuste de lambda por xG."""
    
    def test_ajusta_lambda_com_sorte(self, team_com_sorte):
        """Deve reduzir lambda quando detecta sorte."""
        lambda_original = 2.5
        
        lambda_adj, adjusted, metadata = ajustar_lambda_por_xg(
            lambda_original=lambda_original,
            goals_scored=team_com_sorte['goals_scored'],
            xg=team_com_sorte['xg'],
            games_played=team_com_sorte['games_played']
        )
        
        assert adjusted is True, "Ajuste deveria ter sido aplicado"
        assert lambda_adj < lambda_original, f"Lambda ajustado ({lambda_adj:.3f}) deveria ser < original ({lambda_original:.3f})"
        assert metadata['adjustment_applied'] is True
        assert metadata['has_luck'] is True
        assert metadata['classification'] == 'SORTE_ALTA'
    
    def test_nao_ajusta_lambda_sem_sorte(self, team_sem_sorte):
        """Não deve ajustar lambda quando não detecta sorte."""
        lambda_original = 2.5
        
        lambda_adj, adjusted, metadata = ajustar_lambda_por_xg(
            lambda_original=lambda_original,
            goals_scored=team_sem_sorte['goals_scored'],
            xg=team_sem_sorte['xg'],
            games_played=team_sem_sorte['games_played']
        )
        
        assert adjusted is False, "Ajuste não deveria ter sido aplicado"
        assert lambda_adj == lambda_original, f"Lambda deveria ser mantido: {lambda_original:.3f}"
        assert metadata['adjustment_applied'] is False
        assert metadata['has_luck'] is False
    
    def test_ajuste_proporcional_discrepancia(self):
        """Ajuste deve ser proporcional à discrepância."""
        lambda_original = 2.0
        
        # Sorte moderada (discrepância = 1.0)
        lambda_mod, _, meta_mod = ajustar_lambda_por_xg(
            lambda_original, goals_scored=18.0, xg=17.0, games_played=10
        )
        
        # Sorte alta (discrepância = 5.0)
        lambda_alta, _, meta_alta = ajustar_lambda_por_xg(
            lambda_original, goals_scored=20.0, xg=15.0, games_played=10
        )
        
        # Ajuste em sorte alta deve ser maior
        ajuste_mod = lambda_original - lambda_mod
        ajuste_alta = lambda_original - lambda_alta
        
        assert ajuste_alta > ajuste_mod, \
            f"Ajuste em sorte alta ({ajuste_alta:.3f}) deveria ser > sorte moderada ({ajuste_mod:.3f})"


# ============================================================================
# TESTES: Ajuste de Jogo Completo
# ============================================================================

class TestAjusteJogo:
    """Testa ajuste de lambda para ambos os times."""
    
    def test_ajusta_apenas_time_com_sorte(self, team_com_sorte, team_sem_sorte):
        """Deve ajustar apenas o time com sorte."""
        lambda_home = 2.5
        lambda_away = 2.0
        
        lambda_h_adj, lambda_a_adj, metadata = ajustar_lambda_jogo_por_xg(
            lambda_home, lambda_away, team_com_sorte, team_sem_sorte
        )
        
        # Home tem sorte, deve ser ajustado
        assert lambda_h_adj < lambda_home, "Lambda home deveria ser reduzido"
        assert metadata['home']['adjustment_applied'] is True
        
        # Away não tem sorte, deve ser mantido
        assert lambda_a_adj == lambda_away, "Lambda away deveria ser mantido"
        assert metadata['away']['adjustment_applied'] is False
        
        # Pelo menos um ajuste foi aplicado
        assert metadata['any_adjustment'] is True
    
    def test_ajusta_ambos_times_com_sorte(self):
        """Deve ajustar ambos os times se ambos têm sorte."""
        team_home_sorte = {
            'goals_scored': 20.0,
            'xg': 15.0,
            'games_played': 10
        }
        
        team_away_sorte = {
            'goals_scored': 19.0,
            'xg': 14.0,
            'games_played': 10
        }
        
        lambda_home = 2.5
        lambda_away = 2.3
        
        lambda_h_adj, lambda_a_adj, metadata = ajustar_lambda_jogo_por_xg(
            lambda_home, lambda_away, team_home_sorte, team_away_sorte
        )
        
        # Ambos devem ser ajustados
        assert lambda_h_adj < lambda_home, "Lambda home deveria ser reduzido"
        assert lambda_a_adj < lambda_away, "Lambda away deveria ser reduzido"
        assert metadata['any_adjustment'] is True
    
    def test_nao_ajusta_nenhum_time_sem_sorte(self, team_sem_sorte):
        """Não deve ajustar se nenhum time tem sorte."""
        lambda_home = 2.5
        lambda_away = 2.0
        
        lambda_h_adj, lambda_a_adj, metadata = ajustar_lambda_jogo_por_xg(
            lambda_home, lambda_away, team_sem_sorte, team_sem_sorte
        )
        
        assert lambda_h_adj == lambda_home, "Lambda home deveria ser mantido"
        assert lambda_a_adj == lambda_away, "Lambda away deveria ser mantido"
        assert metadata['any_adjustment'] is False


# ============================================================================
# TESTES: Validação de Dados
# ============================================================================

class TestValidacaoDados:
    """Testa validação de dados xG."""
    
    def test_dados_validos(self, team_com_sorte):
        """Dados completos devem passar na validação."""
        assert validar_dados_xg(team_com_sorte, "Lucky FC") is True
    
    def test_dados_campo_faltando(self):
        """Dados sem campo obrigatório devem falhar."""
        team_invalido = {
            'team_name': 'Invalid FC',
            'goals_scored': 20.0
            # Falta xg e games_played
        }
        assert validar_dados_xg(team_invalido, "Invalid FC") is False
    
    def test_dados_campo_none(self):
        """Dados com campo None devem falhar."""
        team_invalido = {
            'team_name': 'Invalid FC',
            'goals_scored': None,
            'xg': 15.0,
            'games_played': 10
        }
        assert validar_dados_xg(team_invalido, "Invalid FC") is False


# ============================================================================
# TESTES: Funções Auxiliares
# ============================================================================

class TestFuncoesAuxiliares:
    """Testa funções auxiliares do módulo."""
    
    def test_calcular_xg_medio(self):
        """Deve calcular xG médio corretamente."""
        xg_medio = calcular_xg_medio(15.5, 10)
        assert abs(xg_medio - 1.55) < 0.01, f"xG médio deveria ser 1.55, obtido: {xg_medio}"
    
    def test_calcular_xg_medio_zero_jogos(self):
        """Deve retornar 0 quando games_played = 0."""
        xg_medio = calcular_xg_medio(15.5, 0)
        assert xg_medio == 0.0, f"xG médio deveria ser 0.0, obtido: {xg_medio}"
    
    def test_obter_info_filtro(self):
        """Deve retornar configurações do filtro."""
        info = obter_info_filtro()
        
        assert info['threshold'] == XG_DISCREPANCY_THRESHOLD
        assert info['adjustment_factor'] == XG_ADJUSTMENT_FACTOR
        assert info['min_sample_size'] == XG_MIN_SAMPLE_SIZE


# ============================================================================
# TESTES: Filtro Completo
# ============================================================================

class TestFiltroCompleto:
    """Testa função de filtro completo."""
    
    def test_filtro_habilitado(self, team_com_sorte, team_sem_sorte):
        """Filtro habilitado deve aplicar ajustes."""
        lambda_home = 2.5
        lambda_away = 2.0
        
        lambda_h_adj, lambda_a_adj, metadata = aplicar_filtro_completo(
            lambda_home, lambda_away, team_com_sorte, team_sem_sorte, enable_filter=True
        )
        
        assert metadata['filter_enabled'] is True
        assert lambda_h_adj < lambda_home, "Lambda home deveria ser ajustado"
    
    def test_filtro_desabilitado(self, team_com_sorte, team_sem_sorte):
        """Filtro desabilitado não deve aplicar ajustes."""
        lambda_home = 2.5
        lambda_away = 2.0
        
        lambda_h_adj, lambda_a_adj, metadata = aplicar_filtro_completo(
            lambda_home, lambda_away, team_com_sorte, team_sem_sorte, enable_filter=False
        )
        
        assert metadata['filter_enabled'] is False
        assert lambda_h_adj == lambda_home, "Lambda home deveria ser mantido"
        assert lambda_a_adj == lambda_away, "Lambda away deveria ser mantido"
    
    def test_filtro_dados_invalidos(self):
        """Filtro com dados inválidos não deve aplicar ajustes."""
        team_invalido = {
            'team_name': 'Invalid FC',
            'goals_scored': None,
            'xg': None,
            'games_played': None
        }
        
        lambda_home = 2.5
        lambda_away = 2.0
        
        lambda_h_adj, lambda_a_adj, metadata = aplicar_filtro_completo(
            lambda_home, lambda_away, team_invalido, team_invalido, enable_filter=True
        )
        
        assert metadata['filter_enabled'] is True
        assert metadata['data_valid'] is False
        assert lambda_h_adj == lambda_home, "Lambda home deveria ser mantido"
        assert lambda_a_adj == lambda_away, "Lambda away deveria ser mantido"


# ============================================================================
# TESTES: Casos Reais
# ============================================================================

class TestCasosReais:
    """Testa com dados realistas."""
    
    def test_arsenal_2023_sorte_alta(self):
        """
        Arsenal 2022/23 início: 20 gols em 10 jogos, xG ~15.
        Deveria detectar sorte e ajustar lambda.
        """
        arsenal = {
            'team_name': 'Arsenal',
            'goals_scored': 20.0,
            'xg': 15.2,
            'games_played': 10
        }
        
        lambda_original = 2.0
        
        lambda_adj, adjusted, metadata = ajustar_lambda_por_xg(
            lambda_original,
            arsenal['goals_scored'],
            arsenal['xg'],
            arsenal['games_played']
        )
        
        assert adjusted is True, "Arsenal deveria ter ajuste aplicado"
        assert lambda_adj < lambda_original, f"Lambda deveria ser reduzido: {lambda_original} → {lambda_adj}"
        assert 1.6 < lambda_adj < 1.9, f"Lambda ajustado deveria estar entre 1.6 e 1.9, obtido: {lambda_adj}"
    
    def test_manchester_city_2023_normal(self):
        """
        Manchester City 2022/23: gols ≈ xG (eficiência normal).
        Não deveria ajustar lambda.
        """
        city = {
            'team_name': 'Manchester City',
            'goals_scored': 25.0,
            'xg': 24.8,
            'games_played': 10
        }
        
        lambda_original = 2.5
        
        lambda_adj, adjusted, metadata = ajustar_lambda_por_xg(
            lambda_original,
            city['goals_scored'],
            city['xg'],
            city['games_played']
        )
        
        assert adjusted is False, "City não deveria ter ajuste aplicado"
        assert lambda_adj == lambda_original, f"Lambda deveria ser mantido: {lambda_original}"
    
    def test_jogo_realista_completo(self):
        """
        Jogo realista: Arsenal (sorte) vs City (normal).
        """
        arsenal = {
            'team_name': 'Arsenal',
            'goals_scored': 20.0,
            'xg': 15.2,
            'games_played': 10
        }
        
        city = {
            'team_name': 'Manchester City',
            'goals_scored': 25.0,
            'xg': 24.8,
            'games_played': 10
        }
        
        lambda_home = 2.0  # Arsenal
        lambda_away = 2.5  # City
        
        lambda_h_adj, lambda_a_adj, metadata = aplicar_filtro_completo(
            lambda_home, lambda_away, arsenal, city
        )
        
        # Arsenal deve ser ajustado
        assert lambda_h_adj < lambda_home, "Lambda Arsenal deveria ser reduzido"
        
        # City deve ser mantido
        assert lambda_a_adj == lambda_away, "Lambda City deveria ser mantido"
        
        # Metadados
        assert metadata['home']['has_luck'] is True
        assert metadata['away']['has_luck'] is False


# ============================================================================
# TESTES: Limites e Edge Cases
# ============================================================================

class TestLimitesEdgeCases:
    """Testa casos extremos."""
    
    def test_xg_zero(self):
        """xG = 0 deve ser tratado como inválido."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=10.0,
            xg=0.0,
            games_played=10
        )
        
        assert has_luck is False
        assert classification == 'INVALID_XG'
    
    def test_xg_negativo(self):
        """xG negativo deve ser tratado como inválido."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=10.0,
            xg=-5.0,
            games_played=10
        )
        
        assert has_luck is False
        assert classification == 'INVALID_XG'
    
    def test_discrepancia_exatamente_threshold(self):
        """Discrepância exatamente no threshold não deve detectar sorte."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=10.5,
            xg=10.0,
            games_played=10,
            threshold=0.50
        )
        
        assert has_luck is False, "Discrepância = threshold não deveria detectar sorte"
        assert classification == 'NORMAL'
    
    def test_discrepancia_minimamente_acima_threshold(self):
        """Discrepância minimamente acima do threshold deve detectar sorte."""
        has_luck, discrepancy, classification = detectar_sorte_insustentavel(
            goals_scored=10.51,
            xg=10.0,
            games_played=10,
            threshold=0.50
        )
        
        assert has_luck is True, "Discrepância > threshold deveria detectar sorte"


# ============================================================================
# CONFIGURAÇÃO PYTEST
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
