"""
Testes Unitários para Lambda Calculator (S1)

Testa a implementação do cálculo dinâmico de lambda conforme especificação v5.5-ML.

Cobertura:
- Ponderação correta por regime (NORMAL vs HIPER-OFENSIVA)
- Ajuste por defesa adversária
- Validação de dados
- Casos extremos e fallbacks
- Compatibilidade com código legado

Autor: SportsBankPro Team
Data: Janeiro 2026
"""

import pytest
import sys
from pathlib import Path

# Adicionar diretório backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from modeling.lambda_calculator import (
    calcular_lambda_dinamico,
    calcular_lambda_jogo,
    calcular_lambda_legado,
    validar_dados_time,
    obter_info_ponderacao,
    PESOS_LAMBDA,
    LAMBDA_MIN,
    LAMBDA_MAX
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def team_data_completo():
    """Dados completos de um time."""
    return {
        'team_name': 'Arsenal',
        'goals_scored_avg_overall': 2.0,
        'goals_scored_avg_home': 2.2,
        'goals_scored_avg_away': 1.8,
        'goals_scored_avg_last_5': 2.5,
        'goals_conceded_avg_overall': 1.2,
        'goals_conceded_avg_home': 1.0,
        'goals_conceded_avg_away': 1.4
    }


@pytest.fixture
def team_data_minimo():
    """Dados mínimos de um time (apenas campos obrigatórios)."""
    return {
        'team_name': 'Chelsea',
        'goals_scored_avg_overall': 1.8,
        'goals_conceded_avg_overall': 1.5
    }


@pytest.fixture
def league_data_normal():
    """Dados de uma liga com regime NORMAL."""
    return {
        'league_name': 'Premier League',
        'average_goals_per_match': 2.7,
        'regime': 'NORMAL'
    }


@pytest.fixture
def league_data_hiper():
    """Dados de uma liga com regime HIPER-OFENSIVA."""
    return {
        'league_name': 'Eredivisie',
        'average_goals_per_match': 3.2,
        'regime': 'HIPER-OFENSIVA'
    }


# ============================================================================
# TESTES: Ponderação por Regime
# ============================================================================

class TestPonderacaoRegime:
    """Testa se a ponderação é aplicada corretamente por regime."""
    
    def test_ponderacao_normal_60_40(self, team_data_completo, league_data_normal):
        """
        Testa ponderação NORMAL: 60% temporada + 40% últimos 5.
        
        Dados:
        - Gols temporada (casa): 2.2
        - Gols últimos 5: 2.5
        
        Esperado (antes ajuste defesa):
        λ = (2.2 × 0.60) + (2.5 × 0.40) = 1.32 + 1.0 = 2.32
        """
        opponent_data = {
            'goals_conceded_avg_overall': 1.35,  # Igual à média da liga/2
            'goals_conceded_avg_away': 1.35
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_data=team_data_completo,
            opponent_data=opponent_data,
            league_data=league_data_normal,
            regime='NORMAL',
            is_home=True
        )
        
        # Cálculo esperado
        gols_temp = 2.2
        gols_ult5 = 2.5
        lambda_esperado = (gols_temp * 0.60) + (gols_ult5 * 0.40)  # 2.32
        
        # Defesa adversária = média liga, então fator = 1.0
        # Lambda final = 2.32 × 1.0 = 2.32
        
        assert abs(lambda_result - lambda_esperado) < 0.01, \
            f"Lambda esperado: {lambda_esperado:.3f}, obtido: {lambda_result:.3f}"
    
    def test_ponderacao_hiper_30_70(self, team_data_completo, league_data_hiper):
        """
        Testa ponderação HIPER-OFENSIVA: 30% temporada + 70% últimos 5.
        
        Dados:
        - Gols temporada (casa): 2.2
        - Gols últimos 5: 2.5
        
        Esperado (antes ajuste defesa):
        λ = (2.2 × 0.30) + (2.5 × 0.70) = 0.66 + 1.75 = 2.41
        """
        opponent_data = {
            'goals_conceded_avg_overall': 1.6,  # Igual à média da liga/2
            'goals_conceded_avg_away': 1.6
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_data=team_data_completo,
            opponent_data=opponent_data,
            league_data=league_data_hiper,
            regime='HIPER-OFENSIVA',
            is_home=True
        )
        
        # Cálculo esperado
        gols_temp = 2.2
        gols_ult5 = 2.5
        lambda_esperado = (gols_temp * 0.30) + (gols_ult5 * 0.70)  # 2.41
        
        # Defesa adversária = média liga, então fator = 1.0
        # Lambda final = 2.41 × 1.0 = 2.41
        
        assert abs(lambda_result - lambda_esperado) < 0.01, \
            f"Lambda esperado: {lambda_esperado:.3f}, obtido: {lambda_result:.3f}"
    
    def test_diferenca_entre_regimes(self, team_data_completo, league_data_normal, league_data_hiper):
        """
        Testa que regimes diferentes produzem lambdas diferentes
        quando forma recente difere da média da temporada.
        """
        # Time com forma recente melhor que média
        team_hot = {
            'goals_scored_avg_overall': 1.5,
            'goals_scored_avg_home': 1.5,
            'goals_scored_avg_last_5': 2.5,  # Muito melhor
            'goals_conceded_avg_overall': 1.2
        }
        
        opponent = {
            'goals_conceded_avg_overall': 1.35,
            'goals_conceded_avg_away': 1.35
        }
        
        lambda_normal = calcular_lambda_dinamico(
            team_hot, opponent, league_data_normal, 'NORMAL', True
        )
        
        lambda_hiper = calcular_lambda_dinamico(
            team_hot, opponent, league_data_hiper, 'HIPER-OFENSIVA', True
        )
        
        # HIPER-OFENSIVA deve dar mais peso à forma recente (2.5)
        # Então lambda_hiper deve ser maior que lambda_normal
        assert lambda_hiper > lambda_normal, \
            f"HIPER-OFENSIVA ({lambda_hiper:.3f}) deveria ser > NORMAL ({lambda_normal:.3f})"


# ============================================================================
# TESTES: Ajuste por Defesa Adversária
# ============================================================================

class TestAjusteDefesa:
    """Testa o ajuste de lambda pela defesa adversária."""
    
    def test_defesa_fraca_aumenta_lambda(self, team_data_completo, league_data_normal):
        """Defesa fraca do adversário deve aumentar lambda."""
        # Defesa fraca (sofre 2.0 gols/jogo, média liga é 1.35)
        opponent_fraco = {
            'goals_conceded_avg_overall': 2.0,
            'goals_conceded_avg_away': 2.0
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_data_completo, opponent_fraco, league_data_normal, 'NORMAL', True
        )
        
        # Fator defesa = 2.0 / 1.35 ≈ 1.48
        # Lambda base ≈ 2.32 (do teste anterior)
        # Lambda final ≈ 2.32 × 1.48 ≈ 3.43
        
        assert lambda_result > 3.0, \
            f"Lambda contra defesa fraca deveria ser > 3.0, obtido: {lambda_result:.3f}"
    
    def test_defesa_forte_reduz_lambda(self, team_data_completo, league_data_normal):
        """Defesa forte do adversário deve reduzir lambda."""
        # Defesa forte (sofre 0.8 gols/jogo, média liga é 1.35)
        opponent_forte = {
            'goals_conceded_avg_overall': 0.8,
            'goals_conceded_avg_away': 0.8
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_data_completo, opponent_forte, league_data_normal, 'NORMAL', True
        )
        
        # Fator defesa = 0.8 / 1.35 ≈ 0.59
        # Lambda base ≈ 2.32
        # Lambda final ≈ 2.32 × 0.59 ≈ 1.37
        
        assert lambda_result < 1.8, \
            f"Lambda contra defesa forte deveria ser < 1.8, obtido: {lambda_result:.3f}"


# ============================================================================
# TESTES: Mando de Campo
# ============================================================================

class TestMandoCampo:
    """Testa diferenciação entre casa e fora."""
    
    def test_usa_stats_casa_quando_home(self, league_data_normal):
        """Quando is_home=True, deve usar stats de casa."""
        team = {
            'goals_scored_avg_home': 2.5,  # Casa
            'goals_scored_avg_away': 1.5,  # Fora
            'goals_scored_avg_overall': 2.0,
            'goals_scored_avg_last_5': 2.2
        }
        
        opponent = {
            'goals_conceded_avg_overall': 1.35,
            'goals_conceded_avg_away': 1.35
        }
        
        lambda_home = calcular_lambda_dinamico(
            team, opponent, league_data_normal, 'NORMAL', is_home=True
        )
        
        # Deve usar goals_scored_avg_home (2.5)
        # λ = (2.5 × 0.60) + (2.2 × 0.40) = 1.5 + 0.88 = 2.38
        
        assert 2.2 < lambda_home < 2.5, \
            f"Lambda casa deveria estar entre 2.2 e 2.5, obtido: {lambda_home:.3f}"
    
    def test_usa_stats_fora_quando_away(self, league_data_normal):
        """Quando is_home=False, deve usar stats de fora."""
        team = {
            'goals_scored_avg_home': 2.5,
            'goals_scored_avg_away': 1.5,  # Fora
            'goals_scored_avg_overall': 2.0,
            'goals_scored_avg_last_5': 1.8
        }
        
        opponent = {
            'goals_conceded_avg_overall': 1.35,
            'goals_conceded_avg_home': 1.35
        }
        
        lambda_away = calcular_lambda_dinamico(
            team, opponent, league_data_normal, 'NORMAL', is_home=False
        )
        
        # Deve usar goals_scored_avg_away (1.5)
        # λ = (1.5 × 0.60) + (1.8 × 0.40) = 0.9 + 0.72 = 1.62
        
        assert 1.4 < lambda_away < 1.8, \
            f"Lambda fora deveria estar entre 1.4 e 1.8, obtido: {lambda_away:.3f}"


# ============================================================================
# TESTES: Validação de Dados
# ============================================================================

class TestValidacaoDados:
    """Testa validação e tratamento de dados inválidos."""
    
    def test_dados_validos(self, team_data_completo):
        """Dados completos devem passar na validação."""
        assert validar_dados_time(team_data_completo, "Arsenal") is True
    
    def test_dados_minimos_validos(self, team_data_minimo):
        """Dados mínimos (campos obrigatórios) devem passar."""
        assert validar_dados_time(team_data_minimo, "Chelsea") is True
    
    def test_dados_campo_faltando(self):
        """Dados sem campo obrigatório devem falhar."""
        team_invalido = {
            'team_name': 'Liverpool',
            'goals_scored_avg_overall': 2.0
            # Falta goals_conceded_avg_overall
        }
        assert validar_dados_time(team_invalido, "Liverpool") is False
    
    def test_dados_campo_none(self):
        """Dados com campo None devem falhar."""
        team_invalido = {
            'team_name': 'Manchester City',
            'goals_scored_avg_overall': None,
            'goals_conceded_avg_overall': 1.2
        }
        assert validar_dados_time(team_invalido, "Manchester City") is False
    
    def test_fallback_quando_dados_insuficientes(self, league_data_normal):
        """Quando dados insuficientes, deve usar média da liga como fallback."""
        team_vazio = {
            'goals_scored_avg_overall': 0.0,
            'goals_scored_avg_last_5': 0.0
        }
        
        opponent = {'goals_conceded_avg_overall': 1.35}
        
        lambda_result = calcular_lambda_dinamico(
            team_vazio, opponent, league_data_normal, 'NORMAL', True
        )
        
        # Deve usar média da liga / 2 = 2.7 / 2 = 1.35
        media_esperada = league_data_normal['average_goals_per_match'] / 2
        
        assert abs(lambda_result - media_esperada) < 0.1, \
            f"Fallback deveria ser ~{media_esperada:.2f}, obtido: {lambda_result:.3f}"


# ============================================================================
# TESTES: Limites de Segurança
# ============================================================================

class TestLimitesSeguranca:
    """Testa aplicação de limites mínimo e máximo."""
    
    def test_lambda_minimo(self, league_data_normal):
        """Lambda não deve ser menor que LAMBDA_MIN."""
        team_fraco = {
            'goals_scored_avg_overall': 0.1,
            'goals_scored_avg_last_5': 0.1
        }
        
        opponent_forte = {
            'goals_conceded_avg_overall': 0.5
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_fraco, opponent_forte, league_data_normal, 'NORMAL', True
        )
        
        assert lambda_result >= LAMBDA_MIN, \
            f"Lambda ({lambda_result:.3f}) deveria ser >= {LAMBDA_MIN}"
    
    def test_lambda_maximo(self, league_data_hiper):
        """Lambda não deve ser maior que LAMBDA_MAX."""
        team_forte = {
            'goals_scored_avg_overall': 4.0,
            'goals_scored_avg_last_5': 5.0
        }
        
        opponent_fraco = {
            'goals_conceded_avg_overall': 3.5
        }
        
        lambda_result = calcular_lambda_dinamico(
            team_forte, opponent_fraco, league_data_hiper, 'HIPER-OFENSIVA', True
        )
        
        assert lambda_result <= LAMBDA_MAX, \
            f"Lambda ({lambda_result:.3f}) deveria ser <= {LAMBDA_MAX}"


# ============================================================================
# TESTES: Função calcular_lambda_jogo
# ============================================================================

class TestCalcularLambdaJogo:
    """Testa cálculo de lambda para ambos os times."""
    
    def test_retorna_tupla(self, team_data_completo, team_data_minimo, league_data_normal):
        """Deve retornar tupla (lambda_home, lambda_away)."""
        result = calcular_lambda_jogo(
            team_data_completo, team_data_minimo, league_data_normal, 'NORMAL'
        )
        
        assert isinstance(result, tuple), "Deve retornar tupla"
        assert len(result) == 2, "Tupla deve ter 2 elementos"
        
        lambda_home, lambda_away = result
        
        assert isinstance(lambda_home, float), "lambda_home deve ser float"
        assert isinstance(lambda_away, float), "lambda_away deve ser float"
    
    def test_lambda_home_maior_que_away(self, league_data_normal):
        """Time mandante forte deve ter lambda maior que visitante fraco."""
        home_forte = {
            'goals_scored_avg_home': 2.5,
            'goals_scored_avg_last_5': 2.8,
            'goals_conceded_avg_overall': 1.0
        }
        
        away_fraco = {
            'goals_scored_avg_away': 1.2,
            'goals_scored_avg_last_5': 1.0,
            'goals_conceded_avg_overall': 2.0
        }
        
        lambda_home, lambda_away = calcular_lambda_jogo(
            home_forte, away_fraco, league_data_normal, 'NORMAL'
        )
        
        assert lambda_home > lambda_away, \
            f"Lambda casa ({lambda_home:.3f}) deveria ser > fora ({lambda_away:.3f})"


# ============================================================================
# TESTES: Compatibilidade com Código Legado
# ============================================================================

class TestCompatibilidadeLegado:
    """Testa compatibilidade com função legada expected_goals."""
    
    def test_calcular_lambda_legado(self):
        """Função legada deve calcular lambda corretamente."""
        home_attack = 1.2
        away_defense = 0.9
        away_attack = 1.1
        home_defense = 1.0
        league_avg = 1.35
        
        lam_home, lam_away = calcular_lambda_legado(
            home_attack, away_defense, away_attack, home_defense, league_avg
        )
        
        # lam_home = 1.35 × 1.2 × 0.9 = 1.458
        # lam_away = 1.35 × 1.1 × 1.0 = 1.485
        
        assert abs(lam_home - 1.458) < 0.01, f"Lambda home esperado: 1.458, obtido: {lam_home:.3f}"
        assert abs(lam_away - 1.485) < 0.01, f"Lambda away esperado: 1.485, obtido: {lam_away:.3f}"
    
    def test_limites_aplicados_legado(self):
        """Função legada deve aplicar limites."""
        lam_home, lam_away = calcular_lambda_legado(
            home_attack=5.0,
            away_defense=5.0,
            away_attack=0.01,
            home_defense=0.01,
            league_avg=2.0
        )
        
        # Sem limites: lam_home = 2.0 × 5.0 × 5.0 = 50.0 (muito alto)
        # Com limites: deve ser <= LAMBDA_MAX
        
        assert lam_home <= LAMBDA_MAX, f"Lambda home deveria ser <= {LAMBDA_MAX}"
        assert lam_away >= LAMBDA_MIN, f"Lambda away deveria ser >= {LAMBDA_MIN}"


# ============================================================================
# TESTES: Funções Auxiliares
# ============================================================================

class TestFuncoesAuxiliares:
    """Testa funções auxiliares do módulo."""
    
    def test_obter_info_ponderacao_normal(self):
        """Deve retornar pesos corretos para NORMAL."""
        pesos = obter_info_ponderacao('NORMAL')
        
        assert pesos['temporada'] == 0.60
        assert pesos['ultimos5'] == 0.40
    
    def test_obter_info_ponderacao_hiper(self):
        """Deve retornar pesos corretos para HIPER-OFENSIVA."""
        pesos = obter_info_ponderacao('HIPER-OFENSIVA')
        
        assert pesos['temporada'] == 0.30
        assert pesos['ultimos5'] == 0.70
    
    def test_obter_info_ponderacao_invalido(self):
        """Regime inválido deve retornar NORMAL como fallback."""
        pesos = obter_info_ponderacao('INVALIDO')
        
        assert pesos['temporada'] == 0.60  # NORMAL
        assert pesos['ultimos5'] == 0.40


# ============================================================================
# TESTES: Casos Reais
# ============================================================================

class TestCasosReais:
    """Testa com dados realistas de jogos."""
    
    def test_arsenal_vs_chelsea_normal(self):
        """
        Teste com dados realistas: Arsenal vs Chelsea em liga NORMAL.
        """
        arsenal = {
            'team_name': 'Arsenal',
            'goals_scored_avg_home': 2.1,
            'goals_scored_avg_last_5': 2.4,
            'goals_conceded_avg_overall': 1.1
        }
        
        chelsea = {
            'team_name': 'Chelsea',
            'goals_scored_avg_away': 1.6,
            'goals_scored_avg_last_5': 1.8,
            'goals_conceded_avg_overall': 1.3,
            'goals_conceded_avg_away': 1.4
        }
        
        league = {
            'league_name': 'Premier League',
            'average_goals_per_match': 2.7
        }
        
        lambda_home, lambda_away = calcular_lambda_jogo(
            arsenal, chelsea, league, 'NORMAL'
        )
        
        # Arsenal casa: (2.1 × 0.60) + (2.4 × 0.40) = 1.26 + 0.96 = 2.22
        # Ajuste defesa Chelsea fora: 1.4 / 1.35 ≈ 1.04
        # Lambda Arsenal ≈ 2.22 × 1.04 ≈ 2.31
        
        # Chelsea fora: (1.6 × 0.60) + (1.8 × 0.40) = 0.96 + 0.72 = 1.68
        # Ajuste defesa Arsenal casa: 1.1 / 1.35 ≈ 0.81
        # Lambda Chelsea ≈ 1.68 × 0.81 ≈ 1.36
        
        assert 2.0 < lambda_home < 2.5, f"Lambda Arsenal esperado ~2.3, obtido: {lambda_home:.3f}"
        assert 1.2 < lambda_away < 1.6, f"Lambda Chelsea esperado ~1.4, obtido: {lambda_away:.3f}"
    
    def test_ajax_vs_psv_hiper(self):
        """
        Teste com dados realistas: Ajax vs PSV em liga HIPER-OFENSIVA (Eredivisie).
        """
        ajax = {
            'team_name': 'Ajax',
            'goals_scored_avg_home': 3.0,
            'goals_scored_avg_last_5': 3.5,
            'goals_conceded_avg_overall': 1.8
        }
        
        psv = {
            'team_name': 'PSV',
            'goals_scored_avg_away': 2.5,
            'goals_scored_avg_last_5': 2.8,
            'goals_conceded_avg_overall': 1.9,
            'goals_conceded_avg_away': 2.1
        }
        
        league = {
            'league_name': 'Eredivisie',
            'average_goals_per_match': 3.2
        }
        
        lambda_home, lambda_away = calcular_lambda_jogo(
            ajax, psv, league, 'HIPER-OFENSIVA'
        )
        
        # Ajax casa: (3.0 × 0.30) + (3.5 × 0.70) = 0.9 + 2.45 = 3.35
        # Ajuste defesa PSV fora: 2.1 / 1.6 ≈ 1.31
        # Lambda Ajax ≈ 3.35 × 1.31 ≈ 4.39 (limitado a LAMBDA_MAX = 4.5)
        
        # PSV fora: (2.5 × 0.30) + (2.8 × 0.70) = 0.75 + 1.96 = 2.71
        # Ajuste defesa Ajax casa: 1.8 / 1.6 ≈ 1.13
        # Lambda PSV ≈ 2.71 × 1.13 ≈ 3.06
        
        assert lambda_home > 3.5, f"Lambda Ajax esperado > 3.5, obtido: {lambda_home:.3f}"
        assert 2.5 < lambda_away < 3.5, f"Lambda PSV esperado ~3.0, obtido: {lambda_away:.3f}"


# ============================================================================
# CONFIGURAÇÃO PYTEST
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
