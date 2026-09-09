"""#189-a — deflação contínua por interpolação linear entre nós.

Auditoria 2026-08-29: a função-degrau do #105 era não-monotônica nas
fronteiras de banda — raw 59.9% exibia prob deflacionada 52.7% enquanto
raw 60.0% exibia 51.0% (quedas de até 4pp em 0.70/0.80). Um pick MELHOR
mostrava prob e EV PIORES, e com o floor de EV (<1% descarta, #165) a
classificação podia inverter.

O nó de 0.55 (centro da banda 50-60%) usa 0.05 — promoção do shadow #179
(banda subconfiante em -12.7pp com a deflação antiga de 0.12).
"""
import pytest

from backend.services.ev_classification import (
    _DEFLATION_KNOTS,
    _band_deflation,
    _band_deflation_v179_shadow,
    apply_probability_deflation,
)


def test_monotonicidade_sem_violacoes():
    """p*(1-d(p)) deve ser estritamente crescente em todo o domínio útil."""
    prev = 0.0
    for i in range(500, 9800):
        p = i / 10000.0
        d = apply_probability_deflation(p)
        assert d >= prev - 1e-12, (
            f"violação de monotonicidade em raw={p:.4f}: {prev:.6f} -> {d:.6f}"
        )
        prev = d


def test_continuidade_sem_saltos():
    """Sem descontinuidades: passos de 1e-4 nunca mudam a deflação em mais de 2e-3."""
    for i in range(4000, 9500):
        p0, p1 = i / 10000.0, (i + 1) / 10000.0
        assert abs(_band_deflation(p1) - _band_deflation(p0)) < 2e-3


def test_valores_nos_nos():
    for x, y in _DEFLATION_KNOTS:
        assert _band_deflation(x) == pytest.approx(y, abs=1e-12)


def test_extremos_constantes():
    assert _band_deflation(0.10) == pytest.approx(0.10)
    assert _band_deflation(0.45) == pytest.approx(0.10)
    assert _band_deflation(0.90) == pytest.approx(0.25)
    assert _band_deflation(0.99) == pytest.approx(0.25)


def test_banda_50_60_recalibrada_menos_agressiva_que_105():
    """No centro da banda, a deflação promovida (#179) é 0.05 (era 0.12)."""
    assert _band_deflation(0.55) == pytest.approx(0.05)
    # deflacionado novo > deflacionado antigo em toda a banda 50-60
    for p in (0.50, 0.52, 0.55, 0.58, 0.599):
        assert p * (1 - _band_deflation(p)) > p * (1 - 0.12)


def test_fronteiras_antigas_sem_queda():
    """Os pontos que antes caíam (0.50/0.60/0.70/0.80) agora sobem."""
    for b in (0.50, 0.60, 0.70, 0.80):
        lo = apply_probability_deflation(b - 0.0001)
        hi = apply_probability_deflation(b)
        assert hi >= lo, f"fronteira {b}: {lo:.6f} -> {hi:.6f}"


def test_shadow_diverge_so_na_faixa_prevista_e_nao_toca_a_producao():
    """#240 — o braco shadow voltou a ter conteudo; a guarda muda de alvo.

    Ate aqui este teste afirmava `shadow == live` incondicionalmente, correto
    enquanto a promocao do #189-a deixara o braco inerte. Reusar a maquina do
    #179 (flag, persistencia, endpoint, gate) para o candidato do #240 derruba
    essa afirmacao por construcao.

    Apagar a guarda seria pior que mante-la desatualizada: sem ela nada impede
    o conjunto shadow de vazar para o caminho live. O que ela protege agora:

      1. os nos de PRODUCAO nao mudaram;
      2. fora de 0.55 < p < 0.75 shadow e live coincidem exatamente;
      3. dentro dessa faixa o candidato deflaciona MENOS — se voltar a
         empatar, o braco ficou inerte de novo e a medicao morre calada.
    """
    assert _DEFLATION_KNOTS == [
        (0.45, 0.10), (0.55, 0.05), (0.65, 0.15), (0.75, 0.20), (0.85, 0.25)
    ], "os nos de producao nao podem mudar por causa do braco shadow"

    for p in (0.30, 0.45, 0.55, 0.75, 0.85, 0.95):
        assert _band_deflation_v179_shadow(p) == pytest.approx(_band_deflation(p)), (
            f"fora da faixa do candidato (p={p}) shadow tem de ser igual ao live"
        )

    for p in (0.60, 0.638, 0.65, 0.70):
        assert _band_deflation_v179_shadow(p) < _band_deflation(p), (
            f"em p={p} o candidato devia deflacionar MENOS que producao"
        )


def test_nos_shadow_preservam_monotonicidade():
    """#189-a vale para o candidato tambem: p*(1-d(p)) nao pode decrescer.

    Foi esta propriedade que rejeitou 0.65 -> 0.05 (quebra em p=0.650) e fixou
    o candidato do #240 em 0.10.
    """
    prev = -1.0
    for i in range(300, 10000):
        p = i / 10000.0
        v = p * (1.0 - _band_deflation_v179_shadow(p))
        assert v >= prev - 1e-12, f"nao-monotonico em p={p:.4f}: {v:.6f} < {prev:.6f}"
        prev = v


def test_piso_e_fator_liga_preservados():
    assert apply_probability_deflation(0.01) == pytest.approx(0.05)  # piso 0.05
    sem_liga = apply_probability_deflation(0.70)
    com_liga = apply_probability_deflation(0.70, "brasileirao-serie-a")
    assert com_liga == pytest.approx(sem_liga * 0.90)
