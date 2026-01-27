from typing import Dict, Any, List

def build_quadro_response(league: str, date: str, incluir_simples: bool, incluir_duplas: bool, incluir_triplas: bool, incluir_governanca: bool, formato: str) -> Dict[str, Any]:
    from backend.main import load_fixtures_from_csv
    jogos = load_fixtures_from_csv(league, date)
    if not jogos:
        return {
            "quadro_texto": "Nenhum jogo encontrado para os filtros selecionados.",
            "jogos_count": 0,
            "duplas_count": 0,
            "triplas_count": 0,
            "regime": "N/A",
            "volatilidade": "N/A",
        }
    from backend.main import calcular_regime_e_volatilidade
    regime, volatilidade = calcular_regime_e_volatilidade(league, jogos)
    if formato == "whatsapp":
        from backend.main import gerar_quadro_resumo_whatsapp
        quadro_texto = gerar_quadro_resumo_whatsapp(
            liga=league,
            jogos=jogos,
            regime=regime,
            volatilidade=volatilidade,
            incluir_simples=incluir_simples,
            incluir_duplas=incluir_duplas,
        )
    else:
        from backend.main import gerar_quadro_resumo
        quadro_texto = gerar_quadro_resumo(
            liga=league,
            jogos=jogos,
            regime=regime,
            volatilidade=volatilidade,
            incluir_simples=incluir_simples,
            incluir_duplas=incluir_duplas,
            incluir_triplas=incluir_triplas,
            incluir_governanca=incluir_governanca,
        )
    from backend.main import identificar_duplas_safe, identificar_triplas_safe
    duplas, motivo_duplas = identificar_duplas_safe(jogos) if incluir_duplas else ([], {})
    triplas, motivo_triplas = identificar_triplas_safe(jogos) if incluir_triplas else ([], {})
    return {
        "quadro_texto": quadro_texto,
        "jogos_count": len(jogos) if incluir_simples else 0,
        "duplas_count": len(duplas),
        "triplas_count": len(triplas),
        "regime": regime,
        "volatilidade": volatilidade,
        "duplas_motivo": motivo_duplas,
        "triplas_motivo": motivo_triplas,
    }
