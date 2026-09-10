# -*- coding: utf-8 -*-
"""Ensaio do primeiro ciclo da camada de calibragem — LE, NAO ESCREVE (#249).

Roda exatamente a computacao de `ciclo.executar` contra o banco de producao e
imprime o que o primeiro ciclo FARIA: o `(a, b)` proposto por celula, o status
que a governanca daria, o fator de encurtamento, o movimento maximo em pontos
de probabilidade e os quatro limiares re-derivados. No fim, a contagem de
picks por classe ANTES e DEPOIS — o numero que decide se ligar a camada
mantem o volume publicado ou o dobra.

Nao escreve nada, por construcao:
  * nao chama `gravar_ciclo` nem `garantir_tabela` (nenhum DDL, nenhum INSERT);
  * so usa `planejar`, que e o mesmo miolo de `executar`, e cujas idas ao
    banco sao SELECTs (`ultimo_status_de_ciclo`, `carregar_anterior`);
  * uma guarda em tempo de execucao substitui `gravar_ciclo`,
    `garantir_tabela` e `garantir_indice_vigente_unico` por funcoes que
    levantam — se um refactor futuro fizer o ciclo escrever, o ensaio quebra
    em vez de escrever em producao.

Independe de `CALIBRAGEM_ENABLED`: a chave governa a ESCRITA, e aqui nao ha
escrita. E justamente com a camada desligada que este ensaio serve para algo.

Uso:
    python scripts/ensaio_calibragem.py
    python scripts/ensaio_calibragem.py --semente caminho/do/backfill.json
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:                                            # noqa: BLE001
    pass

from backend.modeling.calibragem import ciclo, curva, estimador, limiares, repositorio


def _proibir_escrita():
    """Nenhum caminho deste script pode gravar. A guarda e executavel."""
    def _bloqueado(*_a, **_k):
        raise AssertionError(
            "ensaio_calibragem.py tentou ESCREVER no banco. O ensaio le e "
            "imprime; gravar e o ciclo de producao, com CALIBRAGEM_ENABLED.")
    repositorio.gravar_ciclo = _bloqueado
    repositorio.garantir_tabela = _bloqueado
    repositorio.garantir_indice_vigente_unico = _bloqueado


def _movimento_pp(vig, resultado) -> float:
    """Quanto a curva anda, em pontos de probabilidade, no pior ponto."""
    if resultado["a"] is None or vig["a"] is None:
        return float("nan")
    return 100.0 * curva.distancia_maxima(
        vig["a"], vig["b"], resultado["a"], resultado["b"])


def _fmt(x, casas=4):
    return "-" if x is None else f"{x:.{casas}f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--semente", default=None,
                   help="caminho do backfill (mesmo argumento de executar)")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    _proibir_escrita()

    print("=" * 78)
    print("ENSAIO DO PRIMEIRO CICLO — somente leitura, nada e gravado")
    print("=" * 78)

    picks = repositorio.carregar_amostra()
    jogos = len({pk.match_id for pk in picks})
    com_odd = sum(1 for pk in picks if pk.odd)
    print(f"amostra: {len(picks)} picks | {jogos} jogos | "
          f"{com_odd} com odd ({com_odd / max(len(picks), 1):.1%})")

    ajuste = estimador.ajustar_hierarquico(picks)
    if args.semente:
        semente_picks = repositorio.carregar_semente_backfill(args.semente)
        if semente_picks:
            conc, n_sobrepostos = estimador.medir_concordancia(semente_picks, picks)
            n_prior, status = estimador.n_prior_da_concordancia(conc, n_sobrepostos)
            print(f"semente: {len(semente_picks)} picks | concordancia={conc:.4f} "
                  f"| n_prior={n_prior} ({status})")
            ajuste = estimador.aplicar_semente(
                ajuste, estimador.ajustar_hierarquico(semente_picks), n_prior)

    vigentes = repositorio.carregar_vigentes()
    print(f"celulas vigentes hoje no banco: {len(vigentes)}")

    plano = ciclo.planejar(picks, ajuste, vigentes)
    decisoes = plano["decisoes"]
    novos = plano["limiares"]
    atuais = plano["limiares_atuais"]

    print()
    print("-" * 78)
    print("CELULAS  (limiares so nas celulas-familia: a re-derivacao e por "
          "familia)")
    print("-" * 78)
    cab = (f"{'familia':<14}{'liga':<22}{'jogos':>6} {'a':>8}{'b':>8}"
           f"  {'status':<12}{'fator':>7}{'mov.pp':>8}")
    print(cab)
    for (familia, liga), dec in sorted(decisoes.items()):
        r = dec["resultado"]
        print(f"{familia:<14}{(liga or '(familia)'):<22}{dec['n_jogos']:>6} "
              f"{_fmt(r['a'], 3):>8}{_fmt(r['b'], 3):>8}  {r['status']:<12}"
              f"{_fmt(r.get('fator_encurtamento'), 2):>7}"
              f"{_movimento_pp(dec['vig'], r):>8.2f}")
        if liga:
            continue
        lim_novo = novos.get(familia, {})
        lim_atual = atuais.get(familia, {})
        for campo in limiares.CAMPOS:
            antes, depois = lim_atual.get(campo), lim_novo.get(campo)
            marca = "  (inalterado)" if antes == depois else ""
            print(f"    {campo:<12} {_fmt(antes)} -> {_fmt(depois)}{marca}")
        print(f"    motivo: {r.get('motivo', '')}")

    c = plano["contadores"]
    print()
    print("-" * 78)
    print("RESUMO")
    print("-" * 78)
    print(f"celulas={c['celulas']} adotadas={c['adotadas']} "
          f"encurtadas={c['encurtadas']} revertidas={c['revertidas']} "
          f"congeladas={c['congeladas']}")

    antes = limiares.contar_por_classe(picks, plano["parametros_antigos"], atuais)
    depois_sem = limiares.contar_por_classe(picks, plano["parametros_novos"], atuais)
    depois_com = limiares.contar_por_classe(picks, plano["parametros_novos"], novos)

    print()
    print("CONTAGEM DE PICKS POR CLASSE — o numero que decide")
    print(f"{'familia':<14}{'':<4}{'hoje':>16}{'curva nova,':>16}"
          f"{'curva nova,':>16}")
    print(f"{'':<18}{'(versao 0)':>16}{'limiar velho':>16}"
          f"{'limiar novo':>16}")
    total = [0, 0, 0]
    for familia in sorted(set(antes) | set(depois_sem) | set(depois_com)):
        a = antes.get(familia, {"safe": 0, "neutro": 0})
        b = depois_sem.get(familia, {"safe": 0, "neutro": 0})
        d = depois_com.get(familia, {"safe": 0, "neutro": 0})
        for i, x in enumerate((a, b, d)):
            total[i] += x["safe"] + x["neutro"]
        print(f"{familia:<14}{'safe':<4}{a['safe']:>16}{b['safe']:>16}"
              f"{d['safe']:>16}")
        print(f"{'':<14}{'neu':<4}{a['neutro']:>16}{b['neutro']:>16}"
              f"{d['neutro']:>16}")
    print(f"{'TOTAL':<18}{total[0]:>16}{total[1]:>16}{total[2]:>16}")

    delta = total[2] - total[0]
    print()
    if delta == 0:
        print("VOLUME CONSTANTE: a re-derivacao devolveu exatamente o volume "
              "de hoje.")
    else:
        print(f"VOLUME: {total[0]} -> {total[2]} ({delta:+d}). Residuo "
              f"esperado vem de EMPATES exatos no quantil de corte (`>=` leva "
              f"o bloco inteiro); ver `limiares._arredondar_para_baixo`.")
    print(f"Sem a re-derivacao o volume seria {total[1]} "
          f"({total[1] - total[0]:+d}) — e por isso que os limiares "
          f"re-derivados tem de ser LIDOS.")
    print()
    print("NADA FOI GRAVADO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
