# PROMPT — Corrigir Sistema de Auditoria: Priorizar Causa Raiz + Dados de Escanteios + Reverter Correções de Sintoma

## CONTEXTO

O sistema de auditoria Mistral tem 3 problemas:

1. **Sugere correções de sintoma em vez de causa raiz.** Exemplo real: sugeriu `over_25_threshold: 68 → 55` (ajustar threshold) quando o problema real era `lambda_away: 2.00 → 1.20` (lambda inflado). Lambda é a BASE de todos os cálculos — se lambda está correto, os thresholds não precisam de ajuste.

2. **Não inclui dados reais de escanteios na auditoria.** O `actual_result` passado para o auditor contém gols, BTTS, resultado 1X2, mas NÃO contém escanteios reais. A Mistral detecta erro em "Escanteios Over 9.5" mas não sabe quantos escanteios realmente aconteceram.

3. **O usuário já aplicou correções sugeridas** (lambda_away 2.00→1.20, over_25_threshold 68→55, btts_weight_defense 0.50→0.70) via botão "Aplicar Correção". A correção de threshold (over_25: 68→55) trata sintoma e pode causar problemas em outros jogos — deve ser revertida.

## ARQUIVOS A MODIFICAR

1. `backend/ai/prompt_templates.py` — prompts de auditoria pós-jogo e batch
2. `backend/routes/ai_analysis.py` — incluir dados de escanteios e cartões no actual_result
3. `backend/routes/ai_analysis.py` — adicionar validação antes de aplicar correções de threshold

---

## CORREÇÃO 1 — Incluir escanteios e cartões reais no actual_result

Arquivo: `backend/routes/ai_analysis.py`

Na função `audit_match()`, o bloco que monta `actual_result` (~linhas 251-258) não inclui escanteios nem cartões. O `full_match` retornado por `_get_full_match_record` contém `stats` com `homeCornersCount`, `awayCornersCount`, `home_team_yellow_cards`, etc.

Substituir o bloco:

```python
            actual_result = {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": total_goals,
                "btts": btts,
                "result_1x2": result_1x2,
                "score": f"{home_goals}x{away_goals}",
            }
```

Por:

```python
            # Extract corner counts from match stats
            match_stats = full_match.get("stats", {})
            home_corners = match_stats.get("homeCornersCount") or full_match.get("home_team_corner_count") or 0
            away_corners = match_stats.get("awayCornersCount") or full_match.get("away_team_corner_count") or 0
            try:
                home_corners = int(home_corners) if int(home_corners) >= 0 else 0
                away_corners = int(away_corners) if int(away_corners) >= 0 else 0
            except (ValueError, TypeError):
                home_corners, away_corners = 0, 0
            total_corners = home_corners + away_corners

            # Extract card counts
            home_yellow = match_stats.get("home_team_yellow_cards") or full_match.get("home_team_yellow_cards") or 0
            away_yellow = match_stats.get("away_team_yellow_cards") or full_match.get("away_team_yellow_cards") or 0
            home_red = match_stats.get("home_team_red_cards") or full_match.get("home_team_red_cards") or 0
            away_red = match_stats.get("away_team_red_cards") or full_match.get("away_team_red_cards") or 0
            try:
                home_yellow = int(home_yellow) if int(home_yellow) >= 0 else 0
                away_yellow = int(away_yellow) if int(away_yellow) >= 0 else 0
                total_cards = home_yellow + away_yellow
            except (ValueError, TypeError):
                home_yellow, away_yellow, total_cards = 0, 0, 0

            actual_result = {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": total_goals,
                "btts": btts,
                "result_1x2": result_1x2,
                "score": f"{home_goals}x{away_goals}",
                # Corner data for corner market audit
                "home_corners": home_corners,
                "away_corners": away_corners,
                "total_corners": total_corners,
                # Card data for card market audit
                "home_yellow_cards": home_yellow,
                "away_yellow_cards": away_yellow,
                "total_cards": total_cards,
                "home_red_cards": int(home_red) if str(home_red).isdigit() else 0,
                "away_red_cards": int(away_red) if str(away_red).isdigit() else 0,
            }
```

---

## CORREÇÃO 2 — Priorizar lambda nas correções sugeridas pela auditoria

Arquivo: `backend/ai/prompt_templates.py`

Na função `audit_post_match_prompt` (~linha 77), adicionar regra de priorização ao prompt.

Após a lista de tarefas (item 6, "Sugira correcoes ESPECIFICAS"), adicionar:

```python
        REGRAS CRITICAS PARA SUGESTAO DE CORRECOES:
        1. PRIORIDADE MAXIMA: Correcoes de lambda (lambda_home, lambda_away, lambda_total).
           Lambda e a base de TODOS os calculos downstream (probabilidades, EV, thresholds).
           Se lambda esta errado, TODAS as probabilidades estao erradas.
           SEMPRE sugira correcao de lambda ANTES de correcoes de threshold.

        2. PRIORIDADE MEDIA: Correcoes de peso/multiplicador (btts_weight_defense, corner_multiplier).
           Estes afetam mercados especificos sem afetar a base de calculo.

        3. PRIORIDADE BAIXA: Correcoes de threshold (over_25_threshold, etc).
           SOMENTE sugira threshold se o lambda ja estiver correto e o threshold ainda gerar erro.
           Na maioria dos casos, corrigir lambda torna desnecessario ajustar threshold.
           NUNCA sugira threshold_adjustment se lambda_multiplier tambem esta sendo sugerido
           — a correcao de lambda ja resolve o problema de threshold downstream.

        4. Para mercados de ESCANTEIOS, sempre compare:
           - Escanteios reais (home_corners + away_corners do resultado) vs projecao do modelo
           - Potenciais da FootyStats vs escanteios reais
           - Se a liga tem dados suficientes de escanteios (corners_recorded_matches_num)
           Se os dados de escanteios reais estiverem disponiveis no resultado, AVALIE a precisao
           do motor de corners e sugira corner_multiplier se necessario.

        5. Para CARTOES, compare:
           - Cartoes reais (total_cards do resultado) vs media esperada
           - Se houve cartao vermelho, avalie impacto no jogo (vantagem numerica)
```

Também atualizar o schema de corrections para incluir prioridade:

```python
            "corrections": [
                {{
                    "type": "lambda_multiplier|threshold_adjustment|weight_adjustment|corner_multiplier",
                    "parameter": "nome especifico do parametro a ajustar",
                    "current_value": 0.0,
                    "suggested_value": 0.0,
                    "reason": "Justificativa baseada nos dados",
                    "confidence": 75,
                    "impact": "LOW|MEDIUM|HIGH",
                    "priority": "LAMBDA_ROOT_CAUSE|WEIGHT_ADJUSTMENT|THRESHOLD_SYMPTOM"
                }}
            ],
```

---

## CORREÇÃO 3 — Mesma regra no prompt de batch audit

Arquivo: `backend/ai/prompt_templates.py`

Na função `batch_audit_model_evaluation_prompt` (~linha 136), adicionar as mesmas regras após o item 5 da tarefa:

```python
        REGRAS CRITICAS PARA CORRECOES:
        - PRIORIDADE 1: Lambda (causa raiz). Se lambdas estao sobre/sub-estimando, corrigir PRIMEIRO.
        - PRIORIDADE 2: Pesos/multiplicadores (btts_weight, corner_multiplier). Afetam mercados especificos.
        - PRIORIDADE 3: Thresholds. SOMENTE se lambda e pesos ja estiverem corretos.
        - NUNCA sugira threshold_adjustment junto com lambda_multiplier para o mesmo problema.
        - Para ESCANTEIOS: inclua dados reais de corners quando disponiveis e sugira corner_multiplier.
        - Para CARTOES: compare cards reais vs media esperada.
```

---

## CORREÇÃO 4 — Validação antes de aplicar correções de threshold

Arquivo: `backend/routes/ai_analysis.py`

Na função `apply_audit_correction()` (~linha 292), adicionar validação que BLOQUEIA threshold_adjustment quando lambda_multiplier é a causa raiz provável.

Substituir:

```python
        # Apply threshold corrections immediately
        if correction.correction_type == "threshold_adjustment":
            _apply_threshold_correction(correction)
```

Por:

```python
        # Apply corrections with validation
        if correction.correction_type == "threshold_adjustment":
            # Validate: threshold corrections should only be applied if the change is < 15%
            # Large threshold changes (>15%) usually indicate a lambda problem, not a threshold problem
            if correction.old_value > 0:
                change_pct = abs(correction.new_value - correction.old_value) / correction.old_value
                if change_pct > 0.15:
                    logger.warning(
                        f"[Correction] BLOCKED threshold_adjustment {correction.parameter_name}: "
                        f"{correction.old_value} → {correction.new_value} (change={change_pct:.1%} > 15%). "
                        f"Large threshold changes usually indicate a lambda problem. "
                        f"Consider applying lambda_multiplier correction first."
                    )
                    return {
                        "status": "blocked",
                        "message": (
                            f"Correcao bloqueada: mudanca de {change_pct:.0%} no threshold e muito grande. "
                            f"Isso geralmente indica um problema de lambda, nao de threshold. "
                            f"Aplique a correcao de lambda primeiro e reavalie se o threshold ainda precisa de ajuste."
                        ),
                        "old_value": correction.old_value,
                        "new_value": correction.new_value,
                    }
            _apply_threshold_correction(correction)
        
        elif correction.correction_type == "lambda_multiplier":
            # Lambda corrections are always allowed — they fix the root cause
            logger.info(
                f"[Correction] Lambda correction applied: {correction.parameter_name} "
                f"{correction.old_value} → {correction.new_value}"
            )
            # Lambda corrections are logged and picked up by get_lambda_corrections()
            # on the next fixture build cycle
```

---

## CORREÇÃO 5 — Reverter threshold over_25 aplicado incorretamente

O usuário já aplicou `over_25_threshold: 68 → 55` via botão "Aplicar Correção". Esse valor está na tabela `thresholds` do banco de dados em produção. Precisa ser revertido.

Adicionar um endpoint de reversão ou usar o existente:

Arquivo: `backend/routes/ai_analysis.py`

Criar rota de reversão de correção:

```python
@router.post("/correction/revert")
async def revert_correction(
    parameter_name: str = Query(..., description="Nome do parametro a reverter"),
    original_value: float = Query(..., description="Valor original a restaurar"),
):
    """Revert a previously applied correction."""
    from backend import audit as audit_db
    from datetime import datetime

    try:
        conn = audit_db.init_db()
        cursor = conn.cursor()
        
        # Extract market name from parameter
        parts = parameter_name.split(".")
        market = parts[0] if len(parts) == 1 else parts[1] if len(parts) >= 2 else parameter_name
        
        if audit_db._use_postgres():
            cursor.execute(
                "UPDATE thresholds SET safe_threshold = %s, last_updated = %s WHERE market = %s",
                (original_value, datetime.now(), market),
            )
        else:
            cursor.execute(
                "UPDATE thresholds SET safe_threshold = ?, last_updated = ? WHERE market = ?",
                (original_value, datetime.now(), market),
            )
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # Log the reversion
        audit_db.log_correction(
            match_id="manual_revert",
            league="all",
            correction_type="threshold_revert",
            parameter_name=parameter_name,
            old_value=0,  # unknown current
            new_value=original_value,
            suggested_by="manual",
            applied_by="user",
            audit_confidence=100,
            reason=f"Revert: threshold was incorrectly adjusted (symptom, not root cause)",
        )

        return {
            "status": "success" if affected > 0 else "no_change",
            "message": f"Threshold '{market}' revertido para {original_value}",
            "rows_affected": affected,
        }
    except Exception as e:
        logger.error(f"Error reverting correction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

NOTA: Como o over_25_threshold foi aplicado no banco de produção (Vercel), a reversão precisa ser executada lá. Se a rota acima não for suficiente, pode ser necessário executar diretamente:

```python
# Via API: POST /api/ai/correction/revert?parameter_name=over_25_threshold&original_value=68
```

---

## SOBRE AS CORREÇÕES JÁ APLICADAS

O usuário aplicou 3 correções pelo botão "Aplicar Correção":

| Correção | Tipo | De → Para | Avaliação |
|----------|------|-----------|-----------|
| lambda_away | lambda_multiplier | 2.00 → 1.20 | **MANTER.** Lambda era claramente inflado. Esta é correção de causa raiz. |
| over_25_threshold | threshold_adjustment | 68 → 55 | **REVERTER.** Trata sintoma. Com lambda corrigido, o Poisson geraria Over 2.5 ≈ 48-52% automaticamente. O threshold de 55 vai causar problemas em jogos onde Over 2.5 é legítimo. |
| btts_weight_defense | weight_adjustment | 0.50 → 0.70 | **MANTER COM CAUTELA.** O peso de 0.70 é agressivo — ideal seria 0.65. Mas como já foi aplicado, monitorar por 2-3 rodadas antes de ajustar novamente. |

A ação de reversão do threshold pode ser feita pela nova rota `POST /api/ai/correction/revert` após implementar, ou manualmente via SQL no banco de produção.

---

## VALIDAÇÃO

```bash
pytest -q
cd frontend/next && npm run build
```

Verificar:
1. A auditoria pós-jogo deve incluir `total_corners`, `home_corners`, `away_corners`, `total_cards` no resultado
2. As correções sugeridas pela Mistral devem priorizar lambda sobre threshold
3. Tentar aplicar threshold com mudança > 15% deve ser bloqueado
4. O endpoint de reversão deve funcionar

Commit:
```
fix: audit system prioritizes lambda root cause over threshold symptoms

- Include actual corner counts and card data in post-match audit result
- Audit prompt now instructs Mistral to prioritize lambda > weights > thresholds
- Block threshold corrections with >15% change (likely lambda problem)
- Add /correction/revert endpoint for reverting incorrect corrections
- Batch audit prompt updated with same prioritization rules
```

Push:
```bash
git push origin main
```

---

## REGRAS

- NÃO alterar lógica de cálculo de lambda (lambda_calculator.py)
- NÃO alterar o Corners Engine v2
- NÃO alterar o frontend
- As mudanças são nos prompts da Mistral e na lógica de aplicação de correções
- Se `pytest -q` falhar, corrigir antes de commitar
