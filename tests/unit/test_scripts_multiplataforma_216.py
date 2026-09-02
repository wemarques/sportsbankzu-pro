# -*- coding: utf-8 -*-
"""#216 - os scripts tem de achar a raiz do repo no Windows tambem.

`__file__.rsplit("/scripts/", 1)[0]` nao casa com barra invertida: no Windows o
`sys.path` recebia o caminho do ARQUIVO em vez da raiz, e o `import backend`
falhava. Medido em 01/09/2026 — o comparador do #215 so rodou com PYTHONPATH
definido na mao.
"""
import os
import re
import subprocess
import sys

SCRIPTS = ("scripts/comparar_ancora.py", "scripts/verificar_manifesto.py")


def _fonte(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _codigo(p):
    """Fonte sem linhas de comentario — o defeito e o uso, nao a mencao a ele."""
    return "\n".join(l for l in _fonte(p).splitlines() if not l.lstrip().startswith("#"))


def test_nenhum_script_usa_o_rsplit_de_barra():
    for p in SCRIPTS:
        assert 'rsplit("/scripts/"' not in _codigo(p), f"{p} ainda quebra no Windows"


def test_todos_usam_dirname_absoluto():
    for p in SCRIPTS:
        assert "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))" in _codigo(p), p


def test_a_raiz_resolvida_e_a_do_repo():
    """dirname duas vezes sobre scripts/x.py tem de dar a raiz, nos dois sistemas."""
    for sep, caminho in (
        ("/", "/home/user/sportsbankzu-pro/scripts/comparar_ancora.py"),
        ("\\", r"C:\painel_apostas\sportsbank-pro\sportsbankzu-pro\scripts\comparar_ancora.py"),
    ):
        # ntpath/posixpath diretamente, para o teste valer nos dois sistemas
        mod = __import__("ntpath" if sep == "\\" else "posixpath")
        raiz = mod.dirname(mod.dirname(caminho))
        assert raiz.endswith("sportsbankzu-pro"), (sep, raiz)
        assert not raiz.endswith(".py")


def test_script_roda_sem_pythonpath():
    """O teste que reproduz o defeito: sem PYTHONPATH, de outro diretorio."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run(
        [sys.executable, os.path.join(raiz, "scripts", "verificar_manifesto.py")],
        capture_output=True, text=True, env=env, cwd=os.sep,
    )
    assert r.returncode == 0, r.stderr
    assert "Manifesto FootyStats" in r.stdout
