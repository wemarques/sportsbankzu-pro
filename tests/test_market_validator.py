"""
Testes Unitários para Market Validator (S3)

Testa a implementação de Validação de Mercados Proibidos conforme v5.5-ML.

Cobertura:
- Validação de mercados individuais
- Validação de listas de mercados
- Filtros de mercados permitidos
- Validação de prognósticos completos
- Casos por regime (NORMAL, DEFENSIVA, HIPER-OFENSIVA)

Autor: SportsBankPro Team
Data: Janeiro 2026
"""

import pytest
from backend.modeling.market_validator import (
    validar_mercado,
    validar_mercados_lista,
    filtrar_mercados_permitidos,
    obter_mercados_permitidos,
    obter_mercados_proibidos,
    validar_prognostico,
    aplicar_validacao_mercados,
    obter_info_validacao,
    MERCADOS_PROIBIDOS,
    MERCADOS_VALIDOS
)


# ============================================================================
# TESTES: Validação Individual
# ============================================================================

class TestValidacaoIndividual:
    """Testa validação de mercados individuais."""
    
    def test_over_25_permitido_normal(self):
        """Over 2.5 deve ser permitido em NORMAL."""
        is_valid, reason = validar_mercado('Over 2.5', 'NORMAL')
        assert is_valid is True
        assert reason == 'OK'
    
    def test_over_35_proibido_normal(self):
        """Over 3.5 deve ser proibido em NORMAL."""
        is_valid, reason = validar_mercado('Over 3.5', 'NORMAL')
        assert is_valid is False
        assert 'proibido' in reason.lower()
    
    def test_over_45_proibido_normal(self):
        """Over 4.5 deve ser proibido em NORMAL."""
        is_valid, reason = validar_mercado('Over 4.5', 'NORMAL')
        assert is_valid is False
        assert 'proibido' in reason.lower()
    
    def test_over_25_proibido_defensiva(self):
        """Over 2.5 deve ser proibido em DEFENSIVA."""
        is_valid, reason = validar_mercado('Over 2.5', 'DEFENSIVA')
        assert is_valid is False
        assert 'proibido' in reason.lower()
    
    def test_over_15_permitido_defensiva(self):
        """Over 1.5 deve ser permitido em DEFENSIVA."""
        is_valid, reason = validar_mercado('Over 1.5', 'DEFENSIVA')
        assert is_valid is True
        assert reason == 'OK'
    
    def test_over_35_permitido_hiper_ofensiva(self):
        """Over 3.5 deve ser permitido em HIPER-OFENSIVA."""
        is_valid, reason = validar_mercado('Over 3.5', 'HIPER-OFENSIVA')
        assert is_valid is True
        assert reason == 'OK'
    
    def test_over_45_permitido_hiper_ofensiva(self):
        """Over 4.5 deve ser permitido em HIPER-OFENSIVA."""
        is_valid, reason = validar_mercado('Over 4.5', 'HIPER-OFENSIVA')
        assert is_valid is True
        assert reason == 'OK'
    
    def test_btts_proibido_defensiva(self):
        """BTTS deve ser proibido em DEFENSIVA."""
        is_valid, reason = validar_mercado('BTTS', 'DEFENSIVA')
        assert is_valid is False
        assert 'proibido' in reason.lower()
    
    def test_btts_permitido_normal(self):
        """BTTS deve ser permitido em NORMAL."""
        is_valid, reason = validar_mercado('BTTS', 'NORMAL')
        assert is_valid is True
        assert reason == 'OK'
    
    def test_mercado_invalido(self):
        """Mercado inexistente deve ser inválido."""
        is_valid, reason = validar_mercado('Over 10.5', 'NORMAL')
        assert is_valid is False
        assert 'inválido' in reason.lower()


# ============================================================================
# TESTES: Validação de Listas
# ============================================================================

class TestValidacaoListas:
    """Testa validação de listas de mercados."""
    
    def test_validar_lista_mista_normal(self):
        """Lista mista deve retornar validação correta."""
        markets = ['Over 2.5', 'Over 3.5', 'BTTS']
        resultados = validar_mercados_lista(markets, 'NORMAL')
        
        assert resultados['Over 2.5'][0] is True
        assert resultados['Over 3.5'][0] is False
        assert resultados['BTTS'][0] is True
    
    def test_filtrar_mercados_normal(self):
        """Filtro deve remover mercados proibidos."""
        markets = ['Over 2.5', 'Over 3.5', 'Over 4.5', 'BTTS']
        permitidos = filtrar_mercados_permitidos(markets, 'NORMAL')
        
        assert 'Over 2.5' in permitidos
        assert 'BTTS' in permitidos
        assert 'Over 3.5' not in permitidos
        assert 'Over 4.5' not in permitidos
    
    def test_filtrar_mercados_defensiva(self):
        """Filtro deve remover Over 2.5+ em DEFENSIVA."""
        markets = ['Over 1.5', 'Over 2.5', 'Over 3.5', 'BTTS']
        permitidos = filtrar_mercados_permitidos(markets, 'DEFENSIVA')
        
        assert 'Over 1.5' in permitidos
        assert 'Over 2.5' not in permitidos
        assert 'Over 3.5' not in permitidos
        assert 'BTTS' not in permitidos
    
    def test_filtrar_mercados_hiper_ofensiva(self):
        """Filtro não deve remover nada em HIPER-OFENSIVA."""
        markets = ['Over 2.5', 'Over 3.5', 'Over 4.5', 'BTTS']
        permitidos = filtrar_mercados_permitidos(markets, 'HIPER-OFENSIVA')
        
        assert len(permitidos) == len(markets)
        assert set(permitidos) == set(markets)


# ============================================================================
# TESTES: Obter Mercados
# ============================================================================

class TestObterMercados:
    """Testa funções de obter mercados."""
    
    def test_obter_proibidos_normal(self):
        """Deve retornar Over 3.5 e 4.5 para NORMAL."""
        proibidos = obter_mercados_proibidos('NORMAL')
        assert 'Over 3.5' in proibidos
        assert 'Over 4.5' in proibidos
        assert len(proibidos) == 2
    
    def test_obter_proibidos_defensiva(self):
        """Deve retornar Over 2.5, 3.5, 4.5 e BTTS para DEFENSIVA."""
        proibidos = obter_mercados_proibidos('DEFENSIVA')
        assert 'Over 2.5' in proibidos
        assert 'Over 3.5' in proibidos
        assert 'Over 4.5' in proibidos
        assert 'BTTS' in proibidos
        assert len(proibidos) == 4
    
    def test_obter_proibidos_hiper_ofensiva(self):
        """Deve retornar lista vazia para HIPER-OFENSIVA."""
        proibidos = obter_mercados_proibidos('HIPER-OFENSIVA')
        assert len(proibidos) == 0
    
    def test_obter_permitidos_normal(self):
        """Deve retornar todos exceto Over 3.5 e 4.5 para NORMAL."""
        permitidos = obter_mercados_permitidos('NORMAL')
        assert 'Over 2.5' in permitidos
        assert 'Over 3.5' not in permitidos
        assert 'Over 4.5' not in permitidos
    
    def test_obter_permitidos_hiper_ofensiva(self):
        """Deve retornar todos para HIPER-OFENSIVA."""
        permitidos = obter_mercados_permitidos('HIPER-OFENSIVA')
        assert len(permitidos) == len(MERCADOS_VALIDOS)


# ============================================================================
# TESTES: Validação de Prognósticos
# ============================================================================

class TestValidacaoPrognosticos:
    """Testa validação de prognósticos completos."""
    
    def test_prognostico_valido(self):
        """Prognóstico com mercados permitidos deve ser válido."""
        prog = {
            'markets': ['Over 2.5', 'BTTS']
        }
        is_valid, invalidos = validar_prognostico(prog, 'NORMAL')
        
        assert is_valid is True
        assert len(invalidos) == 0
    
    def test_prognostico_invalido(self):
        """Prognóstico com mercado proibido deve ser inválido."""
        prog = {
            'markets': ['Over 2.5', 'Over 3.5']
        }
        is_valid, invalidos = validar_prognostico(prog, 'NORMAL')
        
        assert is_valid is False
        assert 'Over 3.5' in invalidos
    
    def test_prognostico_com_picks_dict(self):
        """Deve validar prognóstico com picks em formato dict."""
        prog = {
            'picks': [
                {'market': 'Over 2.5', 'prob': 0.65},
                {'market': 'Over 3.5', 'prob': 0.45}
            ]
        }
        is_valid, invalidos = validar_prognostico(prog, 'NORMAL')
        
        assert is_valid is False
        assert 'Over 3.5' in invalidos
    
    def test_prognostico_vazio(self):
        """Prognóstico sem mercados deve ser considerado válido."""
        prog = {}
        is_valid, invalidos = validar_prognostico(prog, 'NORMAL')
        
        assert is_valid is True
        assert len(invalidos) == 0


# ============================================================================
# TESTES: Aplicação em Lote
# ============================================================================

class TestAplicacaoLote:
    """Testa aplicação de validação em lote."""
    
    def test_aplicar_validacao_remove_invalidos(self):
        """Deve remover prognósticos inválidos por padrão."""
        progs = [
            {'market': 'Over 2.5', 'prob': 0.65},
            {'market': 'Over 3.5', 'prob': 0.45},
            {'market': 'BTTS', 'prob': 0.55}
        ]
        
        validos, removidos = aplicar_validacao_mercados(progs, 'NORMAL')
        
        assert len(validos) == 2
        assert removidos == 1
    
    def test_aplicar_validacao_mantem_invalidos(self):
        """Deve marcar mas não remover se remove_invalid=False."""
        progs = [
            {'market': 'Over 2.5', 'prob': 0.65},
            {'market': 'Over 3.5', 'prob': 0.45}
        ]
        
        validos, removidos = aplicar_validacao_mercados(
            progs, 'NORMAL', remove_invalid=False
        )
        
        assert len(validos) == 2
        assert removidos == 1
        assert validos[1].get('_invalid') is True
    
    def test_aplicar_validacao_todos_validos(self):
        """Não deve remover nada se todos válidos."""
        progs = [
            {'market': 'Over 2.5', 'prob': 0.65},
            {'market': 'BTTS', 'prob': 0.55}
        ]
        
        validos, removidos = aplicar_validacao_mercados(progs, 'NORMAL')
        
        assert len(validos) == 2
        assert removidos == 0


# ============================================================================
# TESTES: Casos por Regime
# ============================================================================

class TestCasosPorRegime:
    """Testa casos específicos por regime."""
    
    def test_regime_normal_completo(self):
        """Teste completo para regime NORMAL."""
        # Permitidos
        assert validar_mercado('Over 0.5', 'NORMAL')[0] is True
        assert validar_mercado('Over 1.5', 'NORMAL')[0] is True
        assert validar_mercado('Over 2.5', 'NORMAL')[0] is True
        assert validar_mercado('BTTS', 'NORMAL')[0] is True
        
        # Proibidos
        assert validar_mercado('Over 3.5', 'NORMAL')[0] is False
        assert validar_mercado('Over 4.5', 'NORMAL')[0] is False
    
    def test_regime_defensiva_completo(self):
        """Teste completo para regime DEFENSIVA."""
        # Permitidos
        assert validar_mercado('Over 0.5', 'DEFENSIVA')[0] is True
        assert validar_mercado('Over 1.5', 'DEFENSIVA')[0] is True
        assert validar_mercado('Under 2.5', 'DEFENSIVA')[0] is True
        
        # Proibidos
        assert validar_mercado('Over 2.5', 'DEFENSIVA')[0] is False
        assert validar_mercado('Over 3.5', 'DEFENSIVA')[0] is False
        assert validar_mercado('Over 4.5', 'DEFENSIVA')[0] is False
        assert validar_mercado('BTTS', 'DEFENSIVA')[0] is False
    
    def test_regime_hiper_ofensiva_completo(self):
        """Teste completo para regime HIPER-OFENSIVA."""
        # Todos permitidos
        assert validar_mercado('Over 2.5', 'HIPER-OFENSIVA')[0] is True
        assert validar_mercado('Over 3.5', 'HIPER-OFENSIVA')[0] is True
        assert validar_mercado('Over 4.5', 'HIPER-OFENSIVA')[0] is True
        assert validar_mercado('BTTS', 'HIPER-OFENSIVA')[0] is True


# ============================================================================
# TESTES: Funções Auxiliares
# ============================================================================

class TestFuncoesAuxiliares:
    """Testa funções auxiliares."""
    
    def test_obter_info_validacao(self):
        """Deve retornar informações de validação."""
        info = obter_info_validacao()
        
        assert 'mercados_proibidos' in info
        assert 'mercados_validos' in info
        assert 'regimes_suportados' in info
        assert 'NORMAL' in info['regimes_suportados']
        assert 'DEFENSIVA' in info['regimes_suportados']
        assert 'HIPER-OFENSIVA' in info['regimes_suportados']


# ============================================================================
# TESTES: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Testa casos extremos."""
    
    def test_regime_desconhecido(self):
        """Regime desconhecido deve assumir NORMAL."""
        is_valid, reason = validar_mercado('Over 3.5', 'UNKNOWN')
        assert is_valid is False  # Proibido em NORMAL
    
    def test_regime_lowercase(self):
        """Regime em lowercase deve funcionar."""
        is_valid, reason = validar_mercado('Over 2.5', 'normal')
        assert is_valid is True
    
    def test_mercado_case_sensitive(self):
        """Mercado deve ser case-sensitive."""
        is_valid, reason = validar_mercado('over 2.5', 'NORMAL')
        assert is_valid is False  # Inválido (case errado)


# ============================================================================
# CONFIGURAÇÃO PYTEST
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
