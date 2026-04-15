import type { MatchDetailData } from "@/components/MatchDetailCard";
import type {
  AIAnalysisData,
  ClassificationKey,
  LiveStats,
  LiveTarget,
  LiveDirection,
  MatchContext,
  PickData,
  PickResult,
} from "@/components/MatchAnalysis/types";
import { evaluatePick } from "@/lib/localAudit";

type MatchPrediction = NonNullable<MatchDetailData["predictions"]>[number];

const VALID_CLASSIFICATIONS: ClassificationKey[] = [
  "SAFE",
  "NEUTRO_QUALIFICADO",
  "NEUTRO",
  "NO_BET",
];

function toClassification(value: string | undefined): ClassificationKey {
  if (value && (VALID_CLASSIFICATIONS as string[]).includes(value)) {
    return value as ClassificationKey;
  }
  return "NEUTRO";
}

function normalizeProb(value: number | null | undefined): number {
  if (value == null) return 0;
  if (value > 1) return Math.max(0, Math.min(1, value / 100));
  return Math.max(0, Math.min(1, value));
}

function detectMarketFamily(label: string): "corners" | "cards" | "goals" | "other" {
  const lower = label.toLowerCase();
  if (lower.includes("escante") || lower.includes("corner")) return "corners";
  if (lower.includes("cart") || lower.includes("card")) return "cards";
  if (
    lower.includes("gol") ||
    lower.includes("goal") ||
    lower.startsWith("over ") ||
    lower.startsWith("under ") ||
    /\bo[uv]er\b/.test(lower) ||
    /\bunder\b/.test(lower)
  )
    return "goals";
  return "other";
}

function detectOverUnder(label: string): "over" | "under" | null {
  const lower = label.toLowerCase();
  if (lower.includes("over") || lower.includes("mais de")) return "over";
  if (lower.includes("under") || lower.includes("menos de")) return "under";
  return null;
}

function extractLine(label: string): number | null {
  const match = label.match(/(\d+(?:[.,]\d+)?)/);
  if (!match) return null;
  return parseFloat(match[1].replace(",", "."));
}

function buildLiveTarget(
  family: "corners" | "cards" | "goals" | "other",
  direction: "over" | "under" | null,
  line: number | null,
  liveStats: LiveStats,
  score: { home: number; away: number }
): { target: LiveTarget | null; dir: LiveDirection } {
  if (!direction || line == null) return { target: null, dir: null };
  let current: number | null = null;
  if (family === "corners") current = liveStats.totalCorners;
  else if (family === "cards") current = liveStats.totalCards;
  else if (family === "goals") current = score.home + score.away;
  if (current == null) return { target: null, dir: null };
  return { target: { line, current }, dir: direction };
}

function predictionToPick(p: MatchPrediction, index: number): PickData {
  const classification = toClassification(p.classification ?? p.status);
  const rawProb =
    p.calibrated_probability != null
      ? normalizeProb(p.calibrated_probability)
      : normalizeProb((p.prob_max ?? p.prob_min ?? 0) / 100);
  return {
    id: `${p.mercado}-${index}`,
    label: p.mercado,
    type: p.mercado,
    classification,
    rawProb,
    bookOdd: p.book_odd ?? null,
    ev: p.ev ?? null,
    fairOdd: p.fair_odd ?? null,
    reasonCodes: p.reason_codes ?? [],
    liveTarget: null,
    liveDir: null,
  };
}

function groupCorridors(
  picks: PickData[],
  liveStats: LiveStats,
  score: { home: number; away: number }
): PickData[] {
  const result: PickData[] = [];
  const used = new Set<number>();

  for (let i = 0; i < picks.length; i++) {
    if (used.has(i)) continue;
    const pick = picks[i];
    const family = detectMarketFamily(pick.label);
    const dir = detectOverUnder(pick.label);
    const line = extractLine(pick.label);

    // Cards não formam corredor — exibir como picks individuais (#148b)
    if (family !== "other" && family !== "cards" && dir && line != null) {
      const oppositeDir = dir === "over" ? "under" : "over";
      let partnerIdx = -1;
      for (let j = i + 1; j < picks.length; j++) {
        if (used.has(j)) continue;
        const other = picks[j];
        if (detectMarketFamily(other.label) !== family) continue;
        if (detectOverUnder(other.label) !== oppositeDir) continue;
        const otherLine = extractLine(other.label);
        if (otherLine == null) continue;
        if (dir === "over" && otherLine > line) {
          partnerIdx = j;
          break;
        }
        if (dir === "under" && otherLine < line) {
          partnerIdx = j;
          break;
        }
      }

      if (partnerIdx >= 0) {
        const partner = picks[partnerIdx];
        const partnerLine = extractLine(partner.label)!;
        const min = Math.min(line, partnerLine);
        const max = Math.max(line, partnerLine);
        const bestClass: ClassificationKey =
          pick.classification === "SAFE" || partner.classification === "SAFE"
            ? "SAFE"
            : pick.classification === "NEUTRO_QUALIFICADO" ||
              partner.classification === "NEUTRO_QUALIFICADO"
            ? "NEUTRO_QUALIFICADO"
            : pick.classification === "NEUTRO" || partner.classification === "NEUTRO"
            ? "NEUTRO"
            : "NO_BET";
        const familyLabel = family === "corners" ? "Escanteios" : "Gols";
        const current = family === "corners"
            ? liveStats.totalCorners
            : score.home + score.away;

        result.push({
          id: `corridor-${family}-${i}`,
          label: `${familyLabel}: ${min}-${max} no jogo`,
          type: familyLabel,
          classification: bestClass,
          rawProb: (pick.rawProb + partner.rawProb) / 2,
          bookOdd: null,
          ev: null,
          fairOdd: null,
          reasonCodes: ["CORRIDOR_BET"],
          isCorridorBet: true,
          corridorLegs: [
            {
              selection: pick.label,
              prob: pick.rawProb,
              odd: pick.bookOdd ?? 0,
              ev: pick.ev ?? 0,
            },
            {
              selection: partner.label,
              prob: partner.rawProb,
              odd: partner.bookOdd ?? 0,
              ev: partner.ev ?? 0,
            },
          ],
          liveTarget: { min, max, current },
          liveDir: "corridor",
        });
        used.add(i);
        used.add(partnerIdx);
        continue;
      }
    }

    const { target, dir: liveDir } = buildLiveTarget(family, dir, line, liveStats, score);
    result.push({ ...pick, liveTarget: target, liveDir });
    used.add(i);
  }

  return result;
}

export function mapToMatchAnalysis(detail: MatchDetailData): {
  match: MatchContext;
  picks: PickData[];
  analysis: AIAnalysisData;
} {
  const score = {
    home: detail.score?.home ?? 0,
    away: detail.score?.away ?? 0,
  };

  // Extrair stats ao vivo dos matchStats (campos podem vir do polling de live-scores)
  const ms = detail.matchStats as Record<string, unknown> | undefined;
  const _hCorners = (ms?.["homeCornersCount"] as number) ?? 0;
  const _aCorners = (ms?.["awayCornersCount"] as number) ?? 0;
  const _hYellow = (ms?.["homeYellowCards"] as number) ?? 0;
  const _aYellow = (ms?.["awayYellowCards"] as number) ?? 0;
  const _hRed = (ms?.["homeRedCards"] as number) ?? 0;
  const _aRed = (ms?.["awayRedCards"] as number) ?? 0;

  const liveStats: LiveStats = {
    homeCorners: _hCorners,
    awayCorners: _aCorners,
    totalCorners: detail.currentCorners ?? (_hCorners + _aCorners),
    homeYellow: _hYellow,
    awayYellow: _aYellow,
    homeRed: _hRed,
    awayRed: _aRed,
    totalCards: _hYellow + _aYellow + _hRed + _aRed,
  };

  const match: MatchContext = {
    home: detail.homeTeam,
    away: detail.awayTeam,
    league: detail.league,
    homePos: detail.matchStats?.homeLeaguePosition ?? 0,
    awayPos: detail.matchStats?.awayLeaguePosition ?? 0,
    isLive: detail.status === "live",
    minute: detail.minute ?? 0,
    period: detail.period ?? "",
    score,
    liveStats,
  };

  const rawPicks = (detail.predictions ?? []).map(predictionToPick);
  const picks = groupCorridors(rawPicks, liveStats, score);

  // #148 — preencher result (hit/miss) quando terminado ou preview ao vivo
  const totalGoals = score.home + score.away;
  const btts = score.home > 0 && score.away > 0;
  const result1x2: "1" | "X" | "2" =
    score.home > score.away ? "1" : score.home < score.away ? "2" : "X";
  // Extrair totais reais de corners e cards dos matchStats
  const totalCorners: number | undefined =
    (detail.currentCorners != null && detail.currentCorners > 0)
      ? detail.currentCorners
      : undefined;

  // Cards: somar yellow + red de ambos os times se disponível
  const homeCards = (detail.matchStats as Record<string, unknown> | undefined)?.["homeYellowCards"] as number | undefined;
  const awayCards = (detail.matchStats as Record<string, unknown> | undefined)?.["awayYellowCards"] as number | undefined;
  const homeRed = (detail.matchStats as Record<string, unknown> | undefined)?.["homeRedCards"] as number | undefined;
  const awayRed = (detail.matchStats as Record<string, unknown> | undefined)?.["awayRedCards"] as number | undefined;
  const totalCards: number | undefined =
    (homeCards != null && awayCards != null)
      ? (homeCards + awayCards + (homeRed ?? 0) + (awayRed ?? 0))
      : undefined;

  // Avaliar resultado para jogos finalizados
  if (detail.status === "finished") {
    for (const pick of picks) {
      if (pick.isCorridorBet && pick.corridorLegs) {
        // Corredor: AMBAS as pernas devem acertar
        const allHit = pick.corridorLegs.every((leg) =>
          evaluatePick(leg.selection, totalGoals, btts, result1x2, totalCorners, totalCards)
        );
        pick.result = allHit ? "hit" : "miss";
      } else {
        const hit = evaluatePick(
          pick.label, totalGoals, btts, result1x2, totalCorners, totalCards
        );
        pick.result = hit ? "hit" : "miss";
      }
    }
  } else if (detail.status === "live") {
    // Preview ao vivo: Over que bateu → hit antecipado, Under que estourou → miss antecipado
    for (const pick of picks) {
      if (!pick.liveTarget || !pick.liveDir) continue;
      if (pick.liveDir === "over" && pick.liveTarget.line != null) {
        if (pick.liveTarget.current > pick.liveTarget.line) pick.result = "hit";
      } else if (pick.liveDir === "under" && pick.liveTarget.line != null) {
        if (pick.liveTarget.current >= pick.liveTarget.line) pick.result = "miss";
      } else if (pick.liveDir === "corridor" && pick.liveTarget.max != null) {
        if (pick.liveTarget.current >= pick.liveTarget.max) pick.result = "miss";
      }
    }
  }

  const analysis: AIAnalysisData = {
    summary: detail.aiAnalysis?.summary ?? "",
    keyPoints: detail.aiAnalysis?.key_points ?? [],
    confidence: detail.aiAnalysis?.confidence ?? 0,
    recommendation: detail.aiAnalysis?.recommendation ?? "",
  };

  return { match, picks, analysis };
}
