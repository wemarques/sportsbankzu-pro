/**
 * DEPRECATED — batch audit now runs locally in the browser (localAudit.ts).
 * This route only exists as a safety net for stale cached JS that still
 * calls the old endpoint. It returns immediately with a "please refresh"
 * message instead of calling the backend (which would timeout anyway).
 */
export async function POST() {
  return Response.json(
    {
      status: "success",
      message:
        "Uma versao mais rapida da auditoria esta disponivel! " +
        "Atualize a pagina (Ctrl+F5 ou Ctrl+Shift+R) para resultados instantaneos.",
      audited_matches: 0,
      total_matches: 0,
      finished_matches: 0,
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
    },
    { status: 200 },
  );
}
