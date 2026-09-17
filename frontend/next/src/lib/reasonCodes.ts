/** #254 — reason_code do backend → duas palavras (spec §4.3). Ordem = prioridade. */
const MAPA: ReadonlyArray<readonly [string, string]> = [
  ["LOW_DATA_QUALITY", "amostra curta"],
  ["DATA_MISSING", "amostra curta"],
  ["EARLY_SEASON_FALLBACK", "início de temporada"],
  ["NO_ODDS_AVAILABLE", "sem preço"],
  ["ODDS_TOO_LOW", "odd baixa"],
  ["NEGATIVE_EV", "sem valor"],
  ["EV_FLOOR_DROP", "sem valor"],
  ["DIRECTION_NATURAL_NO_EV", "sem valor"],
  ["INSUFFICIENT_EDGE", "margem curta"],
  ["HIGH_MARKET_CORRELATION", "corredor"],
  ["CORNER_ENGINE_NO_BET", "motor vetou"],
  ["REGIME_BLOCKED", "regime bloqueado"],
  ["SAFE_CIRCUIT_BREAKER", "SAFE pausado"],
  ["HIGH_PREDICTION_RISK", "risco alto"],
  ["SUSPICIOUS_EV", "EV suspeito"],
  ["DIRECTION_AGAINST_PROJFT", "contra a projeção"],
  ["COVERAGE_INSUFFICIENT", "cobertura curta"],
  ["BORDERLINE_LINE_MARGIN", "linha no limite"],
  ["LINEUP_UNCERTAINTY", "escalação incerta"],
  ["VOLATILE_MARKET", "mercado volátil"],
  ["ANCHOR_STALE", "âncora velha"],
  ["NO_VALUE_REFERENCE", "sem referência"],
  ["BASE_RATE_ONLY", "só taxa-base"],
  ["MODEL_ONLY", "só modelo"],
];

/** Codes that are informational (positive/neutral) and never a refusal reason */
export const INFORMATIVOS = new Set([
  "POSITIVE_EV",
  "STRONG_EDGE",
  "HIGH_CALIBRATED_PROB",
  "STABLE_MARKET",
  "ANCHOR_MARKET",
  "DIRECTION_NATURAL_MATCH",
]);

export function motivoRecusa(codes: string[]): string {
  for (const [code, frase] of MAPA) if (codes.includes(code)) return frase;
  return "não vale";
}
