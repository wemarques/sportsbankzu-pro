# -*- coding: utf-8 -*-
"""#209 - auditor de premissas.

Toda analise que fizemos deste sistema terminou do mesmo jeito: achando um lugar
onde ele nao faz o que se supoe que faz, ou onde le um dado e nao usa. O padrao
nao e falta de cuidado - e falta de um contrato executavel. Os testes unitarios
provam que cada funcao faz o que ela promete isoladamente; ninguem verificava se
a SAIDA MONTADA obedece as premissas do modelo.

Este modulo faz isso. Recebe a lista de jogos que o /fixtures devolve e devolve
as violacoes. Nao chama API nenhuma, nao depende de resultado de jogo, e roda em
milissegundos - entao serve igualmente no CI, no cron e sob demanda.

Cada premissa esta escrita como uma afirmacao falsificavel, com o numero exato
que a falsifica. Quando uma premissa mudar, muda aqui e o CI cobra.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Iterable, List, Optional

SEV_CRITICO = "critico"      # numero impossivel; o sistema esta mentindo
SEV_ALTO = "alto"            # premissa do modelo violada
SEV_MEDIO = "medio"          # diagnostico degradado, saida ainda plausivel

LAMBDA_MIN, LAMBDA_MAX = 0.5, 4.5
RHO = -0.10


@dataclass
class Violacao:
    premissa: str
    severidade: str
    jogo: str
    liga: str
    detalhe: str
    esperado: Optional[str] = None
    observado: Optional[str] = None

    def linha(self) -> str:
        base = f"[{self.severidade.upper()}] {self.premissa} | {self.liga} | {self.jogo} | {self.detalhe}"
        if self.esperado is not None:
            base += f" (esperado {self.esperado}, observado {self.observado})"
        return base


@dataclass
class Relatorio:
    jogos: int = 0
    violacoes: List[Violacao] = field(default_factory=list)
    premissas_rodadas: List[str] = field(default_factory=list)

    @property
    def criticas(self) -> List[Violacao]:
        return [v for v in self.violacoes if v.severidade == SEV_CRITICO]

    @property
    def ok(self) -> bool:
        return not self.criticas

    def resumo(self) -> str:
        if not self.violacoes:
            return f"{self.jogos} jogos, {len(self.premissas_rodadas)} premissas, nenhuma violacao."
        por_sev: Dict[str, int] = {}
        for v in self.violacoes:
            por_sev[v.severidade] = por_sev.get(v.severidade, 0) + 1
        partes = ", ".join(f"{n} {s}" for s, n in sorted(por_sev.items()))
        return f"{self.jogos} jogos, {len(self.premissas_rodadas)} premissas, {len(self.violacoes)} violacoes ({partes})."

    def para_dict(self) -> Dict[str, Any]:
        return {
            "jogos": self.jogos,
            "ok": self.ok,
            "resumo": self.resumo(),
            "premissas": self.premissas_rodadas,
            "violacoes": [asdict(v) for v in self.violacoes],
        }


# ── matematica de referencia (independente do codigo de producao) ────
# De proposito reimplementada aqui: um auditor que chama a funcao auditada nao
# audita nada. Se as duas divergirem, e exatamente isso que queremos saber.

def p_over25(lambda_total: float) -> float:
    lt = lambda_total
    return 1 - math.exp(-lt) * (1 + lt + lt * lt / 2)


def p_btts(lh: float, la: float) -> float:
    return (1 - math.exp(-lh)) * (1 - math.exp(-la))


def _tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def p_1x2(lh: float, la: float, rho: float = RHO, n: int = 12):
    """Devolve (casa, empate, fora) em percentual, com correcao de Dixon-Coles."""
    H = D = A = 0.0
    for h in range(n):
        ph = math.exp(-lh) * lh ** h / math.factorial(h)
        for a in range(n):
            p = ph * math.exp(-la) * la ** a / math.factorial(a) * _tau(h, a, lh, la, rho)
            if h > a:
                H += p
            elif h == a:
                D += p
            else:
                A += p
    t = H + D + A
    return H / t * 100, D / t * 100, A / t * 100


def lambda_minimo_para(prob_alvo: float, mercado: str) -> float:
    """Menor lambda TOTAL que sustenta `prob_alvo` no mercado dado."""
    lo, hi = 0.01, 20.0
    f = {"over25": p_over25, "btts_simetrico": lambda l: p_btts(l / 2, l / 2)}[mercado]
    for _ in range(200):
        m = (lo + hi) / 2
        if f(m) < prob_alvo:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# ── premissas ────────────────────────────────────────────────────────

def _stats(j: Dict[str, Any]) -> Dict[str, Any]:
    return j.get("stats") or {}


def _rotulo(j: Dict[str, Any]) -> str:
    h = (j.get("homeTeam") or {}).get("name", "?")
    a = (j.get("awayTeam") or {}).get("name", "?")
    return f"{h} x {a}"


def _lambdas(j) -> Optional[tuple]:
    s = _stats(j)
    lh, la = s.get("lambdaHome"), s.get("lambdaAway")
    if not isinstance(lh, (int, float)) or not isinstance(la, (int, float)):
        return None
    if lh <= 0 or la <= 0:
        return None
    return float(lh), float(la)


def premissa_over_bate_com_lambda(jogos, tol_pp=3.0):
    """O Over 2.5 exibido tem de sair da matriz do lambda exibido."""
    for j in jogos:
        par = _lambdas(j)
        s = _stats(j)
        mostrado = s.get("over25Prob")
        if not par or not isinstance(mostrado, (int, float)):
            continue
        esperado = p_over25(par[0] + par[1]) * 100
        if abs(esperado - mostrado) > tol_pp:
            yield Violacao(
                "over_bate_com_lambda", SEV_CRITICO, _rotulo(j), j.get("leagueId", "?"),
                f"Over 2.5 nao sai do lambda {par[0]:.2f}+{par[1]:.2f}",
                f"{esperado:.1f}%", f"{mostrado:.1f}%",
            )


def premissa_btts_bate_com_lambda(jogos, tol_pp=2.0):
    """O BTTS de Poisson exibido tem de sair dos mesmos lambdas."""
    for j in jogos:
        par = _lambdas(j)
        s = _stats(j)
        mostrado = s.get("bttsProb")
        if not par or not isinstance(mostrado, (int, float)):
            continue
        esperado = p_btts(*par) * 100
        if abs(esperado - mostrado) > tol_pp:
            yield Violacao(
                "btts_bate_com_lambda", SEV_CRITICO, _rotulo(j), j.get("leagueId", "?"),
                f"BTTS nao sai do lambda {par[0]:.2f}x{par[1]:.2f}",
                f"{esperado:.1f}%", f"{mostrado:.1f}%",
            )


def premissa_fusao_nao_ultrapassa_o_lambda(jogos, folga_pp=15.0, jogos_min=8):
    """A fusao pode discordar do Poisson, mas nao inventar evidencia.

    Com temporada curta, uma taxa de 100% apurada em 3 jogos nao e um fato -
    e ruido. Foi assim que seis jogos de 01/09 atravessaram o corte SAFE de
    75% com lambdas que exigiriam 2,01 dos dois lados.
    """
    for j in jogos:
        par = _lambdas(j)
        s = _stats(j)
        fus = s.get("bttsFusionProb")
        if not par or not isinstance(fus, (int, float)):
            continue
        base = p_btts(*par) * 100
        gp = s.get("matchesPlayed_overall")
        amostra_curta = isinstance(gp, (int, float)) and gp < jogos_min
        if fus - base > folga_pp:
            yield Violacao(
                "fusao_nao_ultrapassa_o_lambda",
                SEV_ALTO if amostra_curta else SEV_MEDIO,
                _rotulo(j), j.get("leagueId", "?"),
                f"fusao de BTTS {fus - base:+.1f}pp acima do Poisson"
                + (f" com so {gp} rodadas jogadas" if amostra_curta else ""),
                f"ate +{folga_pp:.0f}pp", f"{fus - base:+.1f}pp",
            )


_CORTES_SAFE = {"Over": ("over25", 0.75), "BTTS": ("btts_simetrico", 0.75)}


def premissa_safe_tem_lambda_que_sustente(jogos):
    """Selo de alta confianca exige um lambda que produza aquela probabilidade."""
    for j in jogos:
        par = _lambdas(j)
        if not par:
            continue
        total = par[0] + par[1]
        for mk in (j.get("mercados") or []):
            if (mk.get("classification") or mk.get("status")) not in ("SAFE", "ALTA_CONFIANCA"):
                continue
            nome = str(mk.get("mercado", ""))
            chave = next((k for k in _CORTES_SAFE if nome.startswith(k)), None)
            if not chave:
                continue
            mercado, corte = _CORTES_SAFE[chave]
            preciso = lambda_minimo_para(corte, mercado)
            if total < preciso:
                yield Violacao(
                    "safe_tem_lambda_que_sustente", SEV_CRITICO, _rotulo(j),
                    j.get("leagueId", "?"),
                    f"'{nome}' marcado SAFE",
                    f"soma dos lambdas >= {preciso:.2f}", f"{total:.2f}",
                )


def premissa_lambda_longe_do_grampo(jogos, folga=0.01):
    """Lambda no limite nao e estimativa - e a formula estourando."""
    for j in jogos:
        par = _lambdas(j)
        if not par:
            continue
        for lado, v in zip(("casa", "fora"), par):
            if abs(v - LAMBDA_MIN) < folga or abs(v - LAMBDA_MAX) < folga:
                yield Violacao(
                    "lambda_longe_do_grampo", SEV_ALTO, _rotulo(j), j.get("leagueId", "?"),
                    f"lambda {lado} colado no limite de seguranca",
                    f"entre {LAMBDA_MIN} e {LAMBDA_MAX}, exclusive", f"{v:.2f}",
                )


def premissa_early_season_desliga(jogos, rodadas_max=10):
    """Sinalizador que nunca desliga nao sinaliza nada."""
    for j in jogos:
        gp = _stats(j).get("matchesPlayed_overall")
        if not isinstance(gp, (int, float)) or gp < rodadas_max:
            continue
        for mk in (j.get("mercados") or []):
            if "EARLY_SEASON_FALLBACK" in (mk.get("reason_codes") or []):
                yield Violacao(
                    "early_season_desliga", SEV_MEDIO, _rotulo(j), j.get("leagueId", "?"),
                    f"EARLY_SEASON_FALLBACK em '{mk.get('mercado')}'",
                    f"ausente com {rodadas_max}+ rodadas", f"presente com {gp:.0f}",
                )


def premissa_ev_so_com_odd_real(jogos):
    """EV contra a fair_odd do proprio modelo e um numero que so concorda consigo."""
    for j in jogos:
        for mk in (j.get("mercados") or []):
            ev = mk.get("ev")
            if mk.get("odds_available") is False and isinstance(ev, (int, float)) and ev != 0:
                yield Violacao(
                    "ev_so_com_odd_real", SEV_ALTO, _rotulo(j), j.get("leagueId", "?"),
                    f"'{mk.get('mercado')}' publica EV sem odd de mercado",
                    "EV ausente quando odds_available=false", f"EV {ev:+.3f}",
                )


# ── premissas agregadas (olham a rodada, nao o jogo) ─────────────────

def premissa_vantagem_de_mando_existe(jogos, mediana_min=1.00, minimo_jogos=6):
    """Na mediana de uma rodada, o mandante marca mais que o visitante.

    Nao vale por jogo - o visitante pode ser melhor. Vale na mediana, porque a
    vantagem de mando e um fato agregado. Em 01/09 a mediana deu 0,85 com 14 de
    17 jogos abaixo de 1,00: o modelo estava favorecendo o visitante.
    """
    pares = [p for p in (_lambdas(j) for j in jogos) if p]
    if len(pares) < minimo_jogos:
        return
    razoes = sorted(lh / la for lh, la in pares)
    mediana = razoes[len(razoes) // 2]
    if mediana < mediana_min:
        abaixo = sum(1 for r in razoes if r < 1.0)
        yield Violacao(
            "vantagem_de_mando_existe", SEV_ALTO, f"rodada com {len(pares)} jogos", "-",
            f"mediana da razao lambda casa/fora abaixo de 1 ({abaixo} de {len(pares)} jogos)",
            f">= {mediana_min:.2f}", f"{mediana:.2f}",
        )


def premissa_ev_alto_e_raro(jogos, corte_ev=0.08, fracao_max=0.20, minimo=10):
    """Meia rodada com EV de +8% nao e vantagem - e probabilidade inflada."""
    evs = [mk.get("ev") for j in jogos for mk in (j.get("mercados") or [])
           if isinstance(mk.get("ev"), (int, float))]
    if len(evs) < minimo:
        return
    altos = [e for e in evs if e >= corte_ev]
    frac = len(altos) / len(evs)
    if frac > fracao_max:
        yield Violacao(
            "ev_alto_e_raro", SEV_ALTO, f"rodada com {len(evs)} mercados", "-",
            f"{len(altos)} mercados com EV >= {corte_ev:+.0%}",
            f"ate {fracao_max:.0%} dos mercados", f"{frac:.0%}",
        )


def premissa_manifesto_footystats_em_dia(jogos):
    """#210 - premissa ESTRUTURAL: roda sobre o codigo, nao sobre a saida.

    As outras oito perguntam se a saida obedece o modelo. Esta pergunta se o
    sistema esta lendo os dados que diz ler. Em 01/09/2026, 128 dos 230 campos
    mapeados da FootyStats nao tinham consumidor - inclusive as ancoras de
    vantagem de mando e de BTTS por lado, que passamos semanas derivando por
    outros caminhos.
    """
    try:
        from backend.config.footystats_manifest import verificar
    except Exception as e:
        yield Violacao(
            "manifesto_footystats_em_dia", SEV_MEDIO, "-", "-",
            f"manifesto indisponivel: {type(e).__name__}: {e}",
        )
        return
    r = verificar()
    for linha in r["bloqueia"]:
        yield Violacao("manifesto_footystats_em_dia", SEV_CRITICO, "-", "-", linha)
    for linha in r["avisa"]:
        yield Violacao("manifesto_footystats_em_dia", SEV_MEDIO, "-", "-", linha)


def premissa_ligas_do_frontend_resolvem(jogos):
    """#211 - premissa ESTRUTURAL: todo ID oferecido na tela tem de existir aqui.

    O /fixtures devolvia HTTP 200 com zero jogos para um ID que nao consta do
    registro - indistinguivel de "nao ha jogos hoje". Isso ja custou duas
    leituras erradas: 'england-championship', que nunca existiu, foi lido como
    rodada vazia (0,6s) quando o 'championship' correto trazia 8 jogos em 35s.

    A lista do frontend mistura ID nu ('championship', 'premier-league') com ID
    prefixado ('england-league-one', 'brazil-serie-a'), entao a simetria que se
    supoe nao existe. Uma liga nova adicionada a tela com o prefixo errado
    simplesmente nunca carregaria, sem erro nenhum.
    """
    import os
    import re
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ts = os.path.join(raiz, "frontend", "next", "src", "lib", "leagues.ts")
    if not os.path.exists(ts):
        return
    try:
        from backend.config.leagues_config import get_league_config
    except Exception as e:
        yield Violacao("ligas_do_frontend_resolvem", SEV_MEDIO, "-", "-",
                       f"registro de ligas indisponivel: {type(e).__name__}: {e}")
        return
    with open(ts, encoding="utf-8") as f:
        ids = re.findall(r'^\s+id: "([a-z0-9-]+)",', f.read(), re.M)
    for lid in ids:
        if get_league_config(lid) is None:
            yield Violacao(
                "ligas_do_frontend_resolvem", SEV_CRITICO, "-", lid,
                f"'{lid}' esta em AVAILABLE_LEAGUES e nao resolve no backend; "
                f"a liga nunca carregaria, e o /fixtures devolveria 200 com zero jogos",
                "presente em LEAGUES_CONFIG ou LEAGUE_ID_ALIASES", "ausente",
            )


PREMISSAS: List[Callable] = [
    premissa_over_bate_com_lambda,
    premissa_btts_bate_com_lambda,
    premissa_fusao_nao_ultrapassa_o_lambda,
    premissa_safe_tem_lambda_que_sustente,
    premissa_lambda_longe_do_grampo,
    premissa_early_season_desliga,
    premissa_ev_so_com_odd_real,
    premissa_vantagem_de_mando_existe,
    premissa_ev_alto_e_raro,
    premissa_manifesto_footystats_em_dia,
    premissa_ligas_do_frontend_resolvem,
]


def auditar(jogos: Iterable[Dict[str, Any]], premissas: Optional[List[Callable]] = None) -> Relatorio:
    jogos = list(jogos)
    rel = Relatorio(jogos=len(jogos))
    for p in (premissas or PREMISSAS):
        rel.premissas_rodadas.append(p.__name__.replace("premissa_", ""))
        try:
            rel.violacoes.extend(p(jogos))
        except Exception as e:  # uma premissa quebrada nao pode derrubar o auditor
            rel.violacoes.append(Violacao(
                p.__name__, SEV_MEDIO, "-", "-",
                f"a propria premissa falhou: {type(e).__name__}: {e}",
            ))
    return rel
