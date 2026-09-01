# -*- coding: utf-8 -*-
"""#215 - compara probabilidade crua, calibrada e ancora empirica.

A pergunta que ficou aberta desde o #200: os calibradores treinados sobre o
`audit_results` vazado ajudam ou atrapalham? Ate agora era opiniao. A FootyStats
entrega a distribuicao empirica por linha (`overXX_..._percentage`) - quantos
por cento dos jogos daqueles dois times passaram de cada linha. Isso e contagem,
nao modelo, e serve de terceira opiniao.

O caso que motivou (Londrina x Juventude, 01/09/2026, cartoes):

    linha        empirico   crua    calibrada
    Over 2.5       82%      74,7%     59,9%      calibrador AFASTOU 22pp
    Under 4.5      54%      60,9%     52-54%     calibrador aproximou

O calibrador nao esta calibrando - esta deflacionando tudo na mesma direcao.
Numa linha o erro do lambda e o do calibrador se cancelaram; na outra se
somaram. Este modulo transforma essa observacao em medida sobre N jogos.

Nao decide nada sozinho. Devolve os desvios; a decisao de quarentenar os .pkl
continua sendo humana.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

# mercado publicado -> (familia, prefixo do campo empirico da FootyStats)
_FAMILIAS = {
    "escanteios": ("corners", "over{}_corners_percentage"),
    "cartoes":    ("cards",   "over{}_cards_percentage"),
    "cartões":    ("cards",   "over{}_cards_percentage"),
}


@dataclass
class Linha:
    jogo: str
    liga: str
    mercado: str
    lado: str            # "over" ou "under"
    empirico: float      # 0-100
    crua: Optional[float]
    calibrada: Optional[float]

    @property
    def erro_cru(self) -> Optional[float]:
        return None if self.crua is None else self.crua - self.empirico

    @property
    def erro_calibrado(self) -> Optional[float]:
        return None if self.calibrada is None else self.calibrada - self.empirico

    def linha(self) -> str:
        c = "  -  " if self.crua is None else f"{self.crua:5.1f}%"
        k = "  -  " if self.calibrada is None else f"{self.calibrada:5.1f}%"
        return (f"{self.jogo[:34]:<34} {self.mercado[:24]:<24} "
                f"emp={self.empirico:5.1f}%  crua={c}  calib={k}")


@dataclass
class Comparacao:
    linhas: List[Linha] = field(default_factory=list)
    sem_ancora: int = 0

    def _erros(self, atributo: str) -> List[float]:
        return [v for v in (getattr(l, atributo) for l in self.linhas) if v is not None]

    def resumo(self) -> Dict[str, Any]:
        cru, cal = self._erros("erro_cru"), self._erros("erro_calibrado")
        def bloco(v):
            if not v:
                return None
            return {
                "n": len(v),
                "vies_medio": round(statistics.mean(v), 1),
                "erro_absoluto_medio": round(statistics.mean(abs(x) for x in v), 1),
                "mediana": round(statistics.median(v), 1),
            }
        return {"linhas": len(self.linhas), "sem_ancora": self.sem_ancora,
                "crua": bloco(cru), "calibrada": bloco(cal)}

    def veredito(self) -> str:
        r = self.resumo()
        if not r["crua"] or not r["calibrada"]:
            return "amostra insuficiente para veredito"
        c, k = r["crua"]["erro_absoluto_medio"], r["calibrada"]["erro_absoluto_medio"]
        if k < c:
            return f"o calibrador APROXIMA da ancora ({k:.1f}pp contra {c:.1f}pp da crua)"
        if k > c:
            return f"o calibrador AFASTA da ancora ({k:.1f}pp contra {c:.1f}pp da crua)"
        return "empate"


def _linha_do_mercado(nome: str) -> Optional[Tuple[str, str, float]]:
    """'Escanteios Over 8.5' -> ('corners', 'over', 8.5)."""
    baixo = nome.lower()
    fam = next((v for k, v in _FAMILIAS.items() if baixo.startswith(k)), None)
    if not fam:
        return None
    lado = "over" if " over " in f" {baixo} " else ("under" if " under " in f" {baixo} " else None)
    if not lado:
        return None
    m = re.search(r"(\d+[.,]?\d*)", baixo.split(lado)[-1])
    if not m:
        return None
    return fam[0], lado, float(m.group(1).replace(",", "."))


def _ancora(stats: Dict[str, Any], familia: str, valor: float) -> Optional[float]:
    """Percentual empirico de Over <valor> para a familia. 8.5 -> over85_..."""
    chave = f"over{str(valor).replace('.', '').replace(',', '')}_"
    chave += "corners_percentage" if familia == "corners" else "cards_percentage"
    v = stats.get(chave)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def comparar(jogos: Iterable[Dict[str, Any]]) -> Comparacao:
    """Confronta cada mercado publicado com a contagem empirica da FootyStats."""
    out = Comparacao()
    for j in jogos:
        stats = j.get("stats") or {}
        rot = (f"{(j.get('homeTeam') or {}).get('name','?')} x "
               f"{(j.get('awayTeam') or {}).get('name','?')}")
        for mk in (j.get("mercados") or []):
            nome = str(mk.get("mercado", ""))
            alvo = _linha_do_mercado(nome)
            if not alvo:
                continue
            familia, lado, valor = alvo
            emp_over = _ancora(stats, familia, valor)
            if emp_over is None:
                out.sem_ancora += 1
                continue
            # a ancora e sempre de Over; para Under, complementa
            empirico = emp_over if lado == "over" else 100.0 - emp_over
            crua = mk.get("raw_probability")
            cal = mk.get("calibrated_probability")
            out.linhas.append(Linha(
                jogo=rot, liga=j.get("leagueId", "?"), mercado=nome, lado=lado,
                empirico=empirico,
                crua=None if crua is None else float(crua) * 100,
                calibrada=None if cal is None else float(cal) * 100,
            ))
    return out
