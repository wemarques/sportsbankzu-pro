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
  "professional-league": "saudi-professional-league",
  "primeira-liga": "portugal-liga-nos",
  "super-lig": "turkey-super-lig",
  "super-league-greece": "greece-super-league",
  "la-liga": "spain-la-liga",
  "premiership": "scotland-premiership",
  "eredivisie": "netherlands-eredivisie",
  "ligue-1": "france-ligue-1",
  "liga-mx": "mexico-liga-mx",
  "serie-a": "italy-serie-a",
  "brasileirao-serie-a": "brazil-serie-a",
  "eliteserien": "norway-eliteserien",
  "bundesliga": "germany-bundesliga",
  "colombian-primera-a": "colombia-primera-a",
  "mls": "usa-mls",
  "eerste-divisie": "netherlands-eerste-divisie",
  "super-league": "switzerland-super-league",
  "superliga": "denmark-superliga",
  "allsvenskan": "sweden-allsvenskan",
  "2-bundesliga": "germany-2-bundesliga",
  "ligue-2": "france-ligue-2",
  "brasileirao-serie-b": "brazil-serie-b",
  "serie-b": "italy-serie-b",
  "austrian-bundesliga": "austria-bundesliga",
  "j-league": "japan-j-league",
  "k-league": "south-korea-k-league",
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
