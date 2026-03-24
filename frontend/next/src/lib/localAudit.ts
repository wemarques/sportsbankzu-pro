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
  BatchAuditCorrection,
  BatchAuditModelEvaluation,
  ModelUpdateRecommendation,
  LeagueAuditStats,
  AuditCombinadas,
  AuditCombinada,
  AuditCombinadaLeg,
} from "./api";

/** Evaluate a single pick against the actual result. */
function evaluatePick(
  mercado: string,
  totalGoals: number,
  btts: boolean,
  result1x2: "1" | "X" | "2",
  totalCorners?: number,
): boolean {
  const m = mercado.trim().toUpperCase();

  // Corner markets — evaluate against totalCorners
  if (m.includes("ESCANTEIO") || m.includes("CORNER")) {
    const tc = totalCorners ?? 0;
    for (const threshold of [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]) {
      const ts = String(threshold);
      if (m.includes("OVER") && m.includes(ts)) return tc > threshold;
      if (m.includes("UNDER") && m.includes(ts)) return tc < threshold;
    }
    return false;
  }

  // Over/Under markets (goals)
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
 * Compute deterministic correction suggestions based on audit metrics.
 * These appear immediately (before Mistral AI responds).
 */
function computeLocalCorrections(
  overallAccuracy: number,
  safeAccuracy: number,
  avgBrier: number,
  avgLambdaError: number,
  marketAccuracy: BatchAuditMarketAccuracy[],
): BatchAuditCorrection[] {
  const corrections: BatchAuditCorrection[] = [];

  // Lambda multiplier correction
  if (avgLambdaError > 1.5) {
    const direction = avgLambdaError > 0 ? "reduzir" : "aumentar";
    const factor = avgLambdaError > 2.0 ? 0.90 : 0.95;
    corrections.push({
      type: "LAMBDA_WEIGHT",
      parameter: "lambda_home_multiplier",
      current_value: 1.0,
      suggested_value: factor,
      reason: `Erro médio de lambda ${avgLambdaError.toFixed(2)} gols — ${direction} multiplicador para compensar`,
      confidence: avgLambdaError > 2.0 ? 75 : 60,
      impact: avgLambdaError > 2.0 ? "HIGH" : "MEDIUM",
    });
  }

  // SAFE threshold correction
  if (safeAccuracy > 0 && safeAccuracy < 60) {
    const bump = safeAccuracy < 50 ? 0.05 : 0.03;
    corrections.push({
      type: "THRESHOLD",
      parameter: "safe_threshold_1x2",
      current_value: 0.60,
      suggested_value: +(0.60 + bump).toFixed(2),
      reason: `Acurácia SAFE em ${safeAccuracy.toFixed(1)}% — elevar threshold mínimo para filtrar picks menos confiáveis`,
      confidence: safeAccuracy < 50 ? 80 : 65,
      impact: safeAccuracy < 50 ? "HIGH" : "MEDIUM",
    });
  }

  // Brier score → probability calibration
  if (avgBrier > 0.25) {
    corrections.push({
      type: "THRESHOLD",
      parameter: "calibration_retrain",
      current_value: avgBrier,
      suggested_value: 0.20,
      reason: `Brier Score ${avgBrier.toFixed(4)} acima do ideal (0.25) — recalibrar Isotonic Regression`,
      confidence: avgBrier > 0.35 ? 85 : 65,
      impact: avgBrier > 0.35 ? "HIGH" : "MEDIUM",
    });
  }

  // Market-specific corrections
  for (const ma of marketAccuracy) {
    if (ma.total >= 4 && ma.accuracy_pct < 35) {
      // BTTS market
      if (ma.market.includes("BTTS") || ma.market.includes("AMBAS")) {
        corrections.push({
          type: "BTTS_MULTIPLIER",
          parameter: "btts_multiplier",
          current_value: 1.0,
          suggested_value: ma.accuracy_pct < 25 ? 0.85 : 0.92,
          reason: `Mercado ${ma.market} com ${ma.accuracy_pct.toFixed(1)}% acurácia (${ma.correct}/${ma.total}) — ajustar multiplicador BTTS`,
          confidence: 70,
          impact: "MEDIUM",
        });
      }
      // Over/Under markets
      else if (ma.market.includes("OVER") || ma.market.includes("UNDER") || ma.market.includes("ACIMA") || ma.market.includes("ABAIXO")) {
        corrections.push({
          type: "THRESHOLD",
          parameter: `threshold_${ma.market.toLowerCase().replace(/\s+/g, "_")}`,
          current_value: 0.55,
          suggested_value: 0.60,
          reason: `Mercado ${ma.market} com ${ma.accuracy_pct.toFixed(1)}% acurácia — elevar threshold para reduzir falsos positivos`,
          confidence: 65,
          impact: "MEDIUM",
        });
      }
    }
  }

  // Overall accuracy correction
  if (overallAccuracy > 0 && overallAccuracy < 45) {
    corrections.push({
      type: "THRESHOLD",
      parameter: "neutro_threshold_global",
      current_value: 0.50,
      suggested_value: 0.55,
      reason: `Acurácia geral ${overallAccuracy.toFixed(1)}% — elevar threshold NEUTRO para filtrar picks de baixa confiança`,
      confidence: 70,
      impact: overallAccuracy < 35 ? "HIGH" : "MEDIUM",
    });
  }

  return corrections;
}

/**
 * Build a local model evaluation object with deterministic corrections.
 * This provides immediate feedback before Mistral AI responds.
 */
function buildLocalModelEvaluation(
  overallAccuracy: number,
  safeAccuracy: number,
  avgBrier: number,
  avgLambdaError: number,
  marketAccuracy: BatchAuditMarketAccuracy[],
  modelUpdateRec: ModelUpdateRecommendation,
  auditedMatches: number,
): BatchAuditModelEvaluation | null {
  if (auditedMatches < 2) return null;

  const corrections = computeLocalCorrections(
    overallAccuracy,
    safeAccuracy,
    avgBrier,
    avgLambdaError,
    marketAccuracy,
  );

  // Determine overall assessment
  let assessment: BatchAuditModelEvaluation["overall_assessment"] = "SATISFATORIO";
  if (modelUpdateRec.urgency === "CRITICA" || modelUpdateRec.urgency === "ALTA") {
    assessment = "CRITICO";
  } else if (modelUpdateRec.urgency === "MEDIA" || corrections.length > 2) {
    assessment = "NECESSITA_AJUSTE";
  }

  // Lambda evaluation
  let lambdaStatus: string = "OK";
  let lambdaDirection: string = "BALANCED";
  if (avgLambdaError > 2.0) { lambdaStatus = "CRITICAL"; lambdaDirection = "OVER_ESTIMATING"; }
  else if (avgLambdaError > 1.5) { lambdaStatus = "WARNING"; lambdaDirection = "OVER_ESTIMATING"; }

  // Threshold evaluation
  let safeStatus: string = "OK";
  if (safeAccuracy > 0 && safeAccuracy < 50) safeStatus = "CRITICAL";
  else if (safeAccuracy > 0 && safeAccuracy < 60) safeStatus = "WARNING";

  let neutroStatus: string = "OK";
  const neutroAcc = overallAccuracy; // overall includes neutro
  if (neutroAcc > 0 && neutroAcc < 40) neutroStatus = "CRITICAL";
  else if (neutroAcc > 0 && neutroAcc < 50) neutroStatus = "WARNING";

  // Market biases
  const biases = marketAccuracy
    .filter((ma) => ma.total >= 4 && ma.accuracy_pct < 40)
    .map((ma) => ({
      market: ma.market,
      bias_type: ma.accuracy_pct < 25 ? "SYSTEMATIC_ERROR" : "OVER_CONFIDENT",
      description: `${ma.accuracy_pct.toFixed(1)}% acurácia em ${ma.total} picks`,
      severity: (ma.accuracy_pct < 25 ? "HIGH" : ma.accuracy_pct < 35 ? "MEDIUM" : "LOW") as "HIGH" | "MEDIUM" | "LOW",
    }));

  return {
    overall_assessment: assessment,
    overall_notes: `Avaliação local (determinística): ${corrections.length} correções sugeridas. Aguardando avaliação Mistral AI para análise mais detalhada.`,
    lambda_evaluation: {
      status: lambdaStatus,
      direction: lambdaDirection,
      avg_error: avgLambdaError,
      notes: avgLambdaError > 1.5
        ? `Erro médio de ${avgLambdaError.toFixed(2)} gols — lambdas precisam de ajuste`
        : `Erro médio de ${avgLambdaError.toFixed(2)} gols — dentro do aceitável`,
    },
    threshold_evaluation: {
      safe_status: safeStatus,
      neutro_status: neutroStatus,
      notes: safeStatus !== "OK" || neutroStatus !== "OK"
        ? "Thresholds precisam de revisão com base nos resultados da rodada"
        : "Thresholds dentro dos parâmetros esperados",
    },
    market_biases: biases,
    recommended_corrections: corrections,
    model_update_recommendation: modelUpdateRec,
    audit_confidence: Math.min(90, Math.max(30, auditedMatches * 8)),
  };
}

// ── Combinadas (duplas) computation ──────────────────────────────────────

const _INTRA_INCOMPATIBLE = [
  ["Over 2.5 gols", "Under 2.5 gols"],
  ["Over 3.5 gols", "Under 3.5 gols"],
  ["Over 1.5 gols", "Under 1.5 gols"],
  ["Over 4.5 gols", "Under 4.5 gols"],
  ["BTTS — SIM", "BTTS — NÃO"],
  ["DC 1X", "DC X2"],
].map(([a, b]) => `${a}||${b}`);

function _isIncompatible(a: string, b: string): boolean {
  const key1 = `${a}||${b}`;
  const key2 = `${b}||${a}`;
  return _INTRA_INCOMPATIBLE.includes(key1) || _INTRA_INCOMPATIBLE.includes(key2);
}

type Prediction = NonNullable<Match["predictions"]>[number];

function _validMercado(p: Prediction): boolean {
  const s = (p.status || "").toUpperCase();
  if (s !== "SAFE" && s !== "NEUTRO") return false;
  return (p.odd_minima ?? 0) >= 1.01;
}

function _buildLeg(match: Match, p: Prediction): AuditCombinadaLeg {
  return {
    jogo: `${match.homeTeam.name} x ${match.awayTeam.name}`,
    homeTeam: match.homeTeam.name,
    awayTeam: match.awayTeam.name,
    leagueId: match.leagueId,
    leagueName: match.leagueName,
    datetime: match.datetime,
    mercado: p.mercado,
    status: p.status,
    prob_min: p.prob_min,
    prob_max: p.prob_max,
    odd_minima: p.odd_minima ?? 1.0,
  };
}

function _statusCombinada(legs: AuditCombinadaLeg[]): "SAFE" | "MISTA" | "NEUTRO" {
  const statuses = legs.map((l) => l.status.toUpperCase());
  if (statuses.every((s) => s === "SAFE" || s === "SAFE*")) return "SAFE";
  if (statuses.some((s) => s === "SAFE" || s === "SAFE*") && statuses.every((s) => s === "SAFE" || s === "SAFE*" || s === "NEUTRO")) return "MISTA";
  return "NEUTRO";
}

function _probCombinada(legs: AuditCombinadaLeg[]): [number, number] {
  let pMin = 1, pMax = 1;
  for (const l of legs) { pMin *= l.prob_min / 100; pMax *= l.prob_max / 100; }
  return [Math.round(pMin * 1000) / 10, Math.round(pMax * 1000) / 10];
}

function _oddCombinada(legs: AuditCombinadaLeg[]): number {
  let r = 1;
  for (const l of legs) r *= l.odd_minima;
  return Math.round(r * 100) / 100;
}

/** Actual result for a match, used for dupla evaluation. */
interface MatchActualResult {
  totalGoals: number;
  btts: boolean;
  result1x2: "1" | "X" | "2";
  totalCorners: number;
}

/**
 * Compute intra-game and inter-game combinadas from matches with predictions,
 * and evaluate finished duplas against actual results.
 */
function computeLocalCombinadas(matches: Match[]): AuditCombinadas {
  // Use ALL matches with predictions (scheduled, live, and finished)
  const withPredictions = matches.filter(
    (m) => m.predictions && m.predictions.length > 0
  );

  // Build actual result lookup for finished matches (for dupla evaluation)
  const actualByKey = new Map<string, MatchActualResult>();
  for (const m of matches) {
    if (m.status !== "finished" || !m.score) continue;
    const hg = m.score.home;
    const ag = m.score.away;
    const tg = hg + ag;
    const hc = m.stats.homeCornersCount ?? 0;
    const ac = m.stats.awayCornersCount ?? 0;
    const actual: MatchActualResult = {
      totalGoals: tg,
      btts: hg > 0 && ag > 0,
      result1x2: hg > ag ? "1" : hg === ag ? "X" : "2",
      totalCorners: hc + ac,
    };
    // Index by homeTeam|awayTeam (lowercase) for leg matching
    const key = `${m.homeTeam.name.trim().toLowerCase()}|${m.awayTeam.name.trim().toLowerCase()}`;
    actualByKey.set(key, actual);
  }

  function _findActualForLeg(leg: AuditCombinadaLeg): MatchActualResult | null {
    const key = `${leg.homeTeam.trim().toLowerCase()}|${leg.awayTeam.trim().toLowerCase()}`;
    return actualByKey.get(key) ?? null;
  }

  function _evaluateDupla(dupla: AuditCombinada): "ACERTOU" | "ERROU" | "PENDENTE" {
    const a1 = _findActualForLeg(dupla.leg1);
    const a2 = dupla.tipo === "intra" ? a1 : _findActualForLeg(dupla.leg2);
    if (!a1 || !a2) return "PENDENTE";
    const hit1 = evaluatePick(dupla.leg1.mercado, a1.totalGoals, a1.btts, a1.result1x2, a1.totalCorners);
    const hit2 = evaluatePick(dupla.leg2.mercado, a2.totalGoals, a2.btts, a2.result1x2, a2.totalCorners);
    return hit1 && hit2 ? "ACERTOU" : "ERROU";
  }

  const intra: AuditCombinada[] = [];
  const inter: AuditCombinada[] = [];

  // Intra-game: two markets from the same match
  for (const match of withPredictions) {
    const eligible = (match.predictions ?? []).filter(_validMercado);
    if (eligible.length < 2) continue;
    for (let i = 0; i < eligible.length; i++) {
      for (let j = i + 1; j < eligible.length; j++) {
        if (_isIncompatible(eligible[i].mercado, eligible[j].mercado)) continue;
        const legs = [_buildLeg(match, eligible[i]), _buildLeg(match, eligible[j])];
        const odd = _oddCombinada(legs);
        if (odd < 1.5) continue;
        const [pMin, pMax] = _probCombinada(legs);
        const d: AuditCombinada = { tipo: "intra", leg1: legs[0], leg2: legs[1], odd_combinada: odd, prob_combinada_min: pMin, prob_combinada_max: pMax, status_combinada: _statusCombinada(legs) };
        d.resultado = _evaluateDupla(d);
        intra.push(d);
      }
    }
  }

  // Inter-game: one market from each of two different matches
  const matchMercados: Array<{ match: Match; eligible: Prediction[] }> = [];
  for (const match of withPredictions) {
    const eligible = (match.predictions ?? []).filter(_validMercado);
    if (eligible.length > 0) matchMercados.push({ match, eligible });
  }

  for (let i = 0; i < matchMercados.length; i++) {
    for (let j = i + 1; j < matchMercados.length; j++) {
      for (const m1 of matchMercados[i].eligible) {
        for (const m2 of matchMercados[j].eligible) {
          const legs = [_buildLeg(matchMercados[i].match, m1), _buildLeg(matchMercados[j].match, m2)];
          const odd = _oddCombinada(legs);
          if (odd < 1.8) continue;
          const [pMin, pMax] = _probCombinada(legs);
          const d: AuditCombinada = { tipo: "inter", leg1: legs[0], leg2: legs[1], odd_combinada: odd, prob_combinada_min: pMin, prob_combinada_max: pMax, status_combinada: _statusCombinada(legs) };
          d.resultado = _evaluateDupla(d);
          inter.push(d);
        }
      }
    }
  }

  // Sort: SAFE first, then by probability
  const prio = (s: string) => s === "SAFE" ? 2 : s === "MISTA" ? 1 : 0;
  intra.sort((a, b) => prio(b.status_combinada) - prio(a.status_combinada) || b.odd_combinada - a.odd_combinada);
  inter.sort((a, b) => prio(b.status_combinada) - prio(a.status_combinada) || b.prob_combinada_min - a.prob_combinada_min);

  // Compute dupla accuracy stats (only for evaluated duplas, not PENDENTE)
  const intraEvaluated = intra.filter((d) => d.resultado !== "PENDENTE");
  const interEvaluated = inter.filter((d) => d.resultado !== "PENDENTE");
  const intraCorrect = intraEvaluated.filter((d) => d.resultado === "ACERTOU").length;
  const interCorrect = interEvaluated.filter((d) => d.resultado === "ACERTOU").length;
  const totalEvaluated = intraEvaluated.length + interEvaluated.length;
  const totalCorrect = intraCorrect + interCorrect;

  return {
    intra: intra.slice(0, 10),
    inter: inter.slice(0, 10),
    total_intra: intra.length,
    total_inter: inter.length,
    total_jogos: withPredictions.length,
    dupla_intra_correct: intraCorrect,
    dupla_intra_total: intraEvaluated.length,
    dupla_intra_accuracy: intraEvaluated.length > 0 ? Math.round((intraCorrect / intraEvaluated.length) * 1000) / 10 : 0,
    dupla_inter_correct: interCorrect,
    dupla_inter_total: interEvaluated.length,
    dupla_inter_accuracy: interEvaluated.length > 0 ? Math.round((interCorrect / interEvaluated.length) * 1000) / 10 : 0,
    dupla_overall_accuracy: totalEvaluated > 0 ? Math.round((totalCorrect / totalEvaluated) * 1000) / 10 : 0,
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

  // Market reference signal capping counters
  let cappedByMarketReferenceCount = 0;
  let safeToNeutroBySignalCount = 0;
  let safeBlockedByRestritoCount = 0;

  for (const match of finished) {
    const homeGoals = match.score!.home;
    const awayGoals = match.score!.away;
    const totalGoals = homeGoals + awayGoals;
    const btts = homeGoals > 0 && awayGoals > 0;
    const result1x2: "1" | "X" | "2" =
      homeGoals > awayGoals ? "1" : homeGoals === awayGoals ? "X" : "2";
    const totalCorners = (match.stats.homeCornersCount ?? 0) + (match.stats.awayCornersCount ?? 0);

    const picks = match.predictions || [];
    let matchCorrect = 0;
    let matchTotal = 0;
    const picksEval: BatchAuditMatchResult["picks"] = [];

    for (const pick of picks) {
      const isCorrect = evaluatePick(pick.mercado, totalGoals, btts, result1x2, totalCorners);

      // Use finalClassification (post-capping) for accuracy, fallback to status
      const effectiveStatus = (pick as any).finalClassification || pick.status;
      const wasCapped = (pick as any).wasCappedByMarketSignal === true;
      const mktRefSignal = (pick as any).marketReferenceSignal as string | undefined;

      picksEval.push({
        mercado: pick.mercado,
        status_pick: effectiveStatus,
        resultado: isCorrect ? "ACERTOU" : "ERROU",
        marketReferenceSignal: mktRefSignal as any,
        wasCappedByMarketSignal: wasCapped,
      });

      // Track capping stats
      if (wasCapped) {
        cappedByMarketReferenceCount++;
        if (mktRefSignal === "RESTRITO") {
          safeBlockedByRestritoCount++;
        } else {
          safeToNeutroBySignalCount++;
        }
      }

      matchTotal++;
      if (isCorrect) matchCorrect++;

      if (effectiveStatus === "SAFE" || effectiveStatus === "SAFE*") {
        safeTotal++;
        if (isCorrect) safeCorrect++;
      } else if (effectiveStatus === "NEUTRO" || effectiveStatus === "NEUTRO_QUALIFICADO") {
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
    let matchBrier: number | undefined;
    const over25Prob = match.stats.over25Prob;
    if (over25Prob != null) {
      const actualOver25 = totalGoals > 2.5 ? 1 : 0;
      matchBrier = (over25Prob / 100 - actualOver25) ** 2;
      brierScores.push(matchBrier);
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
      brier_score: matchBrier,
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

  const localEvaluation = buildLocalModelEvaluation(
    overallAcc,
    safeAcc,
    avgBrier,
    avgLambda,
    marketAccuracy,
    modelUpdateRec,
    matchResults.length,
  );

  // League-level aggregation (includes per-league Brier — #077)
  const leagueMap = new Map<string, { correct: number; total: number; matches: number; brierScores: number[] }>();
  for (const mr of matchResults) {
    const ls = leagueMap.get(mr.league) || { correct: 0, total: 0, matches: 0, brierScores: [] };
    ls.matches++;
    ls.correct += mr.picks_correct;
    ls.total += mr.picks_total;
    if (mr.brier_score != null) ls.brierScores.push(mr.brier_score);
    leagueMap.set(mr.league, ls);
  }
  const leagueAccuracy: LeagueAuditStats[] = Array.from(leagueMap.entries())
    .sort(([, a], [, b]) => {
      const pctA = a.total > 0 ? a.correct / a.total : 0;
      const pctB = b.total > 0 ? b.correct / b.total : 0;
      return pctB - pctA;
    })
    .map(([league, d]) => ({
      league,
      matches_audited: d.matches,
      picks_correct: d.correct,
      picks_total: d.total,
      accuracy_pct: d.total > 0 ? Math.round((d.correct / d.total) * 1000) / 10 : 0,
      brier_score: d.brierScores.length > 0
        ? d.brierScores.reduce((a, b) => a + b, 0) / d.brierScores.length
        : undefined,
    }));

  // Compute combinadas from scheduled/live matches with predictions
  const combinadas = computeLocalCombinadas(allMatches);

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
    league_accuracy: leagueAccuracy,
    match_results: matchResults,
    model_evaluation: localEvaluation,
    model_update_recommendation: modelUpdateRec,
    combinadas,
    market_reference_stats: {
      capped_by_market_reference_count: cappedByMarketReferenceCount,
      safe_to_neutro_by_signal_count: safeToNeutroBySignalCount,
      safe_blocked_by_restrito_count: safeBlockedByRestritoCount,
    },
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
    // Market reference signal context for Mistral
    market_reference_stats: result.market_reference_stats || null,
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
