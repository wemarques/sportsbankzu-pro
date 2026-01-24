"""
Testes Unitários para Chaos Detector (S4)

Testa a implementação de Detecção de Caos conforme v5.5-ML.

Cobertura:
- Cálculo de Coeficiente de Variação
- Detecção de caos por xG
- Detecção de caos por resultados
- Detecção em times e jogos
- Penalidade de confiança
- Filtros de jogos

Autor: SportsBankPro Team
Data: Janeiro 2026
"""

import pytest
from backend.modeling.chaos_detector import (
    calcular_coeficiente_variacao,
    detectar_caos_xg,
    detectar_caos_resultados,
    detectar_caos_time,
    detectar_caos_jogo,
    aplicar_penalidade_confianca,
    filtrar_jogos_caos,
    obter_info_caos,
    validar_dados_caos,
    CHAOS_CV_THRESHOLD,
    CHAOS_CONFIDENCE_PENALTY
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def xg_estavel():
    """xG estável (baixa variação)."""
    return [1.5, 1.6, 1.4, 1.5, 1.55, 1.45]


@pytest.fixture
def xg_caos():
    """xG em caos (alta variação)."""
    return [0.5, 3.0, 0.8, 2.5, 1.0, 3.5]


@pytest.fixture
def team_estavel():
    """Time com performance estável."""
    return {
        'team_name': 'Stable FC',
        'xg_per_game': [1.5, 1.6, 1.4, 1.5, 1.55, 1.45],
        'goals_per_game': [2, 2, 1, 2, 2, 1]
    }


@pytest.fixture
def team_caos():
    """Time com performance caótica."""
    return {
        'team_name': 'Chaos FC',
        'xg_per_game': [0.5, 3.0, 0.8, 2.5, 1.0, 3.5],
        'goals_per_game': [0, 4, 0, 5, 1, 4]
    }


# ============================================================================
# TESTES: Coeficiente de Variação
# ============================================================================

class TestCoeficienteVariacao:
    """Testa cálculo de CV."""
    
    def test_cv_baixo(self, xg_estavel):
        """CV deve ser baixo para valores estáveis."""
        cv = calcular_coeficiente_variacao(xg_estavel)
        assert cv < 0.10, f"CV deveria ser < 0.10, obtido: {cv:.2f}"
    
    def test_cv_alto(self, xg_caos):
        """CV deve ser alto para valores caóticos."""
        cv = calcular_coeficiente_variacao(xg_caos)
        assert cv > 0.50, f"CV deveria ser > 0.50, obtido: {cv:.2f}"
    
    def test_cv_valores_identicos(self):
        """CV deve ser 0 para valores idênticos."""
        cv = calcular_coeficiente_variacao([2.0, 2.0, 2.0, 2.0])
        assert cv == 0.0, f"CV deveria ser 0.0, obtido: {cv:.2f}"
    
    def test_cv_poucos_valores(self):
        """CV deve retornar 0 para menos de 2 valores."""
        cv = calcular_coeficiente_variacao([2.0])
        assert cv == 0.0


# ============================================================================
# TESTES: Detecção de Caos por xG
# ============================================================================

class TestDeteccaoCaosXG:
    """Testa detecção de caos por xG."""
    
    def test_nao_detecta_caos_estavel(self, xg_estavel):
        """Não deve detectar caos em xG estável."""
        has_chaos, cv, classification = detectar_caos_xg(xg_estavel)
        
        assert has_chaos is False
        assert classification == 'ESTAVEL'
        assert cv < CHAOS_CV_THRESHOLD
    
    def test_detecta_caos_alto(self, xg_caos):
        """Deve detectar caos em xG caótico."""
        has_chaos, cv, classification = detectar_caos_xg(xg_caos)
        
        assert has_chaos is True
        assert classification == 'CAOS'
        assert cv > CHAOS_CV_THRESHOLD * 1.5
    
    def test_detecta_moderado(self):
        """Deve detectar variação moderada."""
        xg_moderado = [1.0, 1.8, 1.2, 1.6, 1.3, 1.7]
        has_chaos, cv, classification = detectar_caos_xg(xg_moderado)
        
        # Moderado não é considerado caos
        assert has_chaos is False
        assert classification in ['ESTAVEL', 'MODERADO']
    
    def test_dados_insuficientes(self):
        """Não deve detectar caos com poucos dados."""
        xg_poucos = [1.0, 2.0, 0.5]  # Menos que MIN_SAMPLE_SIZE
        has_chaos, cv, classification = detectar_caos_xg(xg_poucos)
        
        assert has_chaos is False
        assert classification == 'INSUFFICIENT_DATA'


# ============================================================================
# TESTES: Detecção de Caos por Resultados
# ============================================================================

class TestDeteccaoCaosResultados:
    """Testa detecção de caos por gols."""
    
    def test_nao_detecta_caos_gols_estaveis(self):
        """Não deve detectar caos em gols estáveis."""
        goals = [2, 2, 1, 2, 2, 1]
        has_chaos, cv, classification = detectar_caos_resultados(goals)
        
        assert has_chaos is False
        assert classification == 'ESTAVEL'
    
    def test_detecta_caos_gols_caoticos(self):
        """Deve detectar caos em gols caóticos."""
        goals = [0, 4, 0, 5, 1, 4]
        has_chaos, cv, classification = detectar_caos_resultados(goals)
        
        assert has_chaos is True
        assert classification == 'CAOS'


# ============================================================================
# TESTES: Detecção em Times
# ============================================================================

class TestDeteccaoCaosTimes:
    """Testa detecção de caos em times."""
    
    def test_nao_detecta_caos_time_estavel(self, team_estavel):
        """Não deve detectar caos em time estável."""
        has_chaos, metadata = detectar_caos_time(team_estavel)
        
        assert has_chaos is False
        assert metadata['has_chaos'] is False
        assert metadata['classification'] == 'ESTAVEL'
    
    def test_detecta_caos_time_caotico(self, team_caos):
        """Deve detectar caos em time caótico."""
        has_chaos, metadata = detectar_caos_time(team_caos)
        
        assert has_chaos is True
        assert metadata['has_chaos'] is True
        assert metadata['classification'] == 'CAOS'
    
    def test_detecta_por_xg(self, team_caos):
        """Deve detectar caos por xG."""
        has_chaos, metadata = detectar_caos_time(team_caos)
        
        assert metadata['method'] == 'xg'
        assert metadata['cv_xg'] > CHAOS_CV_THRESHOLD
    
    def test_detecta_por_goals_quando_sem_xg(self):
        """Deve detectar caos por gols quando não tem xG."""
        team = {
            'team_name': 'No xG FC',
            'goals_per_game': [0, 4, 0, 5, 1, 4]
        }
        has_chaos, metadata = detectar_caos_time(team)
        
        assert has_chaos is True
        assert metadata['method'] == 'goals'


# ============================================================================
# TESTES: Detecção em Jogos
# ============================================================================

class TestDeteccaoCaosJogos:
    """Testa detecção de caos em jogos."""
    
    def test_nao_detecta_caos_ambos_estaveis(self, team_estavel):
        """Não deve detectar caos se ambos estáveis."""
        has_chaos, metadata = detectar_caos_jogo(team_estavel, team_estavel)
        
        assert has_chaos is False
        assert metadata['any_chaos'] is False
        assert metadata['both_chaos'] is False
    
    def test_detecta_caos_home_caotico(self, team_caos, team_estavel):
        """Deve detectar caos se home caótico."""
        has_chaos, metadata = detectar_caos_jogo(team_caos, team_estavel)
        
        assert has_chaos is True
        assert metadata['any_chaos'] is True
        assert metadata['home']['has_chaos'] is True
        assert metadata['away']['has_chaos'] is False
    
    def test_detecta_caos_away_caotico(self, team_estavel, team_caos):
        """Deve detectar caos se away caótico."""
        has_chaos, metadata = detectar_caos_jogo(team_estavel, team_caos)
        
        assert has_chaos is True
        assert metadata['any_chaos'] is True
        assert metadata['home']['has_chaos'] is False
        assert metadata['away']['has_chaos'] is True
    
    def test_detecta_caos_ambos_caoticos(self, team_caos):
        """Deve detectar caos se ambos caóticos."""
        has_chaos, metadata = detectar_caos_jogo(team_caos, team_caos)
        
        assert has_chaos is True
        assert metadata['any_chaos'] is True
        assert metadata['both_chaos'] is True


# ============================================================================
# TESTES: Penalidade de Confiança
# ============================================================================

class TestPenalidadeConfianca:
    """Testa aplicação de penalidade de confiança."""
    
    def test_mantem_confianca_sem_caos(self):
        """Deve manter confiança se não há caos."""
        confidence = 0.80
        adjusted = aplicar_penalidade_confianca(confidence, has_chaos=False)
        
        assert adjusted == confidence
    
    def test_reduz_confianca_com_caos(self):
        """Deve reduzir confiança se há caos."""
        confidence = 0.80
        adjusted = aplicar_penalidade_confianca(confidence, has_chaos=True)
        
        expected = confidence * (1 - CHAOS_CONFIDENCE_PENALTY)
        assert adjusted == expected
        assert adjusted < confidence
    
    def test_penalidade_customizada(self):
        """Deve aplicar penalidade customizada."""
        confidence = 0.80
        penalty = 0.30  # 30%
        adjusted = aplicar_penalidade_confianca(confidence, has_chaos=True, penalty=penalty)
        
        expected = confidence * (1 - penalty)
        assert adjusted == expected


# ============================================================================
# TESTES: Filtro de Jogos
# ============================================================================

class TestFiltroJogos:
    """Testa filtro de jogos com caos."""
    
    def test_filtra_jogos_com_caos(self, team_estavel, team_caos):
        """Deve remover jogos com caos."""
        jogos = [
            {'home': team_estavel, 'away': team_estavel},  # Sem caos
            {'home': team_caos, 'away': team_estavel},     # Com caos
            {'home': team_estavel, 'away': team_estavel}   # Sem caos
        ]
        
        filtrados, removidos = filtrar_jogos_caos(jogos)
        
        assert len(filtrados) == 2
        assert removidos == 1
    
    def test_marca_mas_nao_remove(self, team_estavel, team_caos):
        """Deve marcar mas não remover se remove_chaos=False."""
        jogos = [
            {'home': team_estavel, 'away': team_estavel},
            {'home': team_caos, 'away': team_estavel}
        ]
        
        filtrados, removidos = filtrar_jogos_caos(jogos, remove_chaos=False)
        
        assert len(filtrados) == 2
        assert removidos == 1
        assert filtrados[1].get('_has_chaos') is True
    
    def test_nao_remove_nada_sem_caos(self, team_estavel):
        """Não deve remover nada se não há caos."""
        jogos = [
            {'home': team_estavel, 'away': team_estavel},
            {'home': team_estavel, 'away': team_estavel}
        ]
        
        filtrados, removidos = filtrar_jogos_caos(jogos)
        
        assert len(filtrados) == 2
        assert removidos == 0


# ============================================================================
# TESTES: Validação de Dados
# ============================================================================

class TestValidacaoDados:
    """Testa validação de dados para detecção de caos."""
    
    def test_dados_validos_com_xg(self, team_estavel):
        """Dados com xg_per_game devem ser válidos."""
        assert validar_dados_caos(team_estavel, "Stable FC") is True
    
    def test_dados_validos_com_goals(self):
        """Dados com goals_per_game devem ser válidos."""
        team = {
            'team_name': 'Goals FC',
            'goals_per_game': [2, 2, 1, 2, 2]
        }
        assert validar_dados_caos(team, "Goals FC") is True
    
    def test_dados_invalidos_sem_campos(self):
        """Dados sem xg_per_game nem goals_per_game devem ser inválidos."""
        team = {
            'team_name': 'Invalid FC'
        }
        assert validar_dados_caos(team, "Invalid FC") is False


# ============================================================================
# TESTES: Funções Auxiliares
# ============================================================================

class TestFuncoesAuxiliares:
    """Testa funções auxiliares."""
    
    def test_obter_info_caos(self):
        """Deve retornar informações de configuração."""
        info = obter_info_caos()
        
        assert info['cv_threshold'] == CHAOS_CV_THRESHOLD
        assert info['min_sample_size'] == 5
        assert info['confidence_penalty'] == CHAOS_CONFIDENCE_PENALTY


# ============================================================================
# TESTES: Casos Reais
# ============================================================================

class TestCasosReais:
    """Testa com dados realistas."""
    
    def test_manchester_city_estavel(self):
        """Manchester City tem performance estável."""
        city = {
            'team_name': 'Manchester City',
            'xg_per_game': [2.1, 2.3, 2.0, 2.2, 2.1, 2.4]
        }
        
        has_chaos, metadata = detectar_caos_time(city)
        
        assert has_chaos is False
        assert metadata['classification'] == 'ESTAVEL'
    
    def test_time_inconsistente(self):
        """Time inconsistente deve ter caos detectado."""
        inconsistente = {
            'team_name': 'Inconsistent FC',
            'xg_per_game': [0.8, 3.2, 0.5, 2.8, 1.0, 3.5]
        }
        
        has_chaos, metadata = detectar_caos_time(inconsistente)
        
        assert has_chaos is True
        assert metadata['classification'] == 'CAOS'


# ============================================================================
# TESTES: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Testa casos extremos."""
    
    def test_cv_media_zero(self):
        """CV com média zero deve retornar infinito."""
        cv = calcular_coeficiente_variacao([0.0, 0.0, 0.0])
        assert cv == float('inf')
    
    def test_um_valor(self):
        """Um único valor deve retornar CV = 0."""
        cv = calcular_coeficiente_variacao([2.0])
        assert cv == 0.0
    
    def test_lista_vazia(self):
        """Lista vazia deve retornar CV = 0."""
        cv = calcular_coeficiente_variacao([])
        assert cv == 0.0


# ============================================================================
# CONFIGURAÇÃO PYTEST
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
