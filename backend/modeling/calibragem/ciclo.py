# -*- coding: utf-8 -*-
"""Orquestracao: carrega -> ajusta -> governa -> grava.

Serving: `parametros_vigentes()` com cache por TTL, no padrao do #231-a. Banco
fora do ar NUNCA vira identidade — publicar `raw` de repente seria mudar todo
numero de uma vez por causa de rede. Cai no snapshot empacotado; sem snapshot,
cai no legado (versao 0), e a procedencia sai marcada.
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


def janela_de_reversao(picks_da_celula, criada_em) -> list:
    """Os picks que a versao vigente REALMENTE serviu.

    #248, I1: `ciclo.executar` passava a amostra inteira para
    `avaliar_reversao` — a mesma amostra em que a vigente foi ajustada. Um
    MLE quase sempre ganha no proprio treino, entao o Brier da vigente vinha
    menor que o da anterior por construcao e a acao era SEMPRE `manter`. A
    reversao existia no codigo e nao podia disparar, que e a patologia do
    #247 (o gate que nunca dispara) de novo.

    A janela e `publicado_em > criada_em`, estrito: uma linha publicada no
    mesmo instante da adocao nao foi servida por ela.

    Sem `criada_em` (celula na versao 0, ou dublê de teste que nao informou)
    a janela e VAZIA, nao a amostra inteira. `avaliar_reversao` entao devolve
    `manter` por falta de jogos, com o numero no motivo — nao decidir por
    falta de informacao e diferente de decidir com a informacao errada.
    Pick sem `publicado_em` fica de fora pelo mesmo motivo.
    """
    if criada_em is None:
        return []
    dentro = []
    for p in picks_da_celula:
        quando = p.publicado_em
        if quando is None:
            continue
        try:
            if quando > criada_em:
                dentro.append(p)
        except TypeError:
            # datetime ingenuo x com fuso: comparar levantaria. Fora da
            # janela, e o motivo aparece no log em vez de virar excecao.
            logger.warning(
                "[calibragem] publicado_em (%r) e criada_em (%r) nao sao "
                "comparaveis; pick fora da janela de reversao",
                quando, criada_em)
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


def planejar(picks, ajuste, vigentes) -> dict:
    """Todas as decisoes de um ciclo, SEM escrever uma linha.

    Extraida de `executar` para que o ensaio (`scripts/ensaio_calibragem.py`)
    rode EXATAMENTE a mesma computacao antes de qualquer escrita. Uma segunda
    copia da decisao no script seria a proibicao 5 do CLAUDE.md e, pior,
    divergiria do ciclo justamente no dia em que alguem confiasse no ensaio
    para ligar a camada.

    Faz SELECTs (`ultimo_status_de_ciclo`, `carregar_anterior`); nao faz DDL,
    INSERT nem UPDATE.
    """
    contadores = {"celulas": 0, "adotadas": 0, "encurtadas": 0,
                  "revertidas": 0, "congeladas": 0}
    por_celula = {}
    for p in picks:
        por_celula.setdefault((p.familia, p.liga), []).append(p)

    # Primeira passada: decide o (a, b) de cada celula. Guardado antes de
    # montar as linhas porque a re-derivacao de limiares (abaixo) precisa
    # do "antigo" e do "novo" por FAMILIA (nao por celula) para chamar
    # `limiares.rederivar` uma unica vez por familia.
    decisoes: Dict[tuple, dict] = {}
    for chave, proposta in ajuste.items():
        familia, liga = chave
        if not familia:
            continue
        contadores["celulas"] += 1

        # Congelamento e PEGAJOSO (#248, I2): sem esta leitura a celula
        # congelada por duas reversoes seguidas voltava a adotar no
        # ciclo seguinte, e a "revisao humana" da spec (5.3) era so um
        # logger.error. Ver `repositorio.ultimo_status_de_ciclo` para o
        # procedimento de destravamento.
        if repositorio.ultimo_status_de_ciclo(familia, liga) == "congelada":
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
        # NAO e `por_celula[chave]` inteiro: so os jogos posteriores a
        # adocao da vigente (#248, I1). Ver `janela_de_reversao`.
        servidos = janela_de_reversao(por_celula.get(chave, []),
                                      vig.get("criada_em"))

        # A reversao compara vigente contra ANTERIOR (a versao substituida
        # mais recente), nunca vigente contra ela mesma — isso faria os
        # dois briers ficarem sempre iguais e a reversao nunca disparar.
        # Sem anterior (celula nova, caso normal nos primeiros ciclos) nao
        # ha para onde reverter: pula a avaliacao e segue para a proposta,
        # marcando o motivo para a auditoria. `contar_reversoes_seguidas`
        # so e usada dentro de `avaliar_reversao` — sem anterior essa
        # avaliacao nem roda, entao a contagem fica dentro do ramo que a
        # consome, em vez de uma ida ao banco descartada por celula nova
        # em todo ciclo.
        anterior = repositorio.carregar_anterior(familia, liga)
        if anterior is None:
            rev = {"acao": "manter", "motivo": "sem_anterior",
                  "limite_proximo": PASSO_MAXIMO_PP}
        else:
            reversoes = repositorio.contar_reversoes_seguidas(familia, liga)
            rev = governanca.avaliar_reversao(
                servidos, {"a": vig["a"], "b": vig["b"]},
                {"a": anterior["a"], "b": anterior["b"]}, reversoes)
        limite = rev["limite_proximo"]

        if rev["acao"] == "congelar":
            resultado = {"a": vig["a"], "b": vig["b"], "status": "congelada",
                         "fator_encurtamento": None, "motivo": rev["motivo"]}
        elif rev["acao"] == "reverter":
            contadores["revertidas"] += 1
            # O (a, b) gravado vem da ANTERIOR — reverter e voltar para
            # ela. Gravar o da vigente (a que esta sendo abandonada)
            # faria `gravar_ciclo` promover a celula a "vigente" dela
            # mesma, e a reversao nao mudaria nada.
            resultado = {"a": anterior["a"], "b": anterior["b"],
                         "status": "revertida", "fator_encurtamento": None,
                         "motivo": rev["motivo"]}
        else:
            resultado = governanca.avaliar_proposta(
                proposta, {"a": vig["a"], "b": vig["b"]},
                proposta["n_jogos"], limite=limite)
            # O veredito da reversao entra no motivo TAMBEM quando e
            # `manter` — senao a linha nao distingue "nao havia anterior"
            # de "a janela estava vazia" de "a vigente ganhou". Com a
            # janela agora fora da amostra (#248, I1), saber quantos
            # jogos ela tinha e a unica forma de ler se a reversao esta
            # viva ou so nao teve o que julgar.
            resultado = dict(resultado)
            resultado["motivo"] = "; ".join(
                parte for parte in (rev["motivo"], resultado["motivo"])
                if parte)
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
    # FAMILIA (DEFAULT_THRESHOLDS nao tem granularidade de liga), entao
    # o "antigo"/"novo" que alimentam `rederivar` vem das celulas
    # (familia, "") — a celula-familia, nao das celulas por liga.
    parametros_antigos: Dict[str, dict] = {}
    parametros_novos: Dict[str, dict] = {}
    # #248, C1 (composicao): `dec["vig"]` de uma celula sem versao
    # gravada e `(0, 1)`, e sobre `p_legado` isso E o legado. A
    # re-derivacao preserva o volume que a versao 0 de fato publica —
    # nao o de uma curva idealizada, que era o defeito.
    for (familia, liga), dec in decisoes.items():
        if liga:
            continue
        if dec["vig"]["a"] is None or dec["resultado"]["a"] is None:
            continue   # celula rejeitada por falta de linha de base
        parametros_antigos[familia] = {"a": dec["vig"]["a"], "b": dec["vig"]["b"]}
        parametros_novos[familia] = {"a": dec["resultado"]["a"],
                                     "b": dec["resultado"]["b"]}

    limiares_atuais = _limiares_atuais()
    limiares_novos, motivos_limiares = limiares.rederivar(
        picks, parametros_antigos, parametros_novos, limiares_atuais)

    return {"decisoes": decisoes, "limiares": limiares_novos,
            "motivos_limiares": motivos_limiares,
            "limiares_atuais": limiares_atuais,
            "parametros_antigos": parametros_antigos,
            "parametros_novos": parametros_novos,
            "contadores": contadores}


def executar(caminho_semente: Optional[str] = None) -> dict:
    """Um ciclo completo. Nunca levanta: falha aberta, como o resto do cron."""
    resumo = {"status": "executado", "celulas": 0, "adotadas": 0,
              "encurtadas": 0, "revertidas": 0, "congeladas": 0, "jogos": 0,
              "erro": None}
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
        decisoes = plano["decisoes"]
        limiares_novos = plano["limiares"]
        resumo.update(plano["contadores"])

        linhas = []
        for (familia, liga), dec in decisoes.items():
            vig = dec["vig"]
            # O motivo dos LIMIARES entra na mesma linha do motivo da curva
            # (#249-a). Sem isso, "familia sem odd nenhuma" e "amostra
            # insuficiente para re-derivar" produzem o mesmo silencio na
            # tabela — quatro colunas iguais as da versao anterior, sem dizer
            # por que. Sao coisas diferentes e a auditoria tem de separa-las.
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
                limiares=limiares_novos.get(familia)))

        repositorio.gravar_ciclo(linhas)
        limpar_cache()
        logger.info(
            "[CALIBRAGEM] ciclo: %d celulas, %d jogos | adotadas=%d encurtadas=%d "
            "revertidas=%d congeladas=%d",
            resumo["celulas"], resumo["jogos"], resumo["adotadas"],
            resumo["encurtadas"], resumo["revertidas"], resumo["congeladas"],
        )
    except Exception as e:                                   # noqa: BLE001
        resumo["erro"] = str(e)
        logger.error("[CALIBRAGEM] ciclo falhou: %s", e)
    return resumo
