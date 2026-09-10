# -*- coding: utf-8 -*-
"""Re-derivacao dos limiares de EV e edge, mantendo o volume constante.

A classificacao usa prob RAW (proibicao 11 do CLAUDE.md), entao `safe_prob` e
`neutro_prob` NAO se movem — o raw nao mudou. O volume sobe por `ev` e `edge`,
que consomem a probabilidade corrigida.

Curva e limiar mudam juntos, na mesma versao e na mesma linha de auditoria:
separa-los recria a convivencia de dois regimes que o #244 mediu.
"""
import logging
import math
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from backend.modeling.calibragem import MIN_N_JOGOS
from backend.modeling.calibragem.curva import aplicar, entrada_da_curva
from backend.modeling.calibragem.estimador import contar_jogos

logger = logging.getLogger("sportsbankzu.calibragem.limiares")

# Os quatro campos que a re-derivacao move. Fonte unica: `ciclo` importa
# daqui em vez de manter a propria copia.
CAMPOS = ("safe_ev", "neutro_ev", "safe_edge", "neutro_edge")


def _arredondar_para_baixo(x: float, casas: int = 4) -> float:
    """round(x, 4) pode arredondar PARA CIMA, passando do valor cru do corte.

    O corte e sempre um valor real presente em `evs`/`edges` (o k-esimo da
    ordenacao). Com dados discretos ha clusters de empates exatos nesse valor
    (visto empiricamente: 5 picks empatados em 0.12149539... arredondado para
    0.1215 os excluiu todos do `>=`, porque 0.1215 > 0.12149539...). Arredondar
    sempre para baixo mantem o cluster do corte incluido.

    A folga de +-2 picks que o teste de volume aceita NAO vem daqui. Medido
    pelo revisor da Task 10: neutralizando o arredondamento, o residuo e o
    MESMO. A causa dominante sao os EMPATES exatos no quantil cru — o corte
    e um valor que varios picks compartilham, e `>=` leva o bloco inteiro,
    nao os `k` primeiros. Arredondar para baixo pode acrescentar alguns
    poucos por cima disso, e e um efeito de segunda ordem.
    """
    fator = 10 ** casas
    return math.floor(x * fator) / fator


def _ev_e_edge(p_corr: float, odd) -> tuple:
    if not odd or float(odd) <= 1.0:
        return (None, None)
    odd = float(odd)
    return (p_corr * odd - 1.0, p_corr - 1.0 / odd)


def classificar(picks: Sequence, parametros: Dict[str, dict],
                limiares: Dict[str, dict]):
    """`(pick, classe)` de cada pick que a condicao de EV/edge publica.

    Fonte UNICA da condicao: `contar_por_classe` conta o que sai daqui e o
    piso de amostra (#249-a) mede os jogos do mesmo conjunto. Duas copias da
    condicao divergiriam no dia em que uma delas mudasse.
    """
    for pk in picks:
        par = parametros.get(pk.familia)
        lim = limiares.get(pk.familia)
        if not par or not lim:
            continue
        # A prob que gera EV e edge e a PUBLICADA, ou seja, a composta:
        # `aplicar(legado(raw), a, b)` (#248, C1). Com `(a,b)=(0,1)` isso e
        # exatamente o legado -- e por isso o volume de referencia da versao
        # 0 e agora o volume REAL, nao o de uma curva idealizada.
        ev, edge = _ev_e_edge(aplicar(entrada_da_curva(pk), par["a"], par["b"]),
                              pk.odd)
        if ev is None:
            continue
        if ev >= lim["safe_ev"] and edge >= lim["safe_edge"]:
            yield pk, "safe"
        elif ev >= lim["neutro_ev"] and edge >= lim["neutro_edge"]:
            yield pk, "neutro"


def contar_por_classe(picks: Sequence, parametros: Dict[str, dict],
                      limiares: Dict[str, dict]) -> Dict[str, Dict[str, int]]:
    """Quantos picks caem em cada classe, por familia."""
    saida: Dict[str, Dict[str, int]] = defaultdict(lambda: {"safe": 0, "neutro": 0})
    for pk, classe in classificar(picks, parametros, limiares):
        saida[pk.familia][classe] += 1
    return saida


def _quantil_que_preserva(valores: List[float], quantos: int):
    """O corte que deixa exatamente `quantos` valores acima ou iguais."""
    if quantos <= 0:
        return None
    ordenados = sorted(valores, reverse=True)
    if quantos >= len(ordenados):
        return ordenados[-1] if ordenados else None
    return ordenados[quantos - 1]


def rederivar(picks: Sequence, parametros_antigos: Dict[str, dict],
              parametros_novos: Dict[str, dict],
              limiares_atuais: Dict[str, dict]
              ) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Os quatro valores por familia que reproduzem a contagem anterior.

    Devolve `(limiares, motivos)`. O motivo viaja SEPARADO, e nao como uma
    quinta chave dentro do dict de limiares, por dois motivos: aquele dict
    vai inteiro para `montar_linha_auditoria` e para `_get_thresholds`
    (#249), onde so numeros fazem sentido; e "sem preco" e "amostra
    insuficiente" produziriam o mesmo silencio na tabela se nao houvesse
    canal proprio — quem ler `calibragem_versoes` daqui a tres meses precisa
    distinguir os dois.

    Piso de amostra (#249-a): familia cujo conjunto de picks COM PRECO nao
    alcance `MIN_N_JOGOS` jogos distintos NAO re-deriva. Um limiar estimado
    de uma observacao e um numero sem conteudo ocupando o lugar de um numero
    calibrado — e passa a decidir o que o operador ve. Medido no primeiro
    ciclo real: Double Chance tinha 1 pick publicado, e `safe_ev` saltava de
    0,0400 para 0,2397 por causa dele. E a mesma regra do #079 (`N < 20` e
    diagnostico, nunca decisorio) que a camada ja reusa como piso do
    encolhimento e da governanca.

    JOGOS distintos, nao picks: picks do mesmo jogo dividem o mesmo placar,
    entao 30 linhas de um jogo so nao sao 30 observacoes. E a mesma contagem
    de `estimador.contar_jogos`, importada de la em vez de reescrita.
    """
    alvo = contar_por_classe(picks, parametros_antigos, limiares_atuais)
    # Os JOGOS que sustentam o volume publicado de cada familia. E deste
    # conjunto que o corte sai (o k-esimo maior EV, com k = tamanho do alvo),
    # entao e a amostra desta medida — nao a amostra inteira da familia.
    jogos_do_alvo: Dict[str, set] = defaultdict(set)
    for pk, _classe in classificar(picks, parametros_antigos, limiares_atuais):
        jogos_do_alvo[pk.familia].add(pk.match_id)

    por_familia: Dict[str, list] = defaultdict(list)
    for pk in picks:
        por_familia[pk.familia].append(pk)

    saida: Dict[str, dict] = {}
    motivos: Dict[str, str] = {}
    for familia, atual in limiares_atuais.items():
        pk_familia = por_familia.get(familia) or []
        par = parametros_novos.get(familia)
        if not par:
            saida[familia] = dict(atual)
            motivos[familia] = "limiares mantidos: sem curva nova para a familia"
            continue

        evs, edges, com_preco = [], [], []
        for pk in pk_familia:
            ev, edge = _ev_e_edge(
                aplicar(entrada_da_curva(pk), par["a"], par["b"]), pk.odd)
            if ev is not None:
                evs.append(ev)
                edges.append(edge)
                com_preco.append(pk)

        if not evs:
            # Familia sem preco em quase nenhuma linha (cartoes: 88,3%). Nao ha
            # volume a manter constante — registra e nao mexe.
            logger.info("[calibragem] %s sem picks com odd; limiares inalterados",
                        familia)
            saida[familia] = dict(atual)
            motivos[familia] = "limiares mantidos: nenhum pick com odd"
            continue

        n_jogos = contar_jogos(com_preco)
        if n_jogos < MIN_N_JOGOS:
            # #249-a: NAO e o mesmo caso do `if not evs` acima, e a linha de
            # auditoria tem de dizer qual dos dois foi.
            logger.warning(
                "[calibragem] %s: %d jogos com preco < %d (#079) — limiares "
                "MANTIDOS. Re-derivar aqui trocaria um limiar calibrado por "
                "um quantil de amostra diagnostica.",
                familia, n_jogos, MIN_N_JOGOS)
            saida[familia] = dict(atual)
            motivos[familia] = (
                f"limiares mantidos: {n_jogos} jogos com preco < "
                f"{MIN_N_JOGOS} (#079)")
            continue

        # O piso que pega o ruido MEDIDO (#249-a). O de cima (pool com preco)
        # nao dispara em nenhuma familia real: Double Chance tem 245 jogos com
        # preco. O que era estimado de UMA observacao era o CORTE, porque o
        # alvo daquela familia era 1 pick, de 1 jogo -- e o corte com alvo 1 e
        # o MAXIMO do conjunto, a estatistica mais ruidosa que existe. A
        # amostra desta medida e o conjunto que sustenta o volume publicado.
        n_jogos_alvo = len(jogos_do_alvo.get(familia) or ())
        if n_jogos_alvo < MIN_N_JOGOS:
            logger.warning(
                "[calibragem] %s: volume publicado apoiado em %d jogos < %d "
                "(#079) — limiares MANTIDOS. Com alvo tao pequeno o corte e "
                "um extremo da amostra, nao um quantil.",
                familia, n_jogos_alvo, MIN_N_JOGOS)
            saida[familia] = dict(atual)
            motivos[familia] = (
                f"limiares mantidos: volume publicado apoiado em "
                f"{n_jogos_alvo} jogos < {MIN_N_JOGOS} (#079)")
            continue

        motivos[familia] = (
            f"limiares re-derivados sobre {n_jogos} jogos com preco "
            f"({len(evs)} picks); alvo apoiado em {n_jogos_alvo} jogos")
        n_safe = alvo.get(familia, {}).get("safe", 0)
        n_ate_neutro = n_safe + alvo.get(familia, {}).get("neutro", 0)
        novo = dict(atual)
        for prefixo, quantos in (("safe", n_safe), ("neutro", n_ate_neutro)):
            ev_cutoff = _quantil_que_preserva(evs, quantos)
            if ev_cutoff is None:
                continue
            # O edge nao compartilha a ordenacao do ev entre picks de odds
            # distintas (ev = odd*p-1, edge = p-1/odd pesam odd de jeitos
            # diferentes) -- um quantil independente de edge intersecta com
            # o conjunto por ev e FICA ABAIXO do alvo (visto empiricamente:
            # 222 de 230 no teste 6). O edge_cutoff tem de ser amarrado ao
            # MESMO conjunto que passou no corte de ev (o minimo de edge
            # dentro dele), senao a condicao conjunta (ev AND edge) nao
            # preserva a contagem por classe.
            indices_no_corte = [i for i, ev in enumerate(evs) if ev >= ev_cutoff]
            if not indices_no_corte:
                continue
            edge_cutoff = min(edges[i] for i in indices_no_corte)
            novo[f"{prefixo}_ev"] = _arredondar_para_baixo(ev_cutoff)
            novo[f"{prefixo}_edge"] = _arredondar_para_baixo(edge_cutoff)
        saida[familia] = novo
    return saida, motivos
