"""Test #179 — band 50-60% recalibration.

#189-a PROMOVEU o shadow: o valor recalibrado da banda 50-60% (0.05 no
centro, era 0.12) foi embutido nos nós de produção (`_band_deflation`), e a
flag SHADOW_BAND_50_60_V179 ficou inerte — o endpoint /metrics/shadow_v179
passou a reportar improvement 0 por construção.

#240 devolveu conteúdo ao braço: a mesma máquina (flag, persistência,
endpoint, gate de 3%) passa a carregar o candidato `_SHADOW_KNOTS_V179`
(nó de 0.65 → 0.10; produção 0.15). O caminho live continua intocado — quem
gateia é a flag, desligada por padrão.
"""
import importlib
import os


def _reload_ev():
    """Re-import ev_classification so any env flag is re-read."""
    import backend.services.ev_classification as ev
    importlib.reload(ev)
    return ev


def test_shadow_identico_ao_live_flag_off():
    os.environ.pop("SHADOW_BAND_50_60_V179", None)
    ev = _reload_ev()
    for p in [0.30, 0.45, 0.55, 0.65, 0.75, 0.85]:
        cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
        assert abs(cur - shadow) < 1e-9, f"prob={p}: cur={cur}, shadow={shadow}"


def test_shadow_diverge_do_live_com_flag_on():
    """#240: com a flag ligada o braco tem de MEDIR alguma coisa.

    Ate o #240 este teste afirmava `shadow == live` tambem com a flag ligada,
    o que registrava a promocao concluida do #189-a. Com o candidato do #240
    no braco, a afirmacao se inverte: se voltar a empatar, o endpoint reporta
    improvement 0 por construcao e a janela de duas semanas do #179 passa
    medindo nada — falha silenciosa, exatamente a classe do #226.

    Fora da faixa do candidato (0.55 < p < 0.75) os dois seguem iguais.
    """
    os.environ["SHADOW_BAND_50_60_V179"] = "true"
    try:
        ev = _reload_ev()

        for p in [0.45, 0.55, 0.75, 0.85]:
            cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
            assert abs(cur - shadow) < 1e-9, (
                f"fora da faixa do candidato (p={p}) devia empatar: {cur} vs {shadow}"
            )

        for p in [0.60, 0.638, 0.65, 0.70]:
            cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
            assert shadow > cur + 1e-9, (
                f"p={p}: shadow devia publicar MAIS que live ({shadow} vs {cur}) — "
                f"empate aqui significa braco inerte"
            )

        # o alvo medido: raw 0.638 publica 55.0% hoje; o candidato leva a ~57.8%
        cur, shadow = ev.apply_probability_deflation_with_shadow(0.638, "")
        assert abs(cur - 0.550) < 0.005, f"live mudou: {cur}"
        assert abs(shadow - 0.578) < 0.005, f"shadow fora do previsto: {shadow}"
    finally:
        os.environ.pop("SHADOW_BAND_50_60_V179", None)
        _reload_ev()


def test_banda_50_60_promovida_menos_deflacao_que_105():
    """O centro da banda usa 0.05 (promovido); era 0.12 no #105."""
    ev = _reload_ev()
    cur, _ = ev.apply_probability_deflation_with_shadow(0.55, "")
    assert abs(cur - 0.55 * (1 - 0.05)) < 1e-9
    assert cur > 0.55 * (1 - 0.12)


def test_min_n_floor_in_endpoint():
    """Endpoint must respect MIN_N=20 (regra #079) before reporting improvement."""
    from backend.services.brier_service import MIN_N
    assert MIN_N == 20  # regra #079 preserved
