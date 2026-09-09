#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#243 - cruza as apostas REAIS da casa com o que o sistema publicou.

Ate aqui, "o sistema erra muito" e "eu perdi dinheiro" eram duas frases sobre
populacoes diferentes: o Brier mede TODOS os picks publicados, e a aposta sai
de um subconjunto escolhido a mao, as vezes numa linha que o sistema nem
precifica. Este script junta os dois pelo `match_id` e responde, com numero:

  1. COBERTURA   — quantas apostas tem pick correspondente no ledger
  2. LINHA       — quantas foram em linha que o sistema nao publica (X.0)
  3. REVISAO     — quantas foram numa revisao que o sistema DEPOIS mudou
                   (o defeito do #238-a, agora com dinheiro em cima)
  4. DESEMPENHO  — acerto e ROI so nas linhas realmente jogadas

E o modo `--taxas`, que responde a pergunta "da para chegar a 80% de acerto?"
separando os picks COM odd real dos picks SEM preco — porque taxa de acerto
alta num mercado sem preco nao vale nada, e num mercado com preco justo vale
exatamente zero.

    python scripts/cruzar_apostas.py --exemplo apostas.csv   # gera o modelo
    python scripts/cruzar_apostas.py --apostas apostas.csv
    python scripts/cruzar_apostas.py --taxas
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RAIZ))

# Mesmo carregamento do backfill_historico.py: o DSN e a chave vivem no .env.
try:
    from dotenv import load_dotenv
    for _nome in (".env", "backend/.env"):
        if (_RAIZ / _nome).exists():
            load_dotenv(_RAIZ / _nome, override=False)
except ImportError:
    pass

_MODELO = """data,jogo,mercado,selecao,odd,stake,resultado
2026-09-07,Cruz Azul x Santos Laguna,BTTS,BTTS Yes,1.66,20.00,L
2026-09-07,Cruz Azul x Santos Laguna,Corners,Mais de 8.0,1.40,10.00,W
2026-09-05,Flamengo x Mirassol,Corners,Menos de 16.0,2.10,10.00,L
"""

# Rotulo da casa -> (market, selection) do sistema. So o que da para mapear
# sem inventar: a casa usa "Mais/Menos de X", o sistema usa Over/Under X.5.
_FAMILIA = {
    "gols": "Over/Under",
    "corners": "Corners",
    "escanteios": "Corners",
    "cartoes": "Cards",
    "cards": "Cards",
    "btts": "BTTS",
}


def _linha_da_selecao(sel: str) -> Optional[str]:
    m = re.search(r"(\d+)[.,](\d)", sel or "")
    return f"{m.group(1)}.{m.group(2)}" if m else None


def e_linha_inteira(sel: str) -> bool:
    """A casa oferece X.0 (asiatica, admite empate); o sistema so precifica X.5."""
    linha = _linha_da_selecao(sel)
    return bool(linha) and linha.endswith(".0")


def selecao_do_sistema(mercado: str, sel: str) -> Optional[str]:
    """Traduz o rotulo da casa para a `selection` do ledger, quando existe."""
    mk = _FAMILIA.get((mercado or "").strip().lower(), (mercado or "").strip())
    s = (sel or "").strip().lower()
    if mk == "BTTS":
        return "BTTS Yes" if ("sim" in s or "yes" in s) else "BTTS No"
    linha = _linha_da_selecao(sel)
    if not linha:
        return None
    lado = "Over" if ("mais" in s or "over" in s) else "Under"
    if mk == "Corners":
        return f"Corners {lado} {linha}"
    if mk == "Cards":
        return f"{lado} {linha}"
    return f"{lado} {linha}"


def _conectar():
    from backend.services.prediction_ledger import dsn_obrigatorio
    dsn = dsn_obrigatorio()
    import psycopg2
    return psycopg2.connect(dsn)


def _match_ids(cur, jogo: str) -> List[str]:
    """Acha o match_id pelos dois nomes de time, sem supor o formato do id."""
    partes = re.split(r"\s+[xX×]\s+", jogo or "")
    if len(partes) != 2:
        return []
    casa, fora = (p.strip() for p in partes)
    cur.execute(
        """SELECT DISTINCT match_id FROM prediction_ledger
            WHERE match_id ILIKE %s AND match_id ILIKE %s""",
        (f"%{casa}%", f"%{fora}%"),
    )
    return [r[0] for r in cur.fetchall()]


def cruzar(caminho: str) -> int:
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        apostas = [dict(r) for r in csv.DictReader(f)]
    if not apostas:
        print("arquivo de apostas vazio", file=sys.stderr)
        return 1

    conn = _conectar()
    cur = conn.cursor()
    linhas: List[Dict[str, Any]] = []

    for a in apostas:
        sel_sis = selecao_do_sistema(a.get("mercado", ""), a.get("selecao", ""))
        mk = _FAMILIA.get((a.get("mercado") or "").strip().lower(), (a.get("mercado") or "").strip())
        reg: Dict[str, Any] = {
            "jogo": a.get("jogo", ""), "selecao": a.get("selecao", ""),
            "mercado": mk, "sel_sistema": sel_sis,
            "odd": float(a.get("odd") or 0), "stake": float(a.get("stake") or 0),
            "resultado": (a.get("resultado") or "").strip().upper(),
            "inteira": e_linha_inteira(a.get("selecao", "")),
            "ids": _match_ids(cur, a.get("jogo", "")),
            "revisoes": [], "mudou": None, "pick": None,
        }
        if reg["ids"] and sel_sis:
            cur.execute(
                """SELECT published_at, classification, calibrated_prob, ev, book_odd
                     FROM prediction_ledger
                    WHERE match_id = ANY(%s) AND market = %s AND selection = %s
                    ORDER BY published_at""",
                (reg["ids"], mk, sel_sis),
            )
            reg["revisoes"] = cur.fetchall()
            if reg["revisoes"]:
                reg["pick"] = reg["revisoes"][-1]
                classes = {r[1] for r in reg["revisoes"]}
                reg["mudou"] = len(classes) > 1
        linhas.append(reg)

    conn.close()
    _relatorio(linhas)
    return 0


def _relatorio(L: List[Dict[str, Any]]) -> None:
    n = len(L)
    print(f"\n{n} aposta(s) lidas\n")

    print("── 1. COBERTURA: a aposta tem pick no sistema? ──")
    sem_jogo = [x for x in L if not x["ids"]]
    sem_sel = [x for x in L if x["ids"] and not x["sel_sistema"]]
    sem_pick = [x for x in L if x["ids"] and x["sel_sistema"] and not x["revisoes"]]
    com = [x for x in L if x["revisoes"]]
    for nome, g in (("jogo ausente do ledger", sem_jogo),
                    ("selecao nao traduzivel", sem_sel),
                    ("jogo existe, selecao NUNCA publicada", sem_pick),
                    ("COM pick correspondente", com)):
        print(f"  {nome:<40}{len(g):>4}  R$ {sum(x['stake'] for x in g):>8.2f}")
    if sem_pick:
        print("    linhas apostadas que o sistema nao publicou:")
        for x in sorted({(y["selecao"], y["mercado"]) for y in sem_pick}):
            print(f"      {x[1]:<10} {x[0]}")

    print("\n── 2. LINHA: X.0 da casa contra X.5 do sistema ──")
    for nome, g in (("linha INTEIRA (o sistema nao precifica)", [x for x in L if x["inteira"]]),
                    ("linha MEIA (a mesma do sistema)", [x for x in L if not x["inteira"]])):
        _bloco(nome, g)
    print("  Numa linha inteira o desfecho exato empata ou perde; na meia vizinha,")
    print("  ganha. Sao apostas diferentes, nao arredondamento.")

    print("\n── 3. REVISAO: o sistema mudou de ideia depois? (#238-a) ──")
    mudou = [x for x in L if x["mudou"]]
    print(f"  apostas cuja selecao teve MAIS DE UMA classificacao: {len(mudou)}"
          f"  R$ {sum(x['stake'] for x in mudou):>8.2f}")
    for x in mudou:
        seq = " -> ".join(f"{r[1]}({r[2]:.2f})" for r in x["revisoes"])
        print(f"    {x['jogo'][:40]:<42} {x['sel_sistema']:<22} {seq}  [{x['resultado']}]")

    print("\n── 4. DESEMPENHO nas linhas realmente jogadas ──")
    _cabecalho()
    _bloco("TODAS", L)
    _bloco("so com pick no sistema", com)
    _bloco("so linha meia + com pick", [x for x in com if not x["inteira"]])


def _cabecalho() -> None:
    print(f"  {'recorte':<40}{'n':>4}{'W':>4}{'L':>4}{'acerto':>9}{'apostado':>11}{'retorno':>10}{'ROI':>9}")


def _bloco(nome: str, g: List[Dict[str, Any]]) -> None:
    if not g:
        print(f"  {nome:<40}{0:>4}{'—':>34}")
        return
    w = [x for x in g if x["resultado"] == "W"]
    ap = sum(x["stake"] for x in g)
    ret = sum(x["stake"] * x["odd"] for x in w)
    roi = (ret - ap) / ap * 100 if ap else 0.0
    print(f"  {nome:<40}{len(g):>4}{len(w):>4}{len(g)-len(w):>4}"
          f"{len(w)/len(g)*100:>8.1f}%{ap:>11.2f}{ret:>10.2f}{roi:>+8.1f}%")


def taxas() -> int:
    """A pergunta dos 80%: acerto e ROI por mercado, COM e SEM odd real.

    Taxa de acerto alta num mercado sem preco nao e vantagem — e so uma linha
    facil. E num mercado com preco justo, 80% de acerto rende exatamente zero
    menos a margem. O que separa os dois e a odd, nao a taxa.
    """
    import json
    conn = _conectar()
    cur = conn.cursor()
    cur.execute(
        """SELECT market, predicted_probs, actual_result
             FROM audit_results
            WHERE actual_result IN ('hit','miss') AND market <> 'audit'"""
    )
    por: Dict[str, Dict[str, List]] = defaultdict(lambda: {"com": [], "sem": []})
    for market, probs, res in cur.fetchall():
        if isinstance(probs, str):
            try:
                probs = json.loads(probs)
            except Exception:
                continue
        if not isinstance(probs, dict):
            continue
        book = probs.get("book_odd")
        prob = probs.get("prob")
        # #244 - ODD CIRCULAR, teste RELATIVO. O #243 usou tolerancia ABSOLUTA
        # (|odd - 1/prob| < 0.02) e por isso subestimou o problema: numa odd de
        # 1,90 uma diferenca de 1% na probabilidade vale ~0,04 de odd e passa
        # batido. Medido com `prob * odd`, a fracao de odds derivadas da propria
        # probabilidade sobe de 47,5% para 75,6% — e chega a 100% em todos os
        # mercados de cartoes e em `Escanteios Over 7.5`, que nao tem nenhuma
        # odd de casa gravada. ROI sobre odd derivada nao mede vantagem: mede o
        # tamanho da deflacao (#244). Fica fora da coluna "com odd".
        #
        # A janela [0,95; 1,03] e o pico da distribuicao de prob*odd; acima de
        # 1,03 a distribuicao vira uma cauda plana (nenhuma faixa passa de 1,4%).
        # Falso positivo possivel: pick com preco real em que o modelo concorda
        # exatamente com a casa. Preferimos exclui-lo a contar uma odd circular.
        produto = float(book) * float(prob) if (book and prob) else None
        circular = produto is not None and 0.95 <= produto <= 1.03
        alvo = "com" if (book and not circular) else "sem"
        por[market][alvo].append((res == "hit", float(book or 0), float(prob or 0)))
    conn.close()

    print("\nTaxa de acerto e retorno por mercado — o que muda quando existe PRECO")
    print("(ROI simulado com a odd real; mercados sem preco nao tem ROI possivel)")
    # #244: AVISO OBRIGATORIO. A fonte desta tabela e o `audit_results`, que o
    # #200 documenta como prognostico RECOMPUTADO POS-JOGO. Medido: os picks de
    # `Escanteios Over 11.5` caem em jogos de 13,6 escanteios em media e acertam
    # 78,8% — o modelo "escolhe" o lado certo porque ja viu o jogo. Acerto e ROI
    # desta tabela sao um teto sem sentido; servem so para comparar COM x SEM
    # preco dentro do mesmo mercado. Numero limpo: prediction_ledger (pre-jogo).
    print("AVISO (#200/#244): audit_results e recomputado pos-jogo — acerto e")
    print("ROI aqui estao contaminados. Use so a comparacao COM x SEM preco.\n")
    print(f"{'mercado':<26}{'n c/odd':>8}{'acerto':>8}{'odd med':>9}{'ROI':>9}   |"
          f"{'n s/odd':>8}{'acerto':>8}")
    print("-" * 92)
    tot_n = tot_ap = tot_ret = 0
    for market in sorted(por, key=lambda m: -(len(por[m]["com"]) + len(por[m]["sem"]))):
        com, sem = por[market]["com"], por[market]["sem"]
        if len(com) + len(sem) < 20:      # #079 MIN_N_BRIER
            continue
        if com:
            acerto = sum(1 for h, _, _ in com if h) / len(com) * 100
            odd_med = sum(o for _, o, _ in com) / len(com)
            ret = sum(o for h, o, _ in com if h)
            roi = (ret - len(com)) / len(com) * 100
            tot_n += len(com); tot_ap += len(com); tot_ret += ret
            c = f"{len(com):>8}{acerto:>7.1f}%{odd_med:>9.2f}{roi:>+8.1f}%"
        else:
            c = f"{0:>8}{'—':>8}{'—':>9}{'—':>9}"
        s = (f"{len(sem):>8}{sum(1 for h, _, _ in sem if h)/len(sem)*100:>7.1f}%"
             if sem else f"{0:>8}{'—':>8}")
        print(f"{market[:25]:<26}{c}   |{s}")
    if tot_ap:
        print("-" * 92)
        print(f"{'TOTAL com odd real':<26}{tot_n:>8}{'':>8}{'':>9}"
              f"{(tot_ret-tot_ap)/tot_ap*100:>+8.1f}%")
    print("\nLeitura: a coluna que decide lucro e a ODD, nao o acerto. Um mercado de")
    print("80% pago a 1,20 rende -4%; um de 55% pago a 2,00 rende +10%. Perseguir")
    print("taxa de acerto leva a linhas faceis e baratas — Over 0.5 acerta ~94%.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apostas", help="CSV com as apostas reais da casa")
    ap.add_argument("--exemplo", metavar="ARQUIVO", help="escreve um CSV modelo e sai")
    ap.add_argument("--taxas", action="store_true",
                    help="acerto e ROI por mercado, com e sem odd real (audit_results)")
    args = ap.parse_args()

    if args.exemplo:
        Path(args.exemplo).write_text(_MODELO, encoding="utf-8")
        print(f"modelo escrito em {args.exemplo}")
        print("colunas: data,jogo,mercado,selecao,odd,stake,resultado (W/L)")
        print("  jogo    = 'Casa x Fora', com os nomes como aparecem no sistema")
        print("  mercado = gols | escanteios | cartoes | btts")
        print("  selecao = o rotulo da casa, ex.: 'Mais de 8.0', 'Menos de 2.5'")
        return 0
    if args.taxas:
        return taxas()
    if args.apostas:
        return cruzar(args.apostas)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
