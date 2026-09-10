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

from backend.modeling.calibragem import (
    MIN_N_JOGOS, PASSO_MAXIMO_PP, VERSAO_LEGADO,
)
from backend.modeling.calibragem import (
    estimador, governanca, limiares, linha_base, repositorio,
)

logger = logging.getLogger("sportsbankzu.calibragem.ciclo")

# Snapshot empacotado no deploy. Preenchido por `scripts/snapshot_calibragem.py`
# quando houver versoes vigentes; vazio significa "tudo na versao 0".
_SNAPSHOT: Dict[tuple, tuple] = {}

_CACHE: Dict[str, object] = {"parametros": None, "procedencia": None, "t": 0.0}

# Os quatro campos de `DEFAULT_THRESHOLDS` que a re-derivacao de limiares
# move. `safe_prob`/`neutro_prob`/`min_quality` nao entram: a classificacao
# usa prob RAW (proibicao 11), entao esses nao se movem com a curva.
_CAMPOS_LIMIAR = ("safe_ev", "neutro_ev", "safe_edge", "neutro_edge")


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
    _CACHE.update({"parametros": None, "procedencia": None, "t": 0.0})


def parametros_vigentes() -> Tuple[Dict[tuple, tuple], str]:
    agora = time.time()
    ttl = _ttl()
    if _CACHE["parametros"] is not None and ttl > 0 and agora - _CACHE["t"] < ttl:
        return _CACHE["parametros"], _CACHE["procedencia"]
    try:
        parametros = repositorio.carregar_parametros_para_curva()
        procedencia = "banco"
    except Exception as e:                                   # noqa: BLE001
        if _SNAPSHOT:
            parametros, procedencia = dict(_SNAPSHOT), "snapshot"
        else:
            parametros, procedencia = {}, "legado"
        logger.error(
            "[calibragem] parametros do banco indisponiveis (%s); servindo de "
            "'%s' — o painel NAO caiu para identidade", e, procedencia,
        )
    _CACHE.update({"parametros": parametros, "procedencia": procedencia, "t": agora})
    return parametros, procedencia


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

    Celula com versao gravada: o que esta no banco. Celula SEM versao gravada:
    a versao 0 — e a versao 0 NAO e a identidade, e o legado (#248, C1). Sem
    esta funcao, `{"a": 0.0, "b": 1.0}` fazia a trava de 2pp medir contra uma
    curva 12-25 pontos acima da publicada, e o primeiro ciclo passava por
    "adotada" um salto de ate 24,95pp.

    `None` quando a familia nao tem linha de base mensuravel (familia nova,
    sem mercado representativo). O chamador rejeita a celula em vez de
    inventar uma referencia — adotar sem saber de onde se parte e como o
    defeito nasceu.
    """
    vig = vigentes.get(chave)
    if vig is not None:
        return vig
    familia, liga = chave
    try:
        a0, b0 = linha_base.linha_base(familia, liga)
    except ValueError as e:                                  # noqa: BLE001
        logger.error("[calibragem] celula (%s, %s) sem linha de base: %s",
                     familia, liga or "-", e)
        return None
    return {"versao": VERSAO_LEGADO, "a": a0, "b": b0, "criada_em": None}


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
            resumo["celulas"] += 1

            # Congelamento e PEGAJOSO (#248, I2): sem esta leitura a celula
            # congelada por duas reversoes seguidas voltava a adotar no
            # ciclo seguinte, e a "revisao humana" da spec (5.3) era so um
            # logger.error. Ver `repositorio.ultimo_status_de_ciclo` para o
            # procedimento de destravamento.
            if repositorio.ultimo_status_de_ciclo(familia, liga) == "congelada":
                resumo["congeladas"] += 1
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
                resumo["revertidas"] += 1
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
                    resumo["adotadas"] += 1
                elif resultado["status"] == "encurtada":
                    resumo["encurtadas"] += 1
            if resultado["status"] == "congelada":
                resumo["congeladas"] += 1

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
        # #248, C1: `dec["vig"]` de uma celula sem versao gravada e a LINHA DE
        # BASE DO LEGADO, nao mais a identidade. Sem isso a re-derivacao
        # preservava o volume de uma curva que nunca publicou nada, e o volume
        # real dobrava no primeiro ciclo (medido: SAFE de Corners 106 -> 306).
        for (familia, liga), dec in decisoes.items():
            if liga:
                continue
            if dec["vig"]["a"] is None or dec["resultado"]["a"] is None:
                continue   # celula rejeitada por falta de linha de base
            parametros_antigos[familia] = {"a": dec["vig"]["a"], "b": dec["vig"]["b"]}
            parametros_novos[familia] = {"a": dec["resultado"]["a"],
                                         "b": dec["resultado"]["b"]}

        limiares_atuais = _limiares_atuais()
        limiares_novos = limiares.rederivar(
            picks, parametros_antigos, parametros_novos, limiares_atuais)

        linhas = []
        for (familia, liga), dec in decisoes.items():
            vig = dec["vig"]
            linhas.append(repositorio.montar_linha_auditoria(
                familia, liga, vig["versao"] + 1, dec["resultado"],
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
