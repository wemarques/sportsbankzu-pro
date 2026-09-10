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
from backend.modeling.calibragem import estimador, governanca, limiares, repositorio

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


def executar(caminho_semente: Optional[str] = None) -> dict:
    """Um ciclo completo. Nunca levanta: falha aberta, como o resto do cron."""
    resumo = {"celulas": 0, "adotadas": 0, "encurtadas": 0, "revertidas": 0,
              "congeladas": 0, "jogos": 0, "erro": None}
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
            vig = vigentes.get(chave) or {"versao": VERSAO_LEGADO, "a": 0.0, "b": 1.0}
            servidos = por_celula.get(chave, [])

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
                if anterior is None:
                    resultado = dict(resultado)
                    resultado["motivo"] = (
                        f"sem_anterior; {resultado['motivo']}"
                        if resultado["motivo"] else "sem_anterior")
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
        for (familia, liga), dec in decisoes.items():
            if liga:
                continue
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
