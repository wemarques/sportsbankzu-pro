/**
 * Local deterministic audit — evaluates picks vs actual results entirely
 * in the browser using match data already loaded in the dashboard.
 *
 * This bypasses the backend Lambda entirely, avoiding the API Gateway
 * 29-second timeout that caused persistent 502/503 errors.
 */

import type { Match } from "./leagues";
import type {
  BatchAuditResult,
  BatchAuditMatchResult,
  BatchAuditMarketAccuracy,
  ModelUpdateRecommendation,
} from "./api";

/** Evaluate a single pick against the actual result. */
function evaluatePick(
  mercado: string,
  totalGoals: number,
  btts: boolean,
  result1x2: "1" | "X" | "2"
): boolean {
  const m = mercado.trim().toUpperCase();

  // Over/Under markets
  for (const threshold of [0.5, 1.5, 2.5, 3.5, 4.5]) {
    const ts = String(threshold);
    if ((m.includes("UNDER") || m.includes("MENOS") || m.includes("ABAIXO")) && m.includes(ts)) {
      return totalGoals < threshold;
    }
    if ((m.includes("OVER") || m.includes("MAIS") || m.includes("ACIMA")) && m.includes(ts)) {
      return totalGoals > threshold;
    }
  }

  // BTTS
  if (m.includes("BTTS") || m.includes("AMBAS")) {
    if (m.includes("NAO") || m.includes("NO") || m.includes("NÃO")) return !btts;
    if (m.includes("SIM") || m.includes("YES")) return btts;
    return btts; // bare "BTTS" defaults to yes
  }

  // Double Chance
  if (m.startsWith("DC 1X") || m.startsWith("1X") || m.includes("CASA OU EMPATE")) {
    return result1x2 === "1" || result1x2 === "X";
  }
  if (m.startsWith("DC 12") || m.startsWith("12") || m.includes("CASA OU FORA")) {
    return result1x2 === "1" || result1x2 === "2";
  }
  if (m.startsWith("DC X2") || m.startsWith("X2") || m.includes("EMPATE OU FORA")) {
    return result1x2 === "X" || result1x2 === "2";
  }

  // 1X2
  if (m === "1" || m === "VITORIA CASA" || m === "HOME WIN" || m === "CASA") {
    return result1x2 === "1";
  }
  if (m === "X" || m === "EMPATE" || m === "DRAW") {
    return result1x2 === "X";
  }
  if (m === "2" || m === "VITORIA FORA" || m === "AWAY WIN" || m === "FORA") {
    return result1x2 === "2";
  }

  return false;
}

/**
 * Compute model update recommendation based on audit metrics.
 * Uses Brier score, lambda error, and accuracy thresholds to determine
 * whether the model needs recalibration/retraining.
 */
function computeModelUpdateRecommendation(
  overallAccuracy: number,
  safeAccuracy: number,
  avgBrier: number,
  avgLambdaError: number,
  marketAccuracy: BatchAuditMarketAccuracy[],
  auditedMatches: number,
): ModelUpdateRecommendation {
  const reasons: string[] = [];
  const actions: string[] = [];
  let score = 0; // higher = more urgent

  // Not enough data to make a recommendation
  if (auditedMatches < 3) {
    return {
      needs_update: false,
      urgency: "BAIXA",
      reasons: ["Dados insuficientes para avaliação (mínimo 3 jogos finalizados)"],
      recommended_actions: ["Aguardar mais jogos finalizados para avaliação"],
      next_retrain_suggestion: "Após acumular mais resultados",
    };
  }

  // 1. Brier Score evaluation (lower is better, >0.25 is concerning, >0.35 is bad)
  if (avgBrier > 0.35) {
    reasons.push(`Brier Score muito alto (${avgBrier.toFixed(4)}) — calibração das probabilidades está fraca`);
    actions.push("Recalibrar modelos de probabilidade (Isotonic Regression)");
    score += 3;
  } else if (avgBrier > 0.25) {
    reasons.push(`Brier Score acima do ideal (${avgBrier.toFixed(4)}) — probabilidades precisam de ajuste`);
    actions.push("Ajustar thresholds de probabilidade");
    score += 1;
  }

  // 2. Lambda error evaluation (>1.5 goals off is concerning, >2.0 is bad)
  if (avgLambdaError > 2.0) {
    reasons.push(`Erro médio de lambda muito alto (${avgLambdaError.toFixed(2)} gols) — modelo Poisson desajustado`);
    actions.push("Re-treinar parâmetros lambda do modelo Poisson");
    score += 3;
  } else if (avgLambdaError > 1.5) {
    reasons.push(`Erro médio de lambda elevado (${avgLambdaError.toFixed(2)} gols)`);
    actions.push("Revisar multiplicadores lambda");
    score += 1;
  }

  // 3. Overall accuracy (< 40% is bad, < 50% is concerning)
  if (overallAccuracy < 40) {
    reasons.push(`Acurácia geral muito baixa (${overallAccuracy.toFixed(1)}%) — modelo precisa de revisão`);
    actions.push("Revisão completa dos modelos estatísticos");
    score += 3;
  } else if (overallAccuracy < 50) {
    reasons.push(`Acurácia geral abaixo de 50% (${overallAccuracy.toFixed(1)}%)`);
    actions.push("Ajustar pesos dos mercados e thresholds");
    score += 2;
  }

  // 4. SAFE accuracy (should be higher than overall; < 55% is a problem)
  if (safeAccuracy < 50) {
    reasons.push(`Picks SAFE com acurácia muito baixa (${safeAccuracy.toFixed(1)}%) — thresholds SAFE precisam recalibração`);
    actions.push("Elevar thresholds mínimos para classificação SAFE");
    score += 3;
  } else if (safeAccuracy < 60) {
    reasons.push(`Picks SAFE com acurácia abaixo do esperado (${safeAccuracy.toFixed(1)}%)`);
    actions.push("Revisar critérios de classificação SAFE");
    score += 1;
  }

  // 5. Market-specific issues (any market with >=5 picks and <30% accuracy)
  for (const ma of marketAccuracy) {
    if (ma.total >= 5 && ma.accuracy_pct < 30) {
      reasons.push(`Mercado "${ma.market}" com acurácia crítica (${ma.accuracy_pct.toFixed(1)}% em ${ma.total} picks)`);
      actions.push(`Recalibrar ou desativar mercado "${ma.market}"`);
      score += 2;
    }
  }

  // Determine urgency
  let urgency: ModelUpdateRecommendation["urgency"];
  if (score >= 7) urgency = "CRITICA";
  else if (score >= 4) urgency = "ALTA";
  else if (score >= 2) urgency = "MEDIA";
  else urgency = "BAIXA";

  const needsUpdate = score >= 2;

  // Next retrain suggestion
  let nextRetrain: string;
  if (score >= 7) nextRetrain = "Imediato — recalibração urgente necessária";
  else if (score >= 4) nextRetrain = "Próximas 24h — agendar recalibração";
  else if (score >= 2) nextRetrain = "Próxima segunda-feira (cron semanal)";
  else nextRetrain = "Manter ciclo semanal atual";

  if (actions.length === 0) {
    actions.push("Manter configuração atual — modelo dentro dos parâmetros");
  }

  if (reasons.length === 0) {
    reasons.push("Todos os indicadores dentro dos parâmetros aceitáveis");
  }

  return {
    needs_update: needsUpdate,
    urgency,
    reasons,
    recommended_actions: actions,
    next_retrain_suggestion: nextRetrain,
  };
}

/**
 * Run deterministic audit on loaded matches — no backend call needed.
 * Returns the same BatchAuditResult shape as the backend endpoint.
 */
export function runLocalAudit(allMatches: Match[]): BatchAuditResult {
  const finished = allMatches.filter(
    (m) => m.status === "finished" && m.score
  );

  if (finished.length === 0) {
    return {
      status: "success",
      total_matches: 0,
      finished_matches: 0,
      audited_matches: 0,
      overall_accuracy: 0,
      safe_accuracy: 0,
      neutro_accuracy: 0,
      safe_correct: 0,
      safe_total: 0,
      neutro_correct: 0,
      neutro_total: 0,
      avg_brier_score: 0,
      avg_lambda_error: 0,
      market_accuracy: [],
      match_results: [],
      model_evaluation: null,
      message: "Nenhum jogo finalizado encontrado para auditar.",
    };
  }

  let safeCorrect = 0;
  let safeTotal = 0;
  let neutroCorrect = 0;
  let neutroTotal = 0;
  const marketStats = new Map<string, { correct: number; total: number }>();
  const lambdaErrors: number[] = [];
  const brierScores: number[] = [];
  const matchResults: BatchAuditMatchResult[] = [];

  for (const match of finished) {
    const homeGoals = match.score!.home;
    const awayGoals = match.score!.away;
    const totalGoals = homeGoals + awayGoals;
    const btts = homeGoals > 0 && awayGoals > 0;
    const result1x2: "1" | "X" | "2" =
      homeGoals > awayGoals ? "1" : homeGoals === awayGoals ? "X" : "2";

    const picks = match.predictions || [];
    let matchCorrect = 0;
    let matchTotal = 0;
    const picksEval: BatchAuditMatchResult["picks"] = [];

    for (const pick of picks) {
      const isCorrect = evaluatePick(pick.mercado, totalGoals, btts, result1x2);

      picksEval.push({
        mercado: pick.mercado,
        status_pick: pick.status,
        resultado: isCorrect ? "ACERTOU" : "ERROU",
      });

      matchTotal++;
      if (isCorrect) matchCorrect++;

      if (pick.status === "SAFE") {
        safeTotal++;
        if (isCorrect) safeCorrect++;
      } else if (pick.status === "NEUTRO") {
        neutroTotal++;
        if (isCorrect) neutroCorrect++;
      }

      const key = pick.mercado.toUpperCase().trim();
      const ms = marketStats.get(key) || { correct: 0, total: 0 };
      ms.total++;
      if (isCorrect) ms.correct++;
      marketStats.set(key, ms);
    }

    // Lambda error
    const lambdaTotal =
      match.stats.lambdaTotal ||
      ((match.stats.lambdaHome || 0) + (match.stats.lambdaAway || 0));
    if (lambdaTotal > 0) {
      lambdaErrors.push(Math.abs(lambdaTotal - totalGoals));
    }

    // Brier score (over 2.5)
    const over25Prob = match.stats.over25Prob;
    if (over25Prob != null) {
      const actualOver25 = totalGoals > 2.5 ? 1 : 0;
      brierScores.push((over25Prob / 100 - actualOver25) ** 2);
    }

    matchResults.push({
      match_id: match.id,
      home_team: match.homeTeam.name,
      away_team: match.awayTeam.name,
      league: match.leagueName,
      score: `${homeGoals}x${awayGoals}`,
      picks: picksEval,
      picks_correct: matchCorrect,
      picks_total: matchTotal,
    });
  }

  const overallTotal = safeTotal + neutroTotal;
  const overallCorrect = safeCorrect + neutroCorrect;

  const marketAccuracy: BatchAuditMarketAccuracy[] = Array.from(
    marketStats.entries()
  )
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([market, data]) => ({
      market,
      correct: data.correct,
      total: data.total,
      accuracy_pct:
        data.total > 0
          ? Math.round((data.correct / data.total) * 1000) / 10
          : 0,
    }));

  const overallAcc = overallTotal > 0
    ? Math.round((overallCorrect / overallTotal) * 1000) / 10
    : 0;
  const safeAcc = safeTotal > 0
    ? Math.round((safeCorrect / safeTotal) * 1000) / 10
    : 0;
  const avgBrier = brierScores.length > 0
    ? brierScores.reduce((a, b) => a + b, 0) / brierScores.length
    : 0;
  const avgLambda = lambdaErrors.length > 0
    ? lambdaErrors.reduce((a, b) => a + b, 0) / lambdaErrors.length
    : 0;

  const modelUpdateRec = computeModelUpdateRecommendation(
    overallAcc,
    safeAcc,
    avgBrier,
    avgLambda,
    marketAccuracy,
    matchResults.length,
  );

  return {
    status: "success",
    total_matches: finished.length,
    finished_matches: finished.length,
    audited_matches: matchResults.length,
    overall_accuracy: overallAcc,
    safe_accuracy: safeAcc,
    neutro_accuracy:
      neutroTotal > 0
        ? Math.round((neutroCorrect / neutroTotal) * 1000) / 10
        : 0,
    safe_correct: safeCorrect,
    safe_total: safeTotal,
    neutro_correct: neutroCorrect,
    neutro_total: neutroTotal,
    avg_brier_score: avgBrier,
    avg_lambda_error: avgLambda,
    market_accuracy: marketAccuracy,
    match_results: matchResults,
    model_evaluation: null,
    model_update_recommendation: modelUpdateRec,
  };
}

/**
 * Fetch Mistral AI evaluation for pre-computed audit stats.
 * Lightweight call — backend only runs Mistral, no fixture fetching (~3-5s).
 * Returns the model_evaluation object or null on failure.
 */
export async function fetchMistralEvaluation(
  result: BatchAuditResult
): Promise<BatchAuditResult["model_evaluation"]> {
  // Build market accuracy text
  const marketLines = (result.market_accuracy || []).map(
    (ma) => `- ${ma.market}: ${ma.correct}/${ma.total} (${ma.accuracy_pct.toFixed(1)}%)`
  );

  // Build matches summary text (first 20)
  const matchLines = (result.match_results || []).slice(0, 20).map((mr) => {
    const picks = mr.picks
      .map((p) => `${p.mercado}:${p.resultado}`)
      .join(", ");
    return `- ${mr.home_team} ${mr.score} ${mr.away_team} (${mr.league}) | ${picks}`;
  });

  const body = {
    total_audited: result.audited_matches,
    overall_correct: result.safe_correct + result.neutro_correct,
    overall_total: result.safe_total + result.neutro_total,
    overall_accuracy_pct: result.overall_accuracy,
    safe_correct: result.safe_correct,
    safe_total: result.safe_total,
    safe_accuracy_pct: result.safe_accuracy,
    neutro_correct: result.neutro_correct,
    neutro_total: result.neutro_total,
    neutro_accuracy_pct: result.neutro_accuracy,
    avg_brier_score: result.avg_brier_score,
    avg_lambda_error: result.avg_lambda_error,
    market_accuracy_text: marketLines.join("\n") || "Sem dados de mercado",
    matches_summary_text: matchLines.join("\n") || "Sem detalhes",
  };

  try {
    const res = await fetch("/api/ai/batch-audit/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.model_evaluation ?? null;
  } catch {
    return null;
  }
}
