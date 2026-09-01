# -*- coding: utf-8 -*-
"""#210 - manifesto dos campos da FootyStats.

Medido em 01/09/2026: o `data_mapper` mapeia 230 campos da FootyStats e 128
deles (56%) nao tinham um unico consumidor no backend. Entre os orfaos estavam
`home_advantage_attack`, `home_advantage_defence`, `btts_percentage_home/away`
e `xg_for_avg_home/away` - exatamente os dados que passamos semanas derivando
por outros caminhos.

A causa nao e descuido. Mapear nao e usar, e nada no sistema cobrava a
diferenca: o mapper despeja um dicionario largo, cada consumidor pesca campo por
nome com cadeia de fallback (`_pick`, `get_stat`, `or baseline`), e tanto o
campo nunca pescado quanto o campo pescado com o nome errado sao silenciosos por
construcao.

Este manifesto torna a diferenca explicita e o CI passa a cobra-la. A regra e
UMA: nenhum campo pode ficar em estado nao declarado.

  CONSUMIDO  - tem consumidor hoje. Perder o consumidor QUEBRA o CI: e assim que
               uma renomeacao apaga um dado sem ninguem perceber.
  PLANEJADO  - mapeado, ainda sem consumidor, com o motivo pelo qual vale a pena.
               E a fila de trabalho, visivel em vez de esquecida.
  DESCARTADO - deliberadamente fora do modelo, com a razao registrada.

Campo novo no mapper sem declaracao aqui quebra o CI. Campo que muda de estado
sozinho aparece no relatorio. Nada volta a passar despercebido.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

CONSUMIDO = "CONSUMIDO"
PLANEJADO = "PLANEJADO"
DESCARTADO = "DESCARTADO"

ESTADOS = (CONSUMIDO, PLANEJADO, DESCARTADO)

# campo -> (estado, motivo)
CAMPOS: Dict[str, Tuple[str, str]] = {
    "attendance": ("DESCARTADO", "metadado de exibicao; nao entra em modelo"),
    "average_possession": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "average_possession_away": ("PLANEJADO", "posse por lado; proxy de controle de jogo"),
    "average_possession_home": ("PLANEJADO", "posse por lado; proxy de controle de jogo"),
    "average_total_goals_2h_per_match": ("PLANEJADO", "segundo tempo; base de mercados de tempo"),
    "average_total_goals_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "average_total_goals_per_match_away": ("PLANEJADO", "media de gols da liga por lado"),
    "average_total_goals_per_match_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "average_total_goals_per_match_home": ("PLANEJADO", "media de gols da liga por lado"),
    "avg_goals_scored_by_away_teams": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "avg_goals_scored_by_home_teams": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_ppg": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_corner_count": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_first_half_cards": ("DESCARTADO", "cartoes por tempo; sem mercado correspondente"),
    "away_team_fouls": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_goal_count": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_goal_count_half_time": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_goal_timings": ("DESCARTADO", "faixas de minuto; sem consumidor previsto no roadmap atual"),
    "away_team_offsides": ("DESCARTADO", "impedimentos; sem mercado correspondente no sistema"),
    "away_team_possession": ("DESCARTADO", "valor pre-jogo do jogo unico; o modelo usa a media de temporada"),
    "away_team_red_cards": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_second_half_cards": ("DESCARTADO", "cartoes por tempo; sem mercado correspondente"),
    "away_team_shots": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_shots_off_target": ("DESCARTADO", "finalizacoes para fora; o modelo usa chutes no alvo"),
    "away_team_shots_on_target": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "away_team_xg": ("DESCARTADO", "valor pre-jogo do jogo unico; o modelo usa a media de temporada"),
    "away_team_yellow_cards": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "btts_2h_percentage": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "btts_and_win_percentage": ("PLANEJADO", "BTTS condicionado a vitoria; refina o mercado combinado"),
    "btts_count": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "btts_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "btts_percentage_away": ("PLANEJADO", "ancora empirica de BTTS por lado; e o contrapeso a saida pura de Poisson (#209)"),
    "btts_percentage_home": ("PLANEJADO", "ancora empirica de BTTS por lado; e o contrapeso a saida pura de Poisson (#209)"),
    "btts_percentage_pre_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "cards_against_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "cards_against_per_match_away": ("PLANEJADO", "#214 - cartoes que o adversario provoca, por lado"),
    "cards_against_per_match_home": ("PLANEJADO", "#214 - cartoes que o adversario provoca, por lado"),
    "cards_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "cards_per_match_away": ("PLANEJADO", "#214 - idem: time visitante faz mais falta, e o modelo nao ve isso"),
    "cards_per_match_home": ("PLANEJADO", "#214 - o lambda de cartoes soma medias gerais e ignora o recorte por lado; a Serie B faz 5,57 cartoes/jogo e o sistema usa 4,94"),
    "cards_total": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "cards_variance": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "clean_sheet_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "clean_sheet_percentage_away": ("PLANEJADO", "ancora de solidez defensiva por lado, util no encolhimento do #208"),
    "clean_sheet_percentage_home": ("PLANEJADO", "ancora de solidez defensiva por lado, util no encolhimento do #208"),
    "clean_sheets": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "clean_sheets_away": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "clean_sheets_home": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "common_name": ("DESCARTADO", "metadado de exibicao; nao entra em modelo"),
    "competition_id": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_against_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_against_per_match_away": ("PLANEJADO", "escanteios por lado; o motor v2 usa medias agregadas"),
    "corners_against_per_match_home": ("PLANEJADO", "escanteios por lado; o motor v2 usa medias agregadas"),
    "corners_o105_potential": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_o85_potential": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_o95_potential": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_per_match_away": ("PLANEJADO", "escanteios por lado; o motor v2 usa medias agregadas"),
    "corners_per_match_home": ("PLANEJADO", "escanteios por lado; o motor v2 usa medias agregadas"),
    "corners_potential": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_recorded_matches_overall": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_total": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_total_avg_away": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_total_avg_home": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "corners_total_avg_overall": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "country": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "date_gmt": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "draw_percentage": ("PLANEJADO", "distribuicao de resultados"),
    "draws": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "draws_away": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "draws_home": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "first_team_to_score_percentage": ("PLANEJADO", "quem abre o placar; util para estado de jogo"),
    "fouls_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "fouls_per_match_away": ("PLANEJADO", "faltas; entrada do modelo de cartoes"),
    "fouls_per_match_home": ("PLANEJADO", "faltas; entrada do modelo de cartoes"),
    "fouls_total": ("PLANEJADO", "faltas; entrada do modelo de cartoes"),
    "fts_count": ("PLANEJADO", "contagens absolutas de BTTS/CS/FTS"),
    "fts_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "game_week": ("DESCARTADO", "metadado de exibicao; nao entra em modelo"),
    "goal_difference": ("PLANEJADO", "saldo; sinal agregado de forca"),
    "goal_difference_away": ("PLANEJADO", "saldo; sinal agregado de forca"),
    "goal_difference_home": ("PLANEJADO", "saldo; sinal agregado de forca"),
    "goals_conceded": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_conceded_2h_per_match": ("PLANEJADO", "segundo tempo; base de mercados de tempo"),
    "goals_conceded_away": ("PLANEJADO", "gols por lado em contagem absoluta"),
    "goals_conceded_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "goals_conceded_home": ("PLANEJADO", "gols por lado em contagem absoluta"),
    "goals_conceded_min_0_to_10": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_conceded_min_81_to_90": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_conceded_per_match_away": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_conceded_per_match_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "goals_conceded_per_match_home": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_conceded_per_match_overall": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_scored": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_scored_2h_per_match": ("PLANEJADO", "segundo tempo; base de mercados de tempo"),
    "goals_scored_away": ("PLANEJADO", "gols por lado em contagem absoluta"),
    "goals_scored_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "goals_scored_home": ("PLANEJADO", "gols por lado em contagem absoluta"),
    "goals_scored_min_0_to_10": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_11_to_20": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_21_to_30": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_31_to_40": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_41_to_50": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_51_to_60": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_61_to_70": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_71_to_80": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_min_81_to_90": ("DESCARTADO", "faixas de minuto de gol; sem consumidor previsto"),
    "goals_scored_per_match_away": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_scored_per_match_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "goals_scored_per_match_home": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "goals_scored_per_match_overall": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_advantage_attack": ("PLANEJADO", "vantagem de mando pronta da FootyStats; hoje o modelo a deriva de seasonAVG_home/away (#201)"),
    "home_advantage_defence": ("PLANEJADO", "vantagem de mando pronta da FootyStats; hoje o modelo a deriva de seasonAVG_home/away (#201)"),
    "home_advantage_overall": ("PLANEJADO", "vantagem de mando pronta da FootyStats; hoje o modelo a deriva de seasonAVG_home/away (#201)"),
    "home_advantage_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_ppg": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_corner_count": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_first_half_cards": ("DESCARTADO", "cartoes por tempo; sem mercado correspondente"),
    "home_team_fouls": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_goal_count": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_goal_count_half_time": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_goal_timings": ("DESCARTADO", "faixas de minuto; sem consumidor previsto no roadmap atual"),
    "home_team_offsides": ("DESCARTADO", "impedimentos; sem mercado correspondente no sistema"),
    "home_team_possession": ("DESCARTADO", "valor pre-jogo do jogo unico; o modelo usa a media de temporada"),
    "home_team_red_cards": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_second_half_cards": ("DESCARTADO", "cartoes por tempo; sem mercado correspondente"),
    "home_team_shots": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_shots_off_target": ("DESCARTADO", "finalizacoes para fora; o modelo usa chutes no alvo"),
    "home_team_shots_on_target": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "home_team_xg": ("DESCARTADO", "valor pre-jogo do jogo unico; o modelo usa a media de temporada"),
    "home_team_yellow_cards": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "id": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "league_position": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "loss_percentage": ("PLANEJADO", "distribuicao de resultados"),
    "losses": ("PLANEJADO", "distribuicao de resultados"),
    "losses_away": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "losses_home": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "matches_played": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "matches_played_away": ("PLANEJADO", "contagem por recorte; o #208 depende dela e hoje cai para games_played"),
    "matches_played_home": ("PLANEJADO", "contagem por recorte; o #208 depende dela e hoje cai para games_played"),
    "minutes_per_goal_conceded": ("PLANEJADO", "ritmo de gol; alternativa a media por jogo"),
    "minutes_per_goal_scored": ("PLANEJADO", "ritmo de gol; alternativa a media por jogo"),
    "odds_btts_no": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_btts_yes": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_corners_over_105": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_corners_over_115": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_corners_over_85": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_corners_over_95": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_away_team_win": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_draw": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_home_team_win": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_over15": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_over25": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_over35": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_over45": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "odds_ft_under25": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "offsides_per_match": ("DESCARTADO", "impedimentos; sem mercado correspondente no sistema"),
    "over05_cards_percentage": ("DESCARTADO", "linha de cartoes fora do catalogo de mercados"),
    "over05_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "over105_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over115_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over125_corners_percentage": ("PLANEJADO", "taxa empirica de escanteios por linha"),
    "over135_corners_percentage": ("PLANEJADO", "taxa empirica de escanteios por linha"),
    "over145_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over15_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over15_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "over25_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over25_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over35_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over35_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "over45_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over45_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "over55_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over55_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "over65_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over65_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over75_cards_percentage": ("CONSUMIDO", "ancora empirica de cartoes por linha; consumida desde o #215 para julgar o calibrador"),
    "over75_corners_percentage": ("PLANEJADO", "taxa empirica de escanteios por linha"),
    "over85_cards_percentage": ("PLANEJADO", "taxa empirica de cartoes por linha"),
    "over85_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over95_corners_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over_15_percentage_pre_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over_25_percentage_pre_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over_35_percentage_pre_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "over_45_percentage_pre_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "points_per_game": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "points_per_game_away": ("PLANEJADO", "forca por lado independente de gols; entra como prior de amostra curta"),
    "points_per_game_home": ("PLANEJADO", "forca por lado independente de gols; entra como prior de amostra curta"),
    "points_per_game_overall": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "points_per_game_recent": ("PLANEJADO", "forma recente em pontos"),
    "pre_match_away_ppg": ("PLANEJADO", "PPG pre-jogo da propria FootyStats"),
    "pre_match_home_ppg": ("PLANEJADO", "PPG pre-jogo da propria FootyStats"),
    "prediction_risk": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "referee": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "scored_both_halves_percentage": ("PLANEJADO", "distribuicao de gols por tempo"),
    "season": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "shots_off_target_per_match": ("DESCARTADO", "finalizacoes para fora; o modelo usa chutes no alvo"),
    "shots_on_target_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "shots_on_target_per_match_away": ("PLANEJADO", "finalizacoes por lado; proxy de volume ofensivo"),
    "shots_on_target_per_match_home": ("PLANEJADO", "finalizacoes por lado; proxy de volume ofensivo"),
    "shots_per_match": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "shots_per_match_away": ("PLANEJADO", "finalizacoes por lado; proxy de volume ofensivo"),
    "shots_per_match_home": ("PLANEJADO", "finalizacoes por lado; proxy de volume ofensivo"),
    "stadium": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "stadium_location": ("DESCARTADO", "metadado de exibicao; nao entra em modelo"),
    "status": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "team_a_name": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "team_b_name": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "team_id": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "team_name": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "timestamp": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "total_goal_count": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "total_goals_at_half_time": ("PLANEJADO", "intervalo; base de mercados de primeiro tempo"),
    "under05_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "under15_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "under25_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "under35_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "under45_percentage": ("PLANEJADO", "taxa empirica de gols da temporada; ancora direta dos mercados de linha"),
    "win_percentage": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "win_percentage_away": ("PLANEJADO", "aproveitamento por lado"),
    "win_percentage_home": ("PLANEJADO", "aproveitamento por lado"),
    "wins": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "wins_away": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "wins_home": ("PLANEJADO", "resultado por lado; base de forca relativa sem depender de gols"),
    "xg_against_avg": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "xg_against_avg_away": ("PLANEJADO", "xG por lado; o xg_filter usa apenas o agregado"),
    "xg_against_avg_home": ("PLANEJADO", "xG por lado; o xg_filter usa apenas o agregado"),
    "xg_for_avg": ("CONSUMIDO", "lido por pelo menos um consumidor no backend"),
    "xg_for_avg_away": ("PLANEJADO", "xG por lado; o xg_filter usa apenas o agregado"),
    "xg_for_avg_home": ("PLANEJADO", "xG por lado; o xg_filter usa apenas o agregado"),}


# ── verificacao ──────────────────────────────────────────────────────

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MAPPER = os.path.join(_RAIZ, "backend", "services", "data_mapper.py")
_IGNORADOS = {"data_mapper.py", "footystats_manifest.py"}


def campos_mapeados(caminho: str = None) -> List[str]:
    """Campos que o data_mapper efetivamente produz."""
    with open(caminho or _MAPPER, encoding="utf-8") as f:
        src = f.read()
    return sorted(set(re.findall(r'^\s*"([a-z0-9_]+)"\s*:', src, re.M)))


def campos_consumidos(raiz: str = None) -> set:
    """Campos citados por algum arquivo do backend fora do proprio mapper."""
    raiz = raiz or os.path.join(_RAIZ, "backend")
    alvos = set(CAMPOS) | set(campos_mapeados())
    achados = set()
    for pasta, _, arquivos in os.walk(raiz):
        if "__pycache__" in pasta:
            continue
        for nome in arquivos:
            # o proprio manifesto cita todos os campos como chave; se ele
            # entrasse na varredura, todo campo pareceria consumido e a
            # verificacao viraria um espelho.
            if not nome.endswith(".py") or nome in _IGNORADOS:
                continue
            with open(os.path.join(pasta, nome), encoding="utf-8", errors="ignore") as f:
                texto = f.read()
            for campo in alvos - achados:
                if re.search(r'["\']' + re.escape(campo) + r'["\']', texto):
                    achados.add(campo)
    return achados


def verificar() -> Dict[str, List[str]]:
    """Confronta manifesto, mapper e consumidores.

    `bloqueia` reune o que nao pode ir para producao; `avisa` reune o que so
    precisa de atualizacao do manifesto.
    """
    mapeados = set(campos_mapeados())
    consumidos = campos_consumidos()
    declarados = set(CAMPOS)

    bloqueia: List[str] = []
    avisa: List[str] = []

    for campo in sorted(mapeados - declarados):
        bloqueia.append(
            f"{campo}: mapeado pelo data_mapper e ausente do manifesto. "
            f"Declare como {CONSUMIDO}, {PLANEJADO} ou {DESCARTADO}."
        )

    for campo in sorted(declarados):
        estado, _motivo = CAMPOS[campo]
        if estado not in ESTADOS:
            bloqueia.append(f"{campo}: estado '{estado}' nao existe.")
            continue
        if estado == CONSUMIDO and campo not in consumidos:
            bloqueia.append(
                f"{campo}: declarado {CONSUMIDO} e nenhum consumidor o le mais. "
                f"Uma renomeacao provavelmente o desligou em silencio."
            )
        if estado in (PLANEJADO, DESCARTADO) and campo in consumidos:
            avisa.append(f"{campo}: ganhou consumidor; promova para {CONSUMIDO} no manifesto.")
        if campo not in mapeados:
            avisa.append(f"{campo}: declarado e o data_mapper nao produz mais; remova do manifesto.")

    return {"bloqueia": bloqueia, "avisa": avisa}


def resumo() -> Dict[str, int]:
    contagem = {e: 0 for e in ESTADOS}
    for estado, _ in CAMPOS.values():
        contagem[estado] = contagem.get(estado, 0) + 1
    contagem["TOTAL"] = len(CAMPOS)
    return contagem


def fila_de_trabalho() -> List[Tuple[str, str]]:
    """Campos PLANEJADO, ordenados: a divida de dados, visivel."""
    return sorted((c, m) for c, (e, m) in CAMPOS.items() if e == PLANEJADO)
