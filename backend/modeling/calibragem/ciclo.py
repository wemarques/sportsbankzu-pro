# -*- coding: utf-8 -*-
"""Orquestracao: carrega -> ajusta -> governa -> grava.

Serving: `parametros_vigentes()` com cache por TTL, no padrao do #231-a. Banco
fora do ar NUNCA vira identidade — publicar `raw` de repente seria mudar todo
numero de uma vez por causa de rede. Cai no snapshot empacotado; sem snapshot,
cai no legado (versao 0), e a procedencia sai marcada.

"Fora do ar" e "nao configurado" NAO sao a mesma coisa (#248-a). Com
`DATABASE_URL` definida e a conexao falhando ha degradacao: procedencia
`legado` (ou `snapshot`), log de erro e sufixo visivel no `tipo_banda`. Sem
`DATABASE_URL` no ambiente a camada simplesmente nao esta ligada — dev, CI,
qualquer execucao sem banco: procedencia `sem_banco`, log informativo e
NENHUM sufixo, porque o comportamento e exatamente o de sempre.
"""
import logging
import os
import time
from typing import Dict, Optional, Tuple

from backend.modeling.calibragem import PASSO_MAXIMO_PP, VERSAO_LEGADO
from backend.modeling.calibragem import (
    estimador, governanca, limiares, repositorio,
)  # noqa: E402 -- pacote e submodulos, dois imports por legibilidade

logger = logging.getLogger("sportsbankzu.calibragem.ciclo")

# Snapshot empacotado no deploy. Preenchido por `scripts/snapshot_calibragem.py`
# quando houver versoes vigentes; vazio significa "tudo na versao 0".
_SNAPSHOT: Dict[tuple, tuple] = {}

_CACHE: Dict[str, object] = {"parametros": None, "limiares": None,
                             "procedencia": None, "t": 0.0}

# Procedencias que NAO marcam o `tipo_banda` (#248-a): o painel esta servindo
# exatamente o que deveria servir. `banco` e o caminho feliz; `sem_banco` e a
# camada desligada, que publica o legado versao 0 — o mesmo numero da vespera.
# `legado` e `snapshot` ficam de fora de proposito: sao degradacao, e o #238
# mostrou o custo de um fallback silencioso.
PROCEDENCIAS_SEM_MARCA = frozenset({"banco", "sem_banco"})

# Os quatro campos de `DEFAULT_THRESHOLDS` que a re-derivacao move. A lista
# mora em `limiares.CAMPOS`, que e quem os re-deriva; havia uma copia literal
# aqui, e duas listas do mesmo conjunto so tem um destino.
# `safe_prob`/`neutro_prob`/`min_quality` ficam de fora: a classificacao usa
# prob RAW (proibicao 11), entao esses nao se movem com a curva.
_CAMPOS_LIMIAR = limiares.CAMPOS


def _ttl() -> float:
    return float(os.getenv("CALIBRAGEM_TTL_S", "300"))


def calibragem_habilitada() -> bool:
    """Chave de desligamento do ciclo de ESCRITA. Padrao: DESLIGADO.

    Segue o padrao da casa (`PROB_SOURCE` do #231, `PREDICTION_LEDGER_ENABLED`
    do #218): o deploy do codigo NAO e a ativacao do comportamento. Sem esta
    chave, `cron_handler` chamaria `executar()` duas vezes por dia desde o
    primeiro deploy, e o `REGISTRO_CORRECOES` do #248 — que afirma que ligar
    em producao e decisao separada — seria falso na pratica.

    Governa apenas a ESCRITA (`executar`). O SERVING (`parametros_vigentes`)
    continua ligado de proposito: sem versoes gravadas ele devolve o mapa
    vazio e `curva.aplicar_versao` delega ao legado, ou seja, publica
    exatamente o que se publicava na vespera.
    """
    return os.getenv("CALIBRAGEM_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on"
    )


def limpar_cache() -> None:
    _CACHE.update({"parametros": None, "limiares": None, "procedencia": None,
                   "t": 0.0})


def _servir() -> Tuple[Dict[tuple, tuple], Dict[str, dict], str]:
    """Curva E limiares, do MESMO instante e da MESMA leitura (#249).

    Uma consulta so, por dois motivos. O barato: `_get_thresholds` roda por
    mercado, por jogo, por liga, e o caminho de `/fixtures` ja namora o teto
    de 60s da Lambda — duas conexoes por container frio seriam duas esperas
    de `connect_timeout`. O caro: curva e limiar tem de vir do mesmo ciclo.
    Ler os dois em consultas separadas admite um instante em que a curva ja
    subiu e o limiar ainda e o velho, e ai o volume publicado dobra — que e
    exatamente o que a re-derivacao existe para impedir.

    Banco fora do ar: a curva cai no snapshot (ou no legado) como sempre, e
    os limiares caem em `{}` — ou seja, `_get_thresholds` devolve os limiares
    de hoje. As duas pontas coerentes: `{}` de parametros e a versao 0, e a
    versao 0 e a curva para a qual os limiares de hoje foram calibrados.
    """
    try:
        vigentes = repositorio.carregar_vigentes()
        parametros = {ch: (v["versao"], v["a"], v["b"])
                      for ch, v in vigentes.items()}
        limiares_servidos = repositorio.limiares_por_familia(vigentes)
        return parametros, limiares_servidos, "banco"
    except Exception as e:                                   # noqa: BLE001
        if _SNAPSHOT:
            parametros, procedencia = dict(_SNAPSHOT), "snapshot"
            # O snapshot carrega `(versao, a, b)` e NAO carrega limiares. Se
            # algum dia ele passar a ser preenchido, servir a curva dele com
            # os limiares de hoje publica volume a mais enquanto o banco
            # estiver fora — quem preencher o snapshot tem de carregar os
            # quatro campos junto.
            logger.error(
                "[calibragem] servindo curva de SNAPSHOT sem limiares "
                "correspondentes: o volume publicado pode subir enquanto o "
                "banco estiver fora")
        elif not repositorio.banco_configurado():
            # `DATABASE_URL` nem definida: a camada nao esta configurada.
            # Nao ha degradacao a anunciar — o painel publica exatamente o
            # que publicava antes desta camada existir, delegando ao legado
            # versao 0. Marcar isso enche o `tipo_banda` de ruido em todo
            # dev e em todo CI (#248-a).
            logger.info(
                "[calibragem] DATABASE_URL nao definida; servindo o legado "
                "versao 0 (comportamento normal sem banco)")
            return {}, {}, "sem_banco"
        else:
            parametros, procedencia = {}, "legado"
        logger.error(
            "[calibragem] parametros do banco indisponiveis (%s); servindo de "
            "'%s' — o painel NAO caiu para identidade", e, procedencia,
        )
        return parametros, {}, procedencia


def _servir_com_cache() -> Tuple[Dict[tuple, tuple], Dict[str, dict], str]:
    agora = time.time()
    ttl = _ttl()
    if _CACHE["parametros"] is not None and ttl > 0 and agora - _CACHE["t"] < ttl:
        return _CACHE["parametros"], _CACHE["limiares"], _CACHE["procedencia"]
    parametros, limiares_servidos, procedencia = _servir()
    _CACHE.update({"parametros": parametros, "limiares": limiares_servidos,
                   "procedencia": procedencia, "t": agora})
    return parametros, limiares_servidos, procedencia


def parametros_vigentes() -> Tuple[Dict[tuple, tuple], str]:
    parametros, _limiares, procedencia = _servir_com_cache()
    return parametros, procedencia


def limiares_vigentes() -> Dict[str, dict]:
    """Os quatro limiares de EV/edge por familia, ou `{}`.

    `{}` significa "nada a sobrescrever": sem versao gravada, com a camada
    desligada ou com o banco fora do ar, `_get_thresholds` devolve
    exatamente o que devolvia antes desta funcao existir.

    Nunca levanta — o chamador esta no caminho de decisao de todo pick.
    """
    _parametros, limiares_servidos, _proc = _servir_com_cache()
    return limiares_servidos or {}


def _limiares_atuais() -> Dict[str, dict]:
    """As quatro chaves que interessam, por familia, de `DEFAULT_THRESHOLDS`."""
    from backend.services.ev_classification import DEFAULT_THRESHOLDS
    return {
        familia: {campo: cfg[campo] for campo in _CAMPOS_LIMIAR}
        for familia, cfg in DEFAULT_THRESHOLDS.items()
    }


def janela_de_reversao(picks_da_celula, desde) -> list:
    """Os picks publicados DEPOIS do `desde` da ancora (#253).

    #248, I1: julgar na amostra inteira era in-sample (o MLE ganha no proprio
    treino). #253: julgar desde a `criada_em` da VIGENTE zerava a janela todo
    ciclo, porque a versao troca a cada cron; em 10 ciclos de producao ela
    nunca chegou a 20 jogos. O ponto de partida e a ancora, que so muda por
    validacao ou reversao. Quem garante "fora da amostra" nao e mais a janela,
    e a pontuacao de cada pick pela versao que o serviu
    (`governanca.curva_servida`).

    `publicado_em > desde`, estrito. Sem `desde` (celula sem historico) a
    janela e VAZIA, nao a amostra inteira; pick sem `publicado_em` fica de
    fora pelo mesmo motivo.
    """
    if desde is None:
        return []
    dentro = []
    for p in picks_da_celula:
        quando = p.publicado_em
        if quando is None:
            continue
        try:
            if quando > desde:
                dentro.append(p)
        except TypeError:
            # datetime ingenuo x com fuso: comparar levantaria. Fora da
            # janela, e o motivo aparece no log em vez de virar excecao.
            logger.warning(
                "[calibragem] publicado_em (%r) e desde (%r) nao sao "
                "comparaveis; pick fora da janela de reversao",
                quando, desde)
    return dentro


def _vigente_da_celula(vigentes: Dict[tuple, dict], chave: tuple) -> Optional[dict]:
    """O `(a, b)` contra o qual a trava e os limiares medem.

    Celula com versao gravada: o que esta no banco. Celula SEM versao
    gravada: `(0, 1)`, a versao 0 — e agora isso e EXATO, nao uma
    aproximacao (#248, C1, resolvido por composicao). A curva servida e
    `sigmoide(a + b*logit(legado(p)))`, entao `(a=0, b=1)` devolve o proprio
    legado, byte a byte, e `distancia_maxima(0, 1, a_p, b_p)` mede a
    distancia real ate a curva publicada na vespera.

    Historia, para nao se repetir: antes da composicao esta funcao chamava
    `linha_base.linha_base(familia, liga)`, que ajustava uma logistica de
    dois parametros a curva legada. A aproximacao errava de 8,14pp a 15,47pp
    e o melhor par POSSIVEL ainda erraria 5,89pp / 9,35pp (piso de
    Chebyshev, otimos equioscilando em quatro pontos) — porque o legado
    satura e a logistica nao. A trava de 2pp nunca valia no primeiro ciclo.
    Compondo, o erro nao diminui: some. `linha_base.py` foi APAGADO.

    A assinatura devolve `Optional` porque o chamador ja trata `None`
    (celula rejeitada); hoje nao ha caminho que devolva `None` — a versao 0
    e a mesma para toda familia, e nao ha mais "familia sem mercado
    representativo".
    """
    vig = vigentes.get(chave)
    if vig is not None:
        return vig
    return {"versao": VERSAO_LEGADO, "a": 0.0, "b": 1.0, "criada_em": None}


def desde_da_familia(ancoras: Dict[tuple, dict], familia: str, celulas) -> object:
    """Onde a janela da FAMILIA abre (#253-a).

    O `desde` da ancora da celula-familia `(familia, "")`: todo veredito da
    familia grava linha nela, entao ela marca o ultimo julgamento. Sem
    historico dela, o `desde` mais recente entre as celulas da familia —
    conservador: nao julga jogos anteriores a qualquer celula existir.
    Nenhum -> None (janela vazia).
    """
    propria = ancoras.get((familia, ""))
    if propria is not None:
        return propria.get("desde")
    desdes = [ancoras[c]["desde"] for c in celulas
              if c in ancoras and ancoras[c].get("desde") is not None]
    if not desdes:
        return None
    try:
        return max(desdes)
    except TypeError:
        return None


def planejar(picks, ajuste, vigentes, historico=None) -> dict:
    """Todas as decisoes de um ciclo, SEM escrever uma linha.

    Extraida de `executar` para que o ensaio (`scripts/ensaio_calibragem.py`)
    rode EXATAMENTE a mesma computacao antes de qualquer escrita. Uma segunda
    copia da decisao no script seria a proibicao 5 do CLAUDE.md.

    `historico`: as linhas de `calibragem_versoes` (#253). `None` le do banco
    uma vez (`repositorio.carregar_historico`, um SELECT). A simulacao
    multi-ciclo dos testes passa a lista em memoria.

    #253-a: o julgamento e POR FAMILIA (`governanca.julgar_familia`), somando
    as ligas; o veredito vale para TODAS as celulas da familia, inclusive as
    vigentes que nao entraram no ajuste deste ciclo. Sem veredito, cada
    celula segue na trava e no teto contra a propria ancora.
    """
    if historico is None:
        historico = repositorio.carregar_historico()
    ancoras = repositorio.ancoras_do_historico(historico)
    vigencia = repositorio.vigencia_do_historico(historico)

    contadores = {"celulas": 0, "adotadas": 0, "encurtadas": 0,
                  "revertidas": 0, "congeladas": 0, "ancoradas": 0}
    picks_por_familia: Dict[str, list] = {}
    for p in picks:
        picks_por_familia.setdefault(p.familia, []).append(p)

    # Um veredito por familia, antes de olhar celula por celula.
    familias = sorted({f for f, _l in ajuste if f})
    vereditos: Dict[str, dict] = {}
    for familia in familias:
        celulas = {c for c in ajuste if c[0] == familia} | {c for c in vigentes if c[0] == familia}
        desde = desde_da_familia(ancoras, familia, celulas)
        vereditos[familia] = governanca.julgar_familia(
            janela_de_reversao(picks_por_familia.get(familia, []), desde),
            vigencia, ancoras,
            {c: {"a": v["a"], "b": v["b"]} for c, v in vigentes.items() if c[0] == familia},
            repositorio.reversoes_seguidas_do_historico(historico, familia, ""))

    # Celulas vigentes fora do ajuste tambem recebem o veredito da familia:
    # revertida so no ajuste deixaria uma liga sem amostra neste ciclo
    # publicando a curva que a familia acabou de reprovar.
    itens = list(ajuste.items())
    for chave in sorted(vigentes):
        familia = chave[0]
        if chave in ajuste or familia not in vereditos:
            continue
        if vereditos[familia]["acao"] == "manter":
            continue
        itens.append((chave, {"n_jogos": 0, "origem": "julgamento-familia"}))

    decisoes: Dict[tuple, dict] = {}
    for chave, proposta in itens:
        familia, liga = chave
        if not familia:
            continue
        contadores["celulas"] += 1

        # Congelamento e PEGAJOSO (#248, I2). Procedimento de destravamento na
        # docstring de `repositorio.ultimo_status_do_historico`.
        if repositorio.ultimo_status_do_historico(historico, familia, liga) == "congelada":
            contadores["congeladas"] += 1
            congelada = vigentes.get(chave)
            logger.error(
                "[calibragem] celula (%s, %s) CONGELADA em ciclo anterior; "
                "nada sera adotado ate destravamento manual",
                familia, liga or "-")
            decisoes[chave] = {
                "vig": congelada if congelada is not None else {
                    "versao": VERSAO_LEGADO, "a": None, "b": None},
                "resultado": {
                    "a": congelada["a"] if congelada is not None else None,
                    "b": congelada["b"] if congelada is not None else None,
                    "status": "congelada", "fator_encurtamento": None,
                    "motivo": "congelada em ciclo anterior; aguarda "
                              "destravamento manual"},
                "n_jogos": proposta["n_jogos"], "origem": proposta["origem"],
            }
            continue

        vig = _vigente_da_celula(vigentes, chave)
        if vig is None:
            decisoes[chave] = {
                "vig": {"versao": VERSAO_LEGADO, "a": None, "b": None},
                "resultado": {"a": None, "b": None, "status": "rejeitada",
                              "fator_encurtamento": None,
                              "motivo": f"sem linha de base para '{familia}'"},
                "n_jogos": proposta["n_jogos"], "origem": proposta["origem"],
            }
            continue

        rev = vereditos[familia]
        a_anc, b_anc = governanca.ancora_do_pick(ancoras, familia, liga)
        ancora = {"a": a_anc, "b": b_anc}

        if rev["acao"] == "congelar":
            resultado = {"a": vig["a"], "b": vig["b"], "status": "congelada",
                         "fator_encurtamento": None, "motivo": rev["motivo"]}
        elif rev["acao"] == "reverter":
            contadores["revertidas"] += 1
            # Volta para a ANCORA da celula: a ultima curva validada (ou a da
            # familia, ou o legado — a mesma ordem que pontuou os picks).
            resultado = {"a": a_anc, "b": b_anc, "status": "revertida",
                         "fator_encurtamento": None, "motivo": rev["motivo"]}
        elif rev["acao"] == "ancorar":
            contadores["ancoradas"] += 1
            # A vigente NAO muda: a linha so marca a validacao e abre uma
            # janela nova. Um evento por celula por ciclo.
            resultado = {"a": vig["a"], "b": vig["b"], "status": "ancorada",
                         "fator_encurtamento": None, "motivo": rev["motivo"]}
        else:
            resultado = dict(governanca.avaliar_proposta(
                proposta, {"a": vig["a"], "b": vig["b"]},
                proposta["n_jogos"], limite=rev["limite_proximo"], ancora=ancora))
            # O veredito da familia entra no motivo TAMBEM quando e `manter`:
            # quantos jogos a janela tinha e a unica forma de ler se o
            # julgamento esta vivo ou so nao teve o que julgar.
            resultado["motivo"] = "; ".join(
                parte for parte in (rev["motivo"], resultado["motivo"]) if parte)
            if resultado["status"] == "adotada":
                contadores["adotadas"] += 1
            elif resultado["status"] == "encurtada":
                contadores["encurtadas"] += 1
        if resultado["status"] == "congelada":
            contadores["congeladas"] += 1

        decisoes[chave] = {
            "vig": vig, "resultado": resultado,
            "n_jogos": proposta["n_jogos"], "origem": proposta["origem"],
        }

    # Re-derivacao dos limiares: curva e limiar mudam juntos, na mesma
    # versao e na mesma linha de auditoria (#244). Os limiares sao por
    # FAMILIA (DEFAULT_THRESHOLDS nao tem granularidade de liga), mas a curva
    # que gera o EV de cada pick e a que o SERVING usaria (#253-b): mapas POR
    # CELULA, com as vigentes antes do ciclo e as vigentes depois dele. Mover
    # so a celula-familia e contar todo pick com ela dizia volume 402 -> 403
    # quando o serving publicaria 365 (9 de 20 ligas tinham vigente propria).
    parametros_antigos: Dict[tuple, dict] = {
        celula: {"a": v["a"], "b": v["b"]} for celula, v in vigentes.items()
        if celula[0] and v.get("a") is not None}
    # A celula-familia esta sempre no mapa: sem vigente ela e a versao 0, que
    # e o que o serving publica para liga sem celula propria (#248, C1).
    for familia in familias:
        parametros_antigos.setdefault((familia, ""), {"a": 0.0, "b": 1.0})
    parametros_novos: Dict[tuple, dict] = {
        celula: dict(par) for celula, par in parametros_antigos.items()}
    for celula, dec in decisoes.items():
        r = dec["resultado"]
        if r["status"] in repositorio.STATUS_DE_PROMOCAO and r["a"] is not None:
            parametros_novos[celula] = {"a": r["a"], "b": r["b"]}

    limiares_atuais = _limiares_atuais()
    limiares_novos, motivos_limiares = limiares.rederivar(
        picks, parametros_antigos, parametros_novos, limiares_atuais)

    return {"decisoes": decisoes, "limiares": limiares_novos,
            "motivos_limiares": motivos_limiares,
            "limiares_atuais": limiares_atuais,
            "parametros_antigos": parametros_antigos,
            "parametros_novos": parametros_novos,
            "contadores": contadores}


def linhas_do_plano(plano: dict) -> list:
    """As linhas de auditoria de um plano, prontas para `gravar_ciclo`.

    Extraida de `executar` (#253) para a simulacao multi-ciclo dos testes
    gravar exatamente o que o ciclo grava.
    """
    linhas = []
    for (familia, liga), dec in plano["decisoes"].items():
        vig = dec["vig"]
        # O motivo dos LIMIARES entra na mesma linha do motivo da curva
        # (#249-a): "familia sem odd nenhuma" e "amostra insuficiente para
        # re-derivar" nao podem produzir o mesmo silencio na tabela.
        resultado = dec["resultado"]
        motivo_limiar = plano["motivos_limiares"].get(familia)
        if motivo_limiar:
            resultado = dict(resultado)
            resultado["motivo"] = "; ".join(
                parte for parte in (resultado.get("motivo", ""),
                                    motivo_limiar) if parte)
        linhas.append(repositorio.montar_linha_auditoria(
            familia, liga, vig["versao"] + 1, resultado,
            dec["n_jogos"], dec["origem"], None,
            limiares=plano["limiares"].get(familia)))
    return linhas


def executar(caminho_semente: Optional[str] = None) -> dict:
    """Um ciclo completo. Nunca levanta: falha aberta, como o resto do cron."""
    resumo = {"status": "executado", "celulas": 0, "adotadas": 0,
              "encurtadas": 0, "revertidas": 0, "congeladas": 0,
              "ancoradas": 0, "jogos": 0, "erro": None}
    if not calibragem_habilitada():
        resumo["status"] = "desligado"
        logger.info(
            "[CALIBRAGEM] ciclo NAO executado: CALIBRAGEM_ENABLED desligada "
            "(padrao). Nenhuma leitura, nenhuma escrita, nenhum DDL.")
        return resumo
    try:
        repositorio.garantir_tabela()
        picks = repositorio.carregar_amostra()
        resumo["jogos"] = len({p.match_id for p in picks})

        ajuste = estimador.ajustar_hierarquico(picks)
        if caminho_semente:
            semente_picks = repositorio.carregar_semente_backfill(caminho_semente)
            if semente_picks:
                conc, n_sobrepostos = estimador.medir_concordancia(semente_picks, picks)
                n_prior, _status = estimador.n_prior_da_concordancia(conc, n_sobrepostos)
                ajuste = estimador.aplicar_semente(
                    ajuste, estimador.ajustar_hierarquico(semente_picks), n_prior)

        vigentes = repositorio.carregar_vigentes()
        plano = planejar(picks, ajuste, vigentes)
        resumo.update(plano["contadores"])

        repositorio.gravar_ciclo(linhas_do_plano(plano))
        limpar_cache()
        logger.info(
            "[CALIBRAGEM] ciclo: %d celulas, %d jogos | adotadas=%d encurtadas=%d "
            "revertidas=%d ancoradas=%d congeladas=%d",
            resumo["celulas"], resumo["jogos"], resumo["adotadas"],
            resumo["encurtadas"], resumo["revertidas"], resumo["ancoradas"],
            resumo["congeladas"],
        )
    except Exception as e:                                   # noqa: BLE001
        resumo["erro"] = str(e)
        logger.error("[CALIBRAGEM] ciclo falhou: %s", e)
    return resumo
