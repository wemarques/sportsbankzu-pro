"""
Testes visuais basicos para validar componentes da interface.
"""
import pytest
from streamlit.testing.v1 import AppTest


def test_app_loads():
    """Testa se a aplicacao carrega sem erros."""
    at = AppTest.from_file("app.py")
    at.run()
    assert not at.exception


def test_title_present():
    """Testa se o titulo principal esta presente."""
    at = AppTest.from_file("app.py")
    at.run()
    assert "SportsBank Pro" in str(at.title)


def test_backend_url_displayed():
    """Testa se a URL do backend e exibida."""
    at = AppTest.from_file("app.py")
    at.run()
    captions = [c.value for c in at.caption]
    assert any("Backend:" in c for c in captions)


def test_filters_present():
    """Testa se os filtros de liga e data estao presentes."""
    at = AppTest.from_file("app.py")
    at.run()
    assert len(at.multiselect) > 0
    assert len(at.radio) > 0


def test_quadro_resumo_section():
    """Testa se a secao de Quadro-Resumo esta presente."""
    at = AppTest.from_file("app.py")
    at.run()
    subheaders = [s.value for s in at.subheader]
    assert any("Quadro-Resumo" in s for s in subheaders)


def test_checkboxes_present():
    """Testa se os checkboxes de visualizacao estao presentes."""
    at = AppTest.from_file("app.py")
    at.run()
    assert len(at.checkbox) >= 4


def test_buttons_present():
    """Testa se os botoes principais estao presentes."""
    at = AppTest.from_file("app.py")
    at.run()
    buttons = [b.label for b in at.button]
    assert any("Buscar" in b for b in buttons)
    assert any("Gerar" in b for b in buttons)
    assert any("Analisar" in b for b in buttons)


def test_responsive_css_present():
    """Testa se o CSS de responsividade esta presente."""
    at = AppTest.from_file("app.py")
    at.run()
    markdowns = [m.value for m in at.markdown]
    has_responsive_css = any("@media" in m for m in markdowns)
    assert has_responsive_css


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
