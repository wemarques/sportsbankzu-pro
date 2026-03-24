import { useState, useEffect } from "react";

export type LeagueClassificationType = "ML_ACTIVE" | "POISSON" | "DEACTIVATED";

export interface LeagueClassification {
  league_id: string;
  classification: LeagueClassificationType;
  status?: string;
  brier: number | null;
  ece?: number | null;
  accuracy: number | null;
  odds_value_added?: number | null;
  market_efficiency_r2?: number | null;
  n_samples: number;
  chronological_sorted?: boolean;
}

// Mapping from retrain pipeline league IDs (FootyStats slugs) to frontend league IDs
const RETRAIN_TO_FRONTEND_ID: Record<string, string> = {
  "primeira-liga": "portugal-liga-nos",
  "super-lig": "turkey-super-lig",
  "la-liga": "spain-la-liga",
  "premiership": "scotland-premiership",
  "eredivisie": "netherlands-eredivisie",
  "ligue-1": "france-ligue-1",
  "liga-mx": "mexico-liga-mx",
  "serie-a": "italy-serie-a",
  "brasileirao-serie-a": "brazil-serie-a",
  "bundesliga": "germany-bundesliga",
  "colombian-primera-a": "colombia-primera-a",
  "mls": "usa-mls",
  "superliga": "denmark-superliga",
  "2-bundesliga": "germany-2-bundesliga",
  "brasileirao-serie-b": "brazil-serie-b",
  "serie-b": "italy-serie-b",
};

export function useLeagueClassifications() {
  const [classifications, setClassifications] = useState<
    Record<string, LeagueClassification>
  >({});

  useEffect(() => {
    fetch("/data/league_classifications.json")
      .then((res) => res.json())
      .then((data: LeagueClassification[]) => {
        const map: Record<string, LeagueClassification> = {};
        data.forEach((lc) => {
          const frontendId = RETRAIN_TO_FRONTEND_ID[lc.league_id] || lc.league_id;
          map[frontendId] = { ...lc, league_id: frontendId };
        });
        setClassifications(map);
      })
      .catch((err) =>
        console.error("Failed to load league classifications:", err)
      );
  }, []);

  return classifications;
}
