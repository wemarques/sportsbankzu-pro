import { useState, useEffect, useMemo, useCallback } from "react";
import { toBackendLeagueId } from "@/lib/leagues";

/**
 * #250 — o selo de confianca passa a descrever a PRODUCAO, nao um backtest.
 *
 * Antes: o hook lia so `public/data/league_classifications.json` (retrato de um
 * backtest offline de marco/2026) e nunca perguntava nada ao backend. O painel
 * afirmava "Modelo AI treinado com 802 jogos" para a Liga NOS enquanto
 * `/ml/status?league=primeira-liga` respondia `{"available": false}` — e
 * `/ml/status/all` devolvia 0 de 22 ligas com modelo. O arquivo estatico
 * tambem usava UM criterio (brier < 0.60) contra os TRES gates de
 * `backend/ml/predictor.py::is_ml_available` (brier < 0.60, odds_value_added
 * >= -0.015, ece <= 0.10), e por isso mostrava `professional-league` como AI
 * apesar de ece = 0.1016 > 0.10.
 *
 * Agora: quem responde "existe modelo servindo esta liga?" e o proprio backend
 * (`/api/ml/status` -> `/ml/status/all`), que ja roda `is_ml_available` inteiro.
 * O JSON estatico sobra APENAS como fonte de metricas historicas (accuracy),
 * e so quando comprovadamente descreve o MESMO modelo que o backend reporta.
 */

/** Nivel do selo. Reflete o caminho que o pipeline de fato usa para a liga. */
export type LeagueConfidenceLevel =
  /** Backend confirma modelo ativo (os 3 gates de is_ml_available passaram). */
  | "ML_ACTIVE"
  /** Nao ha modelo: 1X2 = espelho de mercado de-vigado, gols = Poisson. */
  | "POISSON"
  /** Existe modelo treinado, porem suprimido por um gate de calibragem. */
  | "ML_SUPPRESSED"
  /** Backend nao respondeu — nao afirmamos nivel nenhum. */
  | "UNVERIFIED";

export interface LeagueConfidence {
  /** Slug canonico do backend (ex.: "primeira-liga"). */
  leagueId: string;
  level: LeagueConfidenceLevel;
  /** Brier de validacao reportado pelo BACKEND (nunca o do arquivo estatico). */
  brier: number | null;
  /** Accuracy historica — so preenchida quando a proveniencia confere. */
  accuracy: number | null;
  nSamples: number | null;
  /** ISO de treino, vindo do backend. Nunca literal. */
  trainedAt: string | null;
}

export interface LeagueConfidenceState {
  status: "loading" | "ready" | "unverified";
  get: (leagueId: string) => LeagueConfidence | null;
}

interface MlLeagueStatus {
  available: boolean;
  trained_at: string | null;
  validation_brier: number | null;
  n_samples: number | null;
}

interface HistoricalMetrics {
  league_id: string;
  brier: number | null;
  accuracy: number | null;
  n_samples: number | null;
}

/**
 * #250 — a accuracy historica so pode ser exibida se provar que descreve o
 * MESMO modelo que o backend esta servindo. O criterio e a coincidencia de
 * brier e n_samples; se o modelo foi retreinado, os dois mudam e a accuracy
 * antiga e descartada em vez de virar numero velho com cara de atual.
 */
function describesSameModel(hist: HistoricalMetrics, live: MlLeagueStatus): boolean {
  if (hist.brier == null || live.validation_brier == null) return false;
  if (hist.n_samples == null || live.n_samples == null) return false;
  if (hist.n_samples !== live.n_samples) return false;
  return Math.abs(hist.brier - live.validation_brier) < 5e-4;
}

export function useLeagueClassifications(): LeagueConfidenceState {
  const [live, setLive] = useState<Record<string, MlLeagueStatus> | null>(null);
  const [historical, setHistorical] = useState<Record<string, HistoricalMetrics>>({});
  const [status, setStatus] = useState<"loading" | "ready" | "unverified">("loading");

  useEffect(() => {
    let cancelled = false;

    // Metricas historicas: insumo secundario, nunca decide o nivel do selo.
    fetch("/data/league_classifications.json")
      .then((res) => (res.ok ? res.json() : []))
      .then((rows: HistoricalMetrics[]) => {
        if (cancelled || !Array.isArray(rows)) return;
        const map: Record<string, HistoricalMetrics> = {};
        for (const row of rows) {
          if (row?.league_id) map[row.league_id] = row;
        }
        setHistorical(map);
      })
      .catch(() => {
        /* metrica historica ausente apenas omite accuracy; nao muda o nivel. */
      });

    // Fonte da verdade do NIVEL.
    fetch("/api/ml/status", { cache: "no-store" })
      .then((res) => res.json())
      .then((body: { ok?: boolean; leagues?: Record<string, MlLeagueStatus> | null }) => {
        if (cancelled) return;
        if (body?.ok && body.leagues) {
          setLive(body.leagues);
          setStatus("ready");
        } else {
          setLive(null);
          setStatus("unverified");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("[selo] verificacao de modelos indisponivel:", err);
        setLive(null);
        setStatus("unverified");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const byBackendId = useMemo(() => {
    if (!live) return null;
    const map: Record<string, LeagueConfidence> = {};
    for (const [leagueId, st] of Object.entries(live)) {
      const hist = historical[leagueId];
      const sameModel = st.available && hist ? describesSameModel(hist, st) : false;
      map[leagueId] = {
        leagueId,
        level: st.available
          ? "ML_ACTIVE"
          : st.trained_at
            ? "ML_SUPPRESSED"
            : "POISSON",
        brier: st.validation_brier,
        accuracy: sameModel ? (hist?.accuracy ?? null) : null,
        nSamples: st.n_samples,
        trainedAt: st.trained_at,
      };
    }
    return map;
  }, [live, historical]);

  const get = useCallback(
    (leagueId: string): LeagueConfidence | null => {
      if (!leagueId) return null;
      const slug = toBackendLeagueId(leagueId);
      if (status === "loading") return null;
      if (!byBackendId) {
        // Requisito 2: degradar sem afirmar. O selo aparece em estado
        // explicitamente nao verificado, nao volta a repetir o backtest.
        return {
          leagueId: slug,
          level: "UNVERIFIED",
          brier: null,
          accuracy: null,
          nSamples: null,
          trainedAt: null,
        };
      }
      return byBackendId[slug] ?? null;
    },
    [byBackendId, status],
  );

  return useMemo(() => ({ status, get }), [status, get]);
}
