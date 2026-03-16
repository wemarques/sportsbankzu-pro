# Regras de Correção do Sistema — Placares ao Vivo

## Problema Original
Jogos ao vivo mostravam placar **0 - 0** mesmo quando o placar real era diferente (ex: Preston 1-3 Oxford United exibido como 0-0 aos 90').

## Causa Raiz
Três falhas em cadeia:
1. **FootyStats `todays-matches`** retorna `homeGoalCount: -1` para jogos ao vivo (dados indisponíveis)
2. **Frontend `normalizeMatch`** forçava `{home: 0, away: 0}` como default para qualquer jogo ao vivo sem score
3. **Overlay `/live-scores`** recebia `score: null` e não sobrescrevia o 0-0 fake do frontend

## Correções Aplicadas

### 1. Backend — Fallback via endpoint `match` (defesa em profundidade)
**Arquivo:** `backend/routes/fixtures.py`
- Quando `todays-matches` não tem dados de gol para um jogo ao vivo, o sistema agora faz fallback para o endpoint `match` (detalhes individuais) que retorna dados mais atualizados.
- Cache de 30s garante dados frescos sem sobrecarregar a API.

### 2. Backend — Cache reduzido para 30s
**Arquivo:** `backend/services/footstats_client.py`
- `get_live_scores()`: cache de 1 min → **30s**
- `get_match_live_details()`: cache de 1 min → **30s**

### 3. Frontend — Não defaultar 0-0 para jogos ao vivo
**Arquivo:** `frontend/next/src/app/dashboard/page.tsx`
- `normalizeMatch()`: default `{home: 0, away: 0}` agora só para jogos **finalizados** (não mais para "live")
- Jogos ao vivo sem score mostram `- : -` com animação pulsante (indicando carregamento)

### 4. Frontend — Polling mais rápido
**Arquivo:** `frontend/next/src/hooks/useLivePolling.ts`
- Polling com jogos ao vivo: 30s → **15s**
- Polling sem jogos ao vivo: 120s (mantido)

### 5. Backend — Janela de inferência de status
**Arquivo:** `backend/routes/fixtures.py`
- Janela de inferência "scheduled → live" via kickoff: 150 min → **120 min**
- Evita promover jogos já finalizados que a API reporta como "incomplete"

## Performance Resultante
| Métrica | Antes | Depois |
|---------|-------|--------|
| Cache do servidor | 60s | 30s |
| Polling do dashboard | 30s | 15s |
| Delay máximo estimado | ~90s | ~45s |
| Fallback para gols | Nenhum | endpoint `match` |
| Default de score vivo | 0-0 (fake) | `- : -` (loading) |

## Regras para Futuras Correções

1. **Nunca inventar score** — se a API não retorna gol, mostrar indicador de carregamento, não 0-0
2. **Defesa em profundidade** — usar fallback em cadeia: `todays-matches` → `match` → manter último score válido
3. **Validar com dados reais** — sempre confirmar o score real antes de declarar bug resolvido (ex: consultar foxsports.com, sofascore.com)
4. **Testar com nomes variantes** — times como Vasco (Club de Regatas Vasco da Gama vs Vasco) devem casar corretamente no normalizeTeamName
5. **Cuidado com status "incomplete"** — FootyStats usa "incomplete" para jogos não finalizados, tratar como "scheduled" e deixar o heurístico de kickoff decidir
