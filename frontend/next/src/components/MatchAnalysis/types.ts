export type ClassificationKey =
  | "SAFE"
  | "NEUTRO_QUALIFICADO"
  | "NEUTRO"
  | "NO_BET";

export interface CorridorLeg {
  selection: string;
  prob: number;
  odd: number;
  ev: number;
}

export interface LiveTarget {
  line?: number;
  min?: number;
  max?: number;
  current: number;
}

export type LiveDirection = "over" | "under" | "corridor" | null;

export type PickResult = "hit" | "miss" | null;

export interface PickData {
  id: string;
  label: string;
  type: string;
  classification: ClassificationKey;
  rawProb: number;
  bookOdd: number | null;
  ev: number | null;
  fairOdd: number | null;
  reasonCodes: string[];
  isCorridorBet?: boolean;
  corridorLegs?: CorridorLeg[];
  liveTarget?: LiveTarget | null;
  liveDir?: LiveDirection;
  result?: PickResult;
}

export interface LiveStats {
  homeCorners: number;
  awayCorners: number;
  totalCorners: number;
  homeYellow: number;
  awayYellow: number;
  homeRed: number;
  awayRed: number;
  totalCards: number;
}

export interface MatchContext {
  home: string;
  away: string;
  league: string;
  homePos: number;
  awayPos: number;
  isLive: boolean;
  minute: number;
  period: string;
  score: { home: number; away: number };
  liveStats: LiveStats;
}

export interface AIAnalysisData {
  summary: string;
  keyPoints: string[];
  confidence: number;
  recommendation: string;
}
