"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useLivePolling } from "@/hooks/useLivePolling";
import MatchDetailCard, {
  type MatchDetailData,
  type AIAnalysis,
  type AuditResult,
  type AuditCorrection,
} from "@/components/MatchDetailCard";
import { MatchAnalysis } from "@/components/MatchAnalysis";
import { mapToMatchAnalysis } from "@/lib/matchDataMapper";
import { AVAILABLE_LEAGUES, type Match, type MatchPrediction } from "@/lib/leagues";
import { mapMatchStats } from "@/lib/matchStats";
import { getMatchesByLeague, getAiMatchAnalysis, postMatchAudit, applyAuditCorrection, applyBatchCorrections } from "@/lib/api";
import type { BatchAuditResult, BatchAuditCorrection, MatchesResponse } from "@/lib/api";
import { runLocalAudit, fetchMistralEvaluation } from "@/lib/localAudit";
import BatchAuditPanel from "@/components/BatchAuditPanel";
import LeagueConfidenceBadge, { ConfidenceLegend } from "@/components/LeagueConfidenceBadge";
import BankrollCard, { calcQuarterKelly } from "@/components/BankrollCard";
import ReliabilityCard from "@/components/ReliabilityCard";
import { useLeagueClassifications } from "@/hooks/useLeagueClassifications";
import AuditBanner from "@/components/AuditBanner";
import EmptyState, { MockDataBanner } from "@/components/EmptyState";
import type { EmptyStateVariant } from "@/components/EmptyState";
import Glossary from "@/components/Glossary";
import DestaquesDoDia from "@/components/DestaquesDoDia";
import { getClassificationDisplay } from "@/lib/classifications";
import { useRole } from "@/hooks/useRole";
import {
  Star,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  Loader2,
  Flame,
  Radio,
  Bot,
  SlidersHorizontal,
  Heart,
  Filter,
  Bell,
  Trophy,
  Wrench,
  Sparkles,
  ArrowLeft,
  TrendingUp,
  BarChart3,
  Calculator,
  Brain,
  Target,
  Zap,
  Share2,
  Copy,
  MessageCircle,
  ShieldCheck,
  Link2,
  Layers,
  RefreshCw,
} from "lucide-react";
const VERSION_FALLBACK = "pro V4.0";

/* ── Tipos de Combinadas (duplas) ── */
interface CombinadaLeg {
  jogo: string; homeTeam: string; awayTeam: string;
  leagueId: string; leagueName: string; datetime: string;
  mercado: string; status: string; prob_min: number; prob_max: number; odd_minima: number;
}
interface Combinada {
  tipo: "intra" | "inter"; leg1: CombinadaLeg; leg2: CombinadaLeg;
  odd_combinada: number; prob_combinada_min: number; prob_combinada_max: number;
  status_combinada: "SAFE" | "MISTA" | "NEUTRO";
}
interface CombinadasData {
  intra: Combinada[]; inter: Combinada[];
  total_intra: number; total_inter: number; total_jogos: number;
}

function statusCombinadaStyle(s: string) {
  if (s === "SAFE") return { bg: "rgba(0,223,130,0.08)", border: "rgba(0,223,130,0.25)", badge: { bg: "rgba(0,223,130,0.15)", color: "#00df82" } };
  if (s === "MISTA") return { bg: "rgba(157,80,255,0.08)", border: "rgba(157,80,255,0.25)", badge: { bg: "rgba(157,80,255,0.15)", color: "#c4a0ff" } };
  return { bg: "rgba(255,136,0,0.06)", border: "rgba(255,136,0,0.2)", badge: { bg: "rgba(255,136,0,0.12)", color: "#ffaa44" } };
}

function CombinadaCardDash({ c }: { c: Combinada }) {
  const st = statusCombinadaStyle(c.status_combinada);
  const isIntra = c.tipo === "intra";
  const timeStr = (dt: string) => {
    try { const d = new Date(dt); return isNaN(d.getTime()) ? "--:--" : d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }); }
    catch { return "--:--"; }
  };
  return (
    <div style={{ borderRadius: 12, border: `1px solid ${st.border}`, background: st.bg, padding: "12px 14px", marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {isIntra ? <Layers size={12} style={{ color: "#c4a0ff" }} /> : <Link2 size={12} style={{ color: "#00df82" }} />}
          <span style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "#888" }}>
            {isIntra ? "Intra-jogo" : "Inter-jogo"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: "0.65rem", color: "#666" }}>{c.prob_combinada_min}–{c.prob_combinada_max}%</span>
          <span style={{ fontSize: "0.65rem", fontWeight: 700, borderRadius: 4, padding: "2px 6px", background: st.badge.bg, color: st.badge.color }}>{c.status_combinada === "SAFE" ? "ALTA CONFIANCA" : c.status_combinada === "MISTA" ? "MISTA" : "VIÁVEL"}</span>
        </div>
      </div>
      {([c.leg1, c.leg2] as CombinadaLeg[]).map((leg, i) => (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6 }}>
          <span style={{ width: 16, height: 16, borderRadius: "50%", background: "#1a1a1a", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.6rem", color: "#888", flexShrink: 0, marginTop: 2 }}>{i + 1}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "0.72rem", fontWeight: 600, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {leg.homeTeam} <span style={{ color: "#666" }}>x</span> {leg.awayTeam} <span style={{ color: "#555", fontWeight: 400 }}>{timeStr(leg.datetime)}</span>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 2, flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.7rem", color: "#00df82", fontWeight: 500 }}>{leg.mercado}</span>
              <span style={{ fontSize: "0.65rem", borderRadius: 4, padding: "1px 5px", fontWeight: 700, background: leg.status.toUpperCase().startsWith("SAFE") ? "rgba(0,223,130,0.12)" : "rgba(255,136,0,0.12)", color: leg.status.toUpperCase().startsWith("SAFE") ? "#00df82" : "#ffaa44" }}>
                {leg.status} {leg.prob_min}–{leg.prob_max}%
              </span>
              <span style={{ fontSize: "0.65rem", color: "#555" }}>@{leg.odd_minima.toFixed(2)}</span>
            </div>
          </div>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.05)", marginTop: 4 }}>
        <span style={{ fontSize: "0.65rem", color: "#555", textTransform: "uppercase", letterSpacing: "0.05em" }}>Odd Combinada</span>
        <span style={{ fontSize: "1.1rem", fontWeight: 900, color: "#fff" }}>{c.odd_combinada.toFixed(2)}</span>
      </div>
    </div>
  );
}
const SHARE_TEXT = "Confira os jogos e picks gerados no SportsBankZU Pro.";

type NavView = "matches" | "campeonatos" | "ferramentas" | "recomendadas" | "duplas" | "glossario";
type ShareFeedbackTone = "success" | "error" | "info";

type OddsTab = "1x2" | "double-chance" | "btts" | "goals" | "cards" | "corners";
type DateMode = "today" | "tomorrow" | "week";

type LeagueGroup = {
  leagueId: string;
  leagueName: string;
  countryFlag: string;
  country: string;
  matches: Match[];
  collapsed: boolean;
};

/* ── helpers ── */

function safeOdd(value?: number, fallback = 0) {
  if (!value || value <= 0) return fallback;
  return value;
}

/** Alias map: common nicknames/abbreviations → canonical name (lowercase). */
const TEAM_ALIASES: Record<string, string> = {
  wolves: "wolverhampton wanderers",
  "man united": "manchester united", "man utd": "manchester united",
  "man city": "manchester city",
  spurs: "tottenham hotspur",
  brighton: "brighton and hove albion",
  "west ham": "west ham united",
  newcastle: "newcastle united",
  leicester: "leicester city",
  "nottm forest": "nottingham forest", "nott'm forest": "nottingham forest",
  "sheffield utd": "sheffield united",
  luton: "luton town",
  inter: "inter milan", internazionale: "inter milan",
  psg: "paris saint germain", "paris sg": "paris saint germain",
  bayern: "bayern munich", "bayern munchen": "bayern munich",
  dortmund: "borussia dortmund",
  leverkusen: "bayer leverkusen",
};

/** Normalize team name for matching: remove accents, periods, extra spaces, common prefixes. */
function normalizeTeamName(name: string): string {
  let s = name
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")  // Remove diacritics (é→e, ñ→n)
    .replace(/\./g, "")               // Remove periods (Dep. → Dep)
    .replace(/\s+/g, " ")
    .trim();
  // Remove common prefixes (SC Internacional → Internacional, FC Barcelona → Barcelona, Atlético Mineiro → Mineiro)
  s = s.replace(/\b(sc|ec|fc|cr|se|aa|ce|gr|ac|cf|as|rc|cd|ca|ss|afc|atletico)\b\s*/gi, "").trim();
  return s;
}

/** Resolve team name to canonical form via alias map. */
function resolveTeamAlias(name: string): string {
  const norm = normalizeTeamName(name);
  return TEAM_ALIASES[norm] ?? norm;
}

/** Deduplicate matches by canonical team names. Keeps the richer record (more odds/stats/predictions). */
function deduplicateMatches(matches: Match[]): Match[] {
  if (matches.length <= 1) return matches;
  const seen = new Map<string, { idx: number; richness: number }>();
  const result: Match[] = [];

  for (const m of matches) {
    // #135: Include date in key to avoid collision when same teams play on different dates
    const dateStr = m.datetime ? m.datetime.slice(0, 10) : "";
    const key = `${resolveTeamAlias(m.homeTeam.name)}||${resolveTeamAlias(m.awayTeam.name)}||${dateStr}`;
    const rich = matchRichness(m);
    const prev = seen.get(key);

    if (prev != null) {
      const prevMatch = result[prev.idx];
      if (rich > prev.richness) {
        // Current match is richer — replace, but merge live data from previous
        const merged = mergeMatchData(m, prevMatch);
        result[prev.idx] = merged;
        seen.set(key, { idx: prev.idx, richness: rich });
      } else {
        // Previous is richer — merge live data from current into it
        result[prev.idx] = mergeMatchData(prevMatch, m);
      }
      console.warn(`[dedup] Removed duplicate: ${m.homeTeam.name} vs ${m.awayTeam.name}`);
    } else {
      seen.set(key, { idx: result.length, richness: rich });
      result.push(m);
    }
  }
  return result;
}

function matchRichness(m: Match): number {
  let score = 0;
  if (m.predictions && m.predictions.length > 0) score += 100;
  if ((m as any).recommendations?.length > 0) score += 100;
  const odds = m.odds;
  if (odds) {
    for (const v of Object.values(odds)) {
      if (typeof v === "number" && v > 0) score++;
    }
  }
  const stats = m.stats;
  if (stats) {
    for (const v of Object.values(stats)) {
      if (typeof v === "number" && v > 0) score++;
    }
  }
  if (m.score && ((m.score.home ?? 0) + (m.score.away ?? 0)) > 0) score += 50;
  if (m.status === "live") score += 20;
  return score;
}

function mergeMatchData(primary: Match, secondary: Match): Match {
  const merged = { ...primary };
  // Merge live score if primary lacks it
  const pTotal = (primary.score?.home ?? 0) + (primary.score?.away ?? 0);
  const sTotal = (secondary.score?.home ?? 0) + (secondary.score?.away ?? 0);
  if (sTotal > 0 && pTotal === 0) {
    merged.score = secondary.score;
  }
  if (secondary.score?.halftime && !primary.score?.halftime) {
    merged.score = { ...(merged.score ?? { home: 0, away: 0 }), halftime: secondary.score.halftime };
  }
  // Merge live status
  if (secondary.status === "live" && primary.status !== "live") {
    merged.status = secondary.status;
    merged.period = secondary.period ?? merged.period;
    merged.minute = secondary.minute ?? merged.minute;
  }
  return merged;
}

function formatTime(dt: string) {
  try {
    const d = new Date(dt);
    return d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch {
    return "--:--";
  }
}

function formatDate(dt: string) {
  try {
    const d = new Date(dt);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch {
    return "--/--";
  }
}
/** Normaliza probabilidade para percentual 0-100. Aceita 0-1, 0-100 ou valores >100. */
function toPercent(value?: number | null): number {
  if (value == null || value < 0) return 0;
  if (value <= 1) return value * 100;
  if (value > 100) return value / 100;
  return value;
}

/** Normaliza e formata probabilidade em decimal (ex: 85.5%). */
function formatProb(value?: number | null): string {
  if (value == null || value < 0) return "-";
  const pct = toPercent(value);
  return `${pct.toFixed(1)}%`;
}

type LivePeriod = "1T" | "HT" | "2T";

/** Compute live period from kickoff time when backend hasn't supplied it yet.
 * When backend provides period/minute, use max(backend, estimated) so stale
 * backend data (e.g. 68' when real time is 90') doesn't freeze the display. */
function computeLiveInfo(match: Match): { period: LivePeriod; minute: number | null } | null {
  if (match.status !== "live") return null;
  try {
    const kickoff = new Date(match.datetime).getTime();
    const elapsed = Math.floor((Date.now() - kickoff) / 60_000);
    if (elapsed < 0) return null;
    let period = match.period ?? "";
    let minute: number | null = match.minute ?? null;
    if (elapsed <= 47) {
      const est = { period: "1T" as const, minute: Math.min(elapsed, 45) };
      if (!period) period = est.period;
      if (minute == null) minute = est.minute;
      else minute = Math.max(minute, est.minute);
    } else if (elapsed <= 62) {
      if (!period) period = "HT";
      minute = null;
    } else {
      const estMin = Math.min(elapsed - 15, 90);
      if (!period) period = "2T";
      if (minute == null) minute = estMin;
      else minute = Math.max(minute, estMin);
    }
    return { period: period as LivePeriod, minute };
  } catch {
    return match.period ? { period: match.period as LivePeriod, minute: match.minute ?? null } : null;
  }
}

/** Minutes elapsed since kickoff (null if in the future or invalid). */
function elapsedMinutes(datetime: string): number | null {
  try {
    const diff = Date.now() - new Date(datetime).getTime();
    if (diff <= 0) return null;
    return Math.floor(diff / 60_000);
  } catch {
    return null;
  }
}

/** Minutes until match kickoff (null if already started). */
function minutesToKickoff(datetime: string): number | null {
  try {
    const diff = new Date(datetime).getTime() - Date.now();
    if (diff <= 0) return null;
    return Math.floor(diff / 60_000);
  } catch {
    return null;
  }
}

/** Map pipeline predictions to highlighted odd positions for the active tab (#084). */
function getHighlightedOddPositions(
  predictions: MatchPrediction[] | undefined,
  activeTab: OddsTab,
): Set<string> {
  const result = new Set<string>();
  if (!predictions?.length) return result;

  for (const pred of predictions) {
    const m = (pred.mercado || "").toLowerCase();

    switch (activeTab) {
      case "1x2":
        if (m === "1" || (m.includes("1x2") && (m.includes("home") || m.includes("casa")))) result.add("1");
        else if (m === "x" || (m.includes("1x2") && (m.includes("draw") || m.includes("empate")))) result.add("X");
        else if (m === "2" || (m.includes("1x2") && (m.includes("away") || m.includes("fora")))) result.add("2");
        break;
      case "double-chance":
        if (m.includes("dc") && m.includes("1x")) result.add("1X");
        else if (m.includes("dc") && m.includes("12")) result.add("12");
        else if (m.includes("dc") && m.includes("x2")) result.add("X2");
        break;
      case "btts":
        if (m.includes("btts") && (m.includes("sim") || m.includes("yes"))) result.add("Sim");
        else if (m.includes("btts") && (m.includes("não") || m.includes("nao") || m.includes("no"))) result.add("Nao");
        break;
      case "goals": {
        const gm = m.match(/(\d+\.?\d*)/);
        if (!gm) break;
        if ((m.includes("over") || m.includes("mais")) && m.includes("gol")) result.add(`O ${gm[1]}`);
        break;
      }
      // cards and corners tabs show stats (Casa/Fora/Liga), not odds — skip
    }
  }
  return result;
}

function getHighlightReason(match: Match): string {
  const reasons: string[] = [];
  const homeProb = toPercent(match.stats?.homeWinProb ?? 0);
  const awayProb = toPercent(match.stats?.awayWinProb ?? 0);
  const maxProbPct = Math.max(homeProb, awayProb);
  const favName = homeProb >= awayProb ? match.homeTeam.name : match.awayTeam.name;
  const over25Pct = toPercent(match.stats?.over25Prob ?? 0);
  const bttsPct = toPercent(match.stats?.bttsProb ?? 0);
  const safePreds = match.predictions?.filter((p) => (p.classification || p.status) === "SAFE") ?? [];

  if (maxProbPct >= 65) reasons.push(`Confiança alta: ${favName} (${maxProbPct.toFixed(0)}%)`);
  if (over25Pct >= 70) reasons.push(`Over 2.5 provável (${over25Pct.toFixed(0)}%)`);
  if (bttsPct >= 65) reasons.push(`BTTS forte (${bttsPct.toFixed(0)}%)`);
  if (safePreds.length > 0) reasons.push(`Mercado SAFE: ${safePreds[0].mercado}`);
  if (reasons.length === 0 && maxProbPct >= 50) reasons.push(`Favorito claro: ${favName} (${maxProbPct.toFixed(0)}%)`);
  if (reasons.length === 0) reasons.push("Potencial estatístico detectado");

  return reasons.slice(0, 2).join(" • ");
}

function buildScreenshotName() {
  const stamp = new Date().toISOString().replace(/[:]/g, "-").replace("T", "_").slice(0, 19);
  return `sportsbank-picks-${stamp}.png`;
}

/** Known Danish Superliga teams — correct leagueId when backend returns wrong/missing leagueId */
const KNOWN_DANISH_TEAMS = new Set([
  "esbjerg", "hillerød", "hillerod", "hvidovre", "kolding if", "kolding", "fc midtjylland", "midtjylland",
  "fc copenhagen", "copenhagen", "brøndby", "brondby", "aalborg", "aab", "nordsjælland",
  "nordsjaelland", "silkeborg", "viborg", "ob", "odense", "randers", "lyngby", "vejle",
]);
function inferLeagueFromTeams(home: string, away: string): string | null {
  const h = normalizeTeamName(home);
  const a = normalizeTeamName(away);
  if (KNOWN_DANISH_TEAMS.has(h) || KNOWN_DANISH_TEAMS.has(a)) return "denmark-superliga";
  return null;
}

function normalizeMatch(item: any, leagueId: string, idx: number): Match {
  const home = item.home_team
    ?? (typeof item.homeTeam === "string" ? item.homeTeam : item.homeTeam?.name)
    ?? item.home ?? "Home";
  const away = item.away_team
    ?? (typeof item.awayTeam === "string" ? item.awayTeam : item.awayTeam?.name)
    ?? item.away ?? "Away";
  // Heuristic: correct leagueId when backend returns wrong/missing (e.g. Danish teams in EPL group)
  const inferred = inferLeagueFromTeams(home, away);
  // Backend config uses "superliga", frontend uses "denmark-superliga"
  const normalizedLid = leagueId === "superliga" ? "denmark-superliga" : leagueId;
  const resolvedLeagueId = inferred ?? normalizedLid;
  const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
  const league = AVAILABLE_LEAGUES.find((l) => l.id === resolvedLeagueId);
  return {
    id: item.id ?? `${resolvedLeagueId}-${resolveTeamAlias(home)}-${resolveTeamAlias(away)}`,
    footystatsId: item.footystatsId ?? undefined,
    leagueId: resolvedLeagueId,
    leagueName: league?.name ?? resolvedLeagueId,
    homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? item.homeForm ?? [], rating: item.homeTeam?.rating || item.ratings?.home || 0 },
    awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? item.awayForm ?? [], rating: item.awayTeam?.rating || item.ratings?.away || 0 },
    datetime: dt,
    venue: item.venue ?? item.stadium ?? "",
    status: item.status ?? "scheduled",
    score: (() => {
      const raw = item.score;
      if (raw && typeof raw.home === "number" && typeof raw.away === "number") {
        return raw;
      }
      // Coerce any non-null fields to numbers — use nullish coalescing
      // to avoid treating 0 as falsy (Number(0) || 0 works by coincidence
      // but Number(val) ?? 0 is semantically correct).
      if (raw && raw.home != null && raw.away != null) {
        return { home: Number(raw.home) ?? 0, away: Number(raw.away) ?? 0, halftime: raw.halftime };
      }
      // For finished or live matches without score, default to 0-0.
      // A live match that just kicked off is at 0-0 until proven otherwise;
      // the /live-scores overlay will update with the real score when available.
      if (item.status === "finished" || item.status === "live") {
        return { home: 0, away: 0 };
      }
      // Discard invalid score objects (e.g. {home: null, away: null})
      return undefined;
    })(),
    period: item.period ?? undefined,
    minute: item.minute ?? undefined,
    odds: {
      home: item.odds?.home ?? 0,
      draw: item.odds?.draw ?? 0,
      away: item.odds?.away ?? 0,
      over15: item.odds?.over15 ?? 0,
      over25: item.odds?.over25 ?? 0,
      over35: item.odds?.over35 ?? 0,
      over45: item.odds?.over45 ?? 0,
      under25: item.odds?.under25 ?? 0,
      bttsYes: item.odds?.bttsYes ?? 0,
      bttsNo: item.odds?.bttsNo ?? 0,
    },
    stats: {
      homeWinProb: item.stats?.homeWinProb ?? 0,
      drawProb: item.stats?.drawProb ?? 0,
      awayWinProb: item.stats?.awayWinProb ?? 0,
      avgGoals: item.stats?.avgGoals ?? 0,
      bttsProb: item.stats?.bttsProb ?? 0,
      over15Prob: item.stats?.over15Prob ?? 0,
      over25Prob: item.stats?.over25Prob ?? 0,
      over35Prob: item.stats?.over35Prob ?? 0,
      over45Prob: item.stats?.over45Prob ?? 0,
      lambdaHome: item.stats?.lambdaHome ?? 0,
      lambdaAway: item.stats?.lambdaAway ?? 0,
      homePossession: item.stats?.homePossession ?? 0,
      awayPossession: item.stats?.awayPossession ?? 0,
      homeXG: item.stats?.homeXG ?? 0,
      awayXG: item.stats?.awayXG ?? 0,
      homeForm: item.stats?.homeForm ?? item.homeForm ?? item.homeTeam?.form ?? [],
      awayForm: item.stats?.awayForm ?? item.awayForm ?? item.awayTeam?.form ?? [],
      leagueRegime: item.stats?.leagueRegime ?? "",
      leagueVolatility: item.stats?.leagueVolatility ?? "",
      regime: item.stats?.regime ?? "",
      homeCornersPerMatch: item.stats?.homeCornersPerMatch ?? 0,
      awayCornersPerMatch: item.stats?.awayCornersPerMatch ?? 0,
      homeCardsPerMatch: item.stats?.homeCardsPerMatch ?? 0,
      awayCardsPerMatch: item.stats?.awayCardsPerMatch ?? 0,
      homeShotsOnTarget: item.stats?.homeShotsOnTarget ?? undefined,
      awayShotsOnTarget: item.stats?.awayShotsOnTarget ?? undefined,
      homeShotsPerMatch: item.stats?.homeShotsPerMatch ?? undefined,
      awayShotsPerMatch: item.stats?.awayShotsPerMatch ?? undefined,
      homeFoulsPerMatch: item.stats?.homeFoulsPerMatch ?? undefined,
      awayFoulsPerMatch: item.stats?.awayFoulsPerMatch ?? undefined,
      leagueAvgCorners: item.stats?.leagueAvgCorners ?? 0,
      leagueAvgCards: item.stats?.leagueAvgCards ?? 0,
      leagueAvgFouls: item.stats?.leagueAvgFouls ?? undefined,
      leagueAvgShots: item.stats?.leagueAvgShots ?? undefined,
      // League extended
      leagueHomeAdvantage: item.stats?.leagueHomeAdvantage ?? undefined,
      leagueCleanSheetsPct: item.stats?.leagueCleanSheetsPct ?? undefined,
      leagueOver25Pct: item.stats?.leagueOver25Pct ?? undefined,
      leagueXgAvg: item.stats?.leagueXgAvg ?? undefined,
      // Team advanced stats
      homeBttsPercentage: item.stats?.homeBttsPercentage ?? undefined,
      awayBttsPercentage: item.stats?.awayBttsPercentage ?? undefined,
      homeCleanSheetPct: item.stats?.homeCleanSheetPct ?? undefined,
      awayCleanSheetPct: item.stats?.awayCleanSheetPct ?? undefined,
      homeFtsPercentage: item.stats?.homeFtsPercentage ?? undefined,
      awayFtsPercentage: item.stats?.awayFtsPercentage ?? undefined,
      homeOver25Percentage: item.stats?.homeOver25Percentage ?? undefined,
      awayOver25Percentage: item.stats?.awayOver25Percentage ?? undefined,
      homeWinPercentage: item.stats?.homeWinPercentage ?? undefined,
      awayWinPercentage: item.stats?.awayWinPercentage ?? undefined,
      homeXgForAvg: item.stats?.homeXgForAvg ?? undefined,
      awayXgForAvg: item.stats?.awayXgForAvg ?? undefined,
      homeXgAgainstAvg: item.stats?.homeXgAgainstAvg ?? undefined,
      awayXgAgainstAvg: item.stats?.awayXgAgainstAvg ?? undefined,
      homeCornersAgainstPerMatch: item.stats?.homeCornersAgainstPerMatch ?? undefined,
      awayCornersAgainstPerMatch: item.stats?.awayCornersAgainstPerMatch ?? undefined,
      homeCornersCount: item.stats?.homeCornersCount ?? item.home_team_corner_count ?? undefined,
      awayCornersCount: item.stats?.awayCornersCount ?? item.away_team_corner_count ?? undefined,
      homeYellowCards: item.stats?.homeYellowCards ?? item.home_team_yellow_cards ?? undefined,
      awayYellowCards: item.stats?.awayYellowCards ?? item.away_team_yellow_cards ?? undefined,
      homeRedCards: item.stats?.homeRedCards ?? item.home_team_red_cards ?? undefined,
      awayRedCards: item.stats?.awayRedCards ?? item.away_team_red_cards ?? undefined,
      homeLeaguePosition: item.stats?.homeLeaguePosition ?? undefined,
      awayLeaguePosition: item.stats?.awayLeaguePosition ?? undefined,
      homeAvgTotalGoals: item.stats?.homeAvgTotalGoals ?? undefined,
      awayAvgTotalGoals: item.stats?.awayAvgTotalGoals ?? undefined,
    },
    h2h: {
      totalMatches: item.h2h?.totalMatches ?? 0,
      homeWins: item.h2h?.homeWins ?? 0,
      draws: item.h2h?.draws ?? 0,
      awayWins: item.h2h?.awayWins ?? 0,
      avgGoals: item.h2h?.avgGoals ?? 0,
    },
    predictions: item.mercados ?? item.predictions ?? [],
    source: item.source ?? "footystats",
    lastUpdated: item.lastUpdated ?? new Date().toISOString(),
  };
}

function toDetailData(match: Match, aiData: AIAnalysis | null, isAiLoading: boolean): MatchDetailData {
  const h = safeOdd(match.odds?.home, 1.7);
  const d = safeOdd(match.odds?.draw, 3.1);
  const a = safeOdd(match.odds?.away, 3.8);
  const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
  const ai: AIAnalysis | undefined = isAiLoading
    ? { summary: "Carregando analise Mistral...", key_points: ["Buscando insights..."], recommendation: "Aguardando.", confidence: 5, last_updated: new Date().toLocaleString("pt-BR") }
    : aiData ?? undefined;
  return {
    id: match.id,
    league: league?.name ?? match.leagueName ?? match.leagueId,
    leagueId: match.leagueId,
    season: league?.season ?? "2026",
    homeTeam: match.homeTeam.name,
    awayTeam: match.awayTeam.name,
    homeTeamLogo: match.homeTeam.logo || undefined,
    awayTeamLogo: match.awayTeam.logo || undefined,
    startTime: match.datetime,
    status: match.status === "postponed" ? "scheduled" : match.status,
    score: match.score,
    period: (() => {
      const li = computeLiveInfo(match);
      return (li?.period ?? match.period) as "1T" | "HT" | "2T" | undefined;
    })(),
    minute: (() => {
      const li = computeLiveInfo(match);
      return li?.minute ?? match.minute;
    })(),
    venue: { name: match.venue || "Estadio nao informado" },
    odds: { home: h, draw: d, away: a },
    doubleChance: {
      homeOrDraw: parseFloat((1 / (1 / h + 1 / d)).toFixed(2)),
      homeOrAway: parseFloat((1 / (1 / h + 1 / a)).toFixed(2)),
      drawOrAway: parseFloat((1 / (1 / d + 1 / a)).toFixed(2)),
    },
    btts: { yes: safeOdd(match.odds?.bttsYes, 2.0), no: safeOdd(match.odds?.bttsNo, 1.7) },
    matchStats: mapMatchStats(match.stats as Record<string, unknown> | undefined),
    h2h: match.h2h,
    homeForm: match.stats?.homeForm ?? match.homeTeam.form,
    awayForm: match.stats?.awayForm ?? match.awayTeam.form,
    round: match.stats?.regime ?? "-",
    aiAnalysis: ai,
    predictions: match.predictions,
    currentCorners: match.currentCorners ?? null,
  };
}

/* ── COMPONENT ── */

export default function Dashboard() {
  const { canSeeAudit, canSeeReasonCodes, canRegenMistral, canSeeFerramentas, canSeeConfiabilidade } = useRole();
  const [mounted, setMounted] = useState(false);
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [aiAnalysisMatchId, setAiAnalysisMatchId] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  /** #119a — avoid duplicate live overlay fetch on first progressive batch */
  const livePollAfterBatchRef = useRef(false);
  const [oddsTab, setOddsTab] = useState<OddsTab>("1x2");
  const [collapsedLeagues, setCollapsedLeagues] = useState<Set<string>>(new Set());
  const [dateMode, setDateMode] = useState<DateMode>("today");
  const [navView, setNavView] = useState<NavView>("matches");
  const [selectedLeague, setSelectedLeague] = useState<string | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => {
    if (typeof window !== "undefined") {
      try {
        const s = localStorage.getItem("sb-favorites");
        if (s) return new Set(JSON.parse(s));
      } catch { }
    }
    return new Set();
  });
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [statusFilter, setStatusFilter] = useState<"all" | "live" | "finished" | "scheduled">("all");
  const [shareLoading, setShareLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [batchAuditResult, setBatchAuditResult] = useState<BatchAuditResult | null>(null);
  const [batchAuditLoading, setBatchAuditLoading] = useState(false);
  const [batchAuditOpen, setBatchAuditOpen] = useState(false);
  const [reliabilityOpen, setReliabilityOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [reliabilityData, setReliabilityData] = useState<any>(null);
  const [reliabilityLoading, setReliabilityLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [bankroll, setBankroll] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sportsbankzu-bankroll");
      if (saved) { const v = parseFloat(saved); if (!isNaN(v) && v > 0) return v; }
    }
    return 250;
  });
  const [isMockData, setIsMockData] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<string | null>(null);
  const mainContentRef = useRef<HTMLDivElement>(null);
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const auditResultRef = useRef<HTMLDivElement>(null);

  // Hook para detectar se estamos em mobile/tablet
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const leagueClassifications = useLeagueClassifications();
  const [shareBusy, setShareBusy] = useState<"copy" | "whatsapp" | null>(null);
  const [appVersion, setAppVersion] = useState(VERSION_FALLBACK);
  const [combinadas, setCombinadas] = useState<CombinadasData | null>(null);
  const [combinadasLoading, setCombindasLoading] = useState(false);
  const [combinadasError, setCombindasError] = useState<string | null>(null);
  const [combinadasMinStatus, setCombindasMinStatus] = useState<"SAFE" | "NEUTRO">("NEUTRO");
  const [combinadasSubTab, setCombindasSubTab] = useState<"intra" | "inter">("intra");
  const [shareFeedback, setShareFeedback] = useState("");
  const [shareFeedbackTone, setShareFeedbackTone] = useState<ShareFeedbackTone>("info");
  const capturePanelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { setMounted(true); }, []);

  // Fire-and-forget: ping backend health to warm up Lambda before main data load
  useEffect(() => {
    fetch("/api/backend/health", { cache: "no-store" }).catch(() => { });
  }, []);

  // Auto-refresh stale JS: compare client buildId with server buildId
  useEffect(() => {
    async function checkFreshness() {
      try {
        const res = await fetch("/", { method: "HEAD", cache: "no-store" });
        // Next.js sets x-nextjs-matched-path or we can re-fetch the HTML
        // Simpler: fetch the page and check if the JS chunk URLs match
        const htmlRes = await fetch(window.location.href, { cache: "no-store" });
        const html = await htmlRes.text();
        // Extract buildId from server HTML
        const match = html.match(/"buildId":"([^"]+)"/);
        if (match) {
          const serverBuildId = match[1];
          const clientBuildId = (window as any).__NEXT_DATA__?.buildId;
          if (clientBuildId && serverBuildId !== clientBuildId) {
            console.log(`[stale-check] Build mismatch: client=${clientBuildId} server=${serverBuildId}. Reloading...`);
            window.location.reload();
          }
        }
      } catch {
        // Silently ignore — freshness check is best-effort
      }
    }
    // Check after 2s (let the page settle first)
    const timer = setTimeout(checkFreshness, 2000);
    return () => clearTimeout(timer);
  }, []);

  // Busca a versão real do backend (fica em sync com o cron de auditoria)
  useEffect(() => {
    fetch("/api/audit/status?days=1", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { if (d?.version) setAppVersion(d.version); })
      .catch(() => { /* mantém o fallback VERSION_FALLBACK */ });
  }, []);

  // Scroll right panel to top when a new match is selected
  useEffect(() => {
    if (selectedMatchId && rightPanelRef.current) {
      rightPanelRef.current.scrollTop = 0;
    }
  }, [selectedMatchId]);

  // Stable league-ID string — only uses leagues that actually have loaded matches.
  // Never falls back to ALL leagues to avoid overwhelming the backend.
  const combinadasLeagues = useMemo(() => {
    const ids = Array.from(new Set(allMatches.map((m) => m.leagueId))).sort();
    return ids.join(",");
  }, [allMatches]);

  const fetchCombinadas = useCallback(async (minStatus: "SAFE" | "NEUTRO" = "NEUTRO") => {
    if (!allMatches.length) {
      setCombindasError("Aguarde o carregamento dos jogos antes de calcular duplas.");
      return;
    }
    setCombindasLoading(true);
    setCombindasError(null);
    try {
      // POST with pre-loaded matches to avoid backend re-fetching all leagues
      // (which caused 504 timeouts when many leagues were selected)
      const payload = {
        matches: allMatches.map((m) => ({
          id: m.id,
          leagueId: m.leagueId,
          leagueName: m.leagueName,
          homeTeam: m.homeTeam.name,
          awayTeam: m.awayTeam.name,
          datetime: m.datetime,
          status: m.status,
          odds: m.odds,
          stats: m.stats,
          mercados: m.predictions,
        })),
        tipos: "intra,inter",
        min_status: minStatus,
        limite_intra: 10,
        limite_inter: 10,
      };
      const res = await fetch("/api/combinadas", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      });
      const text = await res.text();
      let data: CombinadasData & { _error?: Record<string, unknown> };
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error(`Servidor retornou resposta invalida (HTTP ${res.status}). Tente novamente em instantes.`);
      }
      if (!res.ok) {
        const errObj = data?._error;
        const errKind = errObj?.kind;
        if (errKind === "NOT_CONFIGURED") throw new Error("Backend nao configurado. Verifique a variavel PY_BACKEND_URL.");
        if (errKind === "TIMEOUT") throw new Error("Timeout ao conectar com o backend. Tente novamente.");
        if (errKind === "CONNECTION_ERROR") throw new Error("Backend indisponivel. Verifique se o servidor esta rodando.");
        throw new Error((errObj?.message as string) || `Servidor indisponivel (HTTP ${res.status}). Tente novamente em instantes.`);
      }
      setCombinadas(data);
    } catch (err) {
      setCombindasError(err instanceof Error ? err.message : "Erro ao carregar combinadas.");
    } finally {
      setCombindasLoading(false);
    }
  }, [allMatches]);

  const dateLabel = dateMode === "today" ? "Hoje" : dateMode === "tomorrow" ? "Amanha" : "Proxima Rodada";

  // Shared function: fetch live scores from backend and merge into allMatches
  // Ref to track live league IDs for fallback query without re-creating the callback
  const liveLeagueIdsRef = useRef<string>("");
  useEffect(() => {
    const liveLeagues = new Set<string>();
    for (const m of allMatches) {
      if (m.status === "live") liveLeagues.add(m.leagueId);
    }
    liveLeagueIdsRef.current = Array.from(liveLeagues).join(",");
  }, [allMatches]);

  // Track consecutive live-score failures for retry backoff (#071 Camada 3)
  const liveScoreFailCountRef = useRef(0);

  const fetchLiveScores = useCallback(async () => {
    try {
      // Pass live league IDs so the API route can fallback to /fixtures when /live-scores is empty
      const leagues = liveLeagueIdsRef.current;
      const qs = leagues ? `?leagues=${encodeURIComponent(leagues)}` : "";
      const res = await fetch(`/api/matches/live${qs}`, { cache: "no-store" });

      // Camada 3 (#071): retry on 503 with backoff instead of silencing
      if (!res.ok) {
        if (res.status === 503) {
          liveScoreFailCountRef.current++;
          const delay = Math.min(3000 * liveScoreFailCountRef.current, 15_000);
          console.warn(`[live-scores] 503 — retry #${liveScoreFailCountRef.current} in ${delay}ms`);
          await new Promise((r) => setTimeout(r, delay));
          const retry = await fetch(`/api/matches/live${qs}`, { cache: "no-store" });
          if (!retry.ok) return;
          const retryData = await retry.json();
          const retryList = retryData.matches ?? [];
          if (retryList.length > 0) {
            liveScoreFailCountRef.current = 0;
            // Fall through to merge logic below via recursive-like pattern
            mergeLiveOverlay(retryList);
            return;
          }
        }
        return;
      }

      liveScoreFailCountRef.current = 0;
      const data = await res.json();
      const liveList: Array<{ id: number; homeTeam: string; awayTeam: string; status: string; score: { home: number; away: number; halftime?: { home: number; away: number } }; period?: string; minute?: number; currentCorners?: number }> = data.matches ?? [];

      // Camada 2 (#071, #122): when liveList is empty, do NOT auto-finish.
      // Empty list may be caused by API rate limit, not actual match completion.
      // Auto-finish only triggers below when liveList has data but a match is missing.
      if (liveList.length === 0) {
        return;
      }

      // Diagnostic: log live overlay data
      if (process.env.NODE_ENV === "development" || liveList.some((lm) => (lm.score?.home ?? 0) > 0 || (lm.score?.away ?? 0) > 0)) {
        console.log(`[live-scores] Overlay: ${liveList.length} matches`, liveList.map((lm) => `${lm.homeTeam} ${lm.score?.home}-${lm.score?.away} ${lm.awayTeam} (id=${lm.id})`));
      }
      mergeLiveOverlay(liveList);

      // Camada 2b (#122): auto-finish matches missing from a NON-EMPTY live list.
      // If live-scores returned data for some matches but NOT this one, and
      // elapsed > 100min, the match likely ended and left the live feed.
      setAllMatches((prev) => {
        let changed = false;
        const updated = prev.map((m) => {
          if (m.status !== "live") return m;
          const elapsed = elapsedMinutes(m.datetime);
          if (elapsed === null || elapsed <= 100) return m;
          // Check if this match was in the live list
          const inLiveList = liveList.some((lm) => {
            if (m.footystatsId != null && lm.id != null && Number(m.footystatsId) === Number(lm.id)) return true;
            const mH = resolveTeamAlias(m.homeTeam.name);
            const lH = resolveTeamAlias(lm.homeTeam);
            const mA = resolveTeamAlias(m.awayTeam.name);
            const lA = resolveTeamAlias(lm.awayTeam);
            return (mH === lH || (mH && lH && (mH.includes(lH) || lH.includes(mH)))) &&
                   (mA === lA || (mA && lA && (mA.includes(lA) || lA.includes(mA))));
          });
          if (!inLiveList) {
            console.log(`[live-scores] Auto-finish: ${m.homeTeam.name} vs ${m.awayTeam.name} (elapsed=${elapsed}min, absent from ${liveList.length} live matches)`);
            changed = true;
            return { ...m, status: "finished" as const };
          }
          return m;
        });
        return changed ? updated : prev;
      });
    } catch (err) {
      // Camada 3 (#071): log the error instead of silencing
      console.warn("[live-scores] fetch error:", err instanceof Error ? err.message : err);
    }
  }, []);

  /** Merge live overlay data into allMatches state */
  function mergeLiveOverlay(liveList: Array<{ id: number; homeTeam: string; awayTeam: string; status: string; score: { home: number; away: number; halftime?: { home: number; away: number } }; period?: string; minute?: number; currentCorners?: number }>) {
    setAllMatches((prev) => {
      let changed = false;
      let matched = 0;
      let unmatched = 0;
      const updated = prev.map((m) => {
        const live = liveList.find((lm) => {
          // #135: Skip if match is scheduled for a different day (prevents stale score from old game)
          if (m.status === "scheduled" && m.datetime) {
            const matchDate = m.datetime.slice(0, 10);
            const today = new Date().toISOString().slice(0, 10);
            if (matchDate !== today) return false;
          }
          // Match by FootyStats ID (coerce to number for safe comparison)
          if (m.footystatsId != null && lm.id != null) {
            if (Number(m.footystatsId) === Number(lm.id)) return true;
          }
          // Fallback: alias-resolved + normalized team name comparison
          const mHome = resolveTeamAlias(m.homeTeam.name);
          const mAway = resolveTeamAlias(m.awayTeam.name);
          const lHome = resolveTeamAlias(lm.homeTeam);
          const lAway = resolveTeamAlias(lm.awayTeam);
          if (mHome === lHome && mAway === lAway) return true;
          // Partial match: one name contains the other (handles "FC Barcelona" vs "Barcelona")
          if (lHome && mHome && (mHome.includes(lHome) || lHome.includes(mHome)) &&
              lAway && mAway && (mAway.includes(lAway) || lAway.includes(mAway))) return true;
          return false;
        });
        if (!live) return m;
        matched++;
        const newStatus = live.status as Match["status"];
        // When score is null/undefined from overlay (missing goal data),
        // keep existing score but still update status/period/minute.
        // If existing score is also missing for a live match, default to 0-0.
        const hasLiveScore = live.score != null && (live.score.home != null || live.score.away != null);
        let liveScore = m.score;
        if (hasLiveScore) {
          const liveScoreHome = typeof live.score?.home === "number" ? live.score.home : Number(live.score?.home) ?? 0;
          const liveScoreAway = typeof live.score?.away === "number" ? live.score.away : Number(live.score?.away) ?? 0;
          // Guard: never overwrite a non-zero score with 0-0 from live overlay
          const existingTotal = (m.score?.home ?? 0) + (m.score?.away ?? 0);
          const liveTotal = liveScoreHome + liveScoreAway;
          const useExistingScore = existingTotal > 0 && liveTotal === 0;
          liveScore = useExistingScore
            ? m.score!
            : { home: liveScoreHome, away: liveScoreAway, halftime: live.score?.halftime };
        } else if (!liveScore && newStatus === "live") {
          // Overlay has no score AND existing has no score — safe 0-0 fallback
          // so the card never shows "- : -" for a confirmed live match.
          console.warn(`[live-scores] No score data for live match ${live.homeTeam} vs ${live.awayTeam}, using 0-0 fallback`);
          liveScore = { home: 0, away: 0 };
        }
        const scoreChanged = liveScore?.home !== m.score?.home || liveScore?.away !== m.score?.away;
        const statusChanged = m.status !== newStatus;
        const periodChanged = m.period !== (live.period as Match["period"]);
        const minuteChanged = m.minute !== live.minute;
        const cornersChanged = live.currentCorners != null && m.currentCorners !== live.currentCorners;
        if (!scoreChanged && !statusChanged && !periodChanged && !minuteChanged && !cornersChanged) return m;
        changed = true;
        if (process.env.NODE_ENV === "development" && live.currentCorners != null) {
          console.log(`[live-scores] currentCorners merged: ${m.homeTeam.name} vs ${m.awayTeam.name} → ${live.currentCorners}`);
        }
        return {
          ...m,
          status: newStatus,
          score: liveScore,
          period: live.period as Match["period"],
          minute: live.minute,
          ...(live.currentCorners != null ? { currentCorners: live.currentCorners } : {}),
        };
      });
      unmatched = liveList.length - matched;
      if (unmatched > 0) {
        console.warn(`[live-scores] ${matched} matched, ${unmatched} unmatched from overlay`);
      }
      return changed ? updated : prev;
    });
  }

  /* Fetch all leagues — fallback to "week" if today returns empty */
  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      livePollAfterBatchRef.current = false;
      setHasError(false);
      setIsMockData(false);
      setErrorMessage(null);
      setErrorCode(null);
      setDataSource(null);
      // Clear stale matches when date mode changes to prevent cross-date leakage
      // (e.g. "week" data persisting when switching back to "today")
      setAllMatches([]);

      const allLeagueIds = AVAILABLE_LEAGUES.map((l) => l.id).join(",");

      /** Backend espera "today" | "tomorrow" | "week" (timezone BRT), não YYYY-MM-DD */
      function dateParamFor(mode: DateMode): string {
        return mode;
      }

      /** #119a — merge each fan-out batch as it arrives */
      const onBatchReady = (batch: MatchesResponse) => {
        const raw = batch.matches ?? [];
        if (raw.length === 0) return;
        const normalized = raw.map((item: any, idx: number) => {
          const lid = item.leagueId ?? item.league ?? "unknown";
          return normalizeMatch(item, lid, idx);
        });
        setAllMatches((prev) => deduplicateMatches([...prev, ...normalized]));
        setDataSource((prev) => batch._dataSource ?? prev);
        setIsMockData((m) => m || !!batch._isMockData);
        setSelectedMatchId((prev) => prev ?? normalized[0].id);
        if (!livePollAfterBatchRef.current) {
          livePollAfterBatchRef.current = true;
          queueMicrotask(() => fetchLiveScores());
        }
      };

      try {
        let res: MatchesResponse = await getMatchesByLeague(allLeagueIds, dateParamFor(dateMode), onBatchReady);
        let raw = res?.matches ?? [];

        // Auto-retry once on transient errors (Lambda cold start, network blip, etc.)
        const retryKinds = new Set(["TIMEOUT", "HTTP_ERROR", "CONNECTION_ERROR", "NETWORK_ERROR", "UNKNOWN"]);
        if (raw.length === 0 && res._error && retryKinds.has(res._error.kind)) {
          console.log(`[dashboard] ${res._error.kind} on first attempt, retrying (Lambda cold start)...`);
          res = await getMatchesByLeague(allLeagueIds, dateParamFor(dateMode), onBatchReady);
          raw = res?.matches ?? [];
        }

        // Track data source and error state
        setDataSource(res._dataSource ?? null);
        setIsMockData(res._isMockData ?? false);

        if (res._error) {
          setHasError(true);
          setErrorMessage(res._error.message);
          setErrorCode(res._error.kind ?? null);
        }

        // Auto-fallback: if today returns empty (and no error), try week
        if (raw.length === 0 && dateMode === "today" && !res._error) {
          setAllMatches([]);
          livePollAfterBatchRef.current = false;
          res = await getMatchesByLeague(allLeagueIds, "week", onBatchReady);
          raw = res?.matches ?? [];
          if (raw.length > 0) {
            setDateMode("week");
            setDataSource(res._dataSource ?? null);
            setIsMockData(res._isMockData ?? false);
          }
          if (res._error) {
            setHasError(true);
            setErrorMessage(res._error.message);
            setErrorCode(res._error.kind ?? null);
          }
        }

        const normalized = raw.map((item: any, idx: number) => {
          // Use "unknown" instead of first league — avoids wrongly assigning to Premier League
          const lid = item.leagueId ?? item.league ?? "unknown";
          return normalizeMatch(item, lid, idx);
        });
        // Deduplicate: same match from different sources (e.g. "Wolves" vs "Wolverhampton Wanderers")
        const deduped = deduplicateMatches(normalized);
        setAllMatches(deduped);
        if (normalized.length > 0) setSelectedMatchId((prev) => prev ?? normalized[0].id);

        // Immediately fetch live scores to overlay real-time data
        // (league-matches used by /fixtures has stale goal counts for live matches)
        if (normalized.length > 0) {
          fetchLiveScores();
        }
      } catch {
        // Don't clear matches on error — preserve what we have
        setHasError(true);
        setErrorMessage("Erro inesperado ao carregar jogos. Tente novamente.");
        setErrorCode("CLIENT_EXCEPTION");
      } finally {
        setLoading(false);
      }
    }
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateMode]);

  // Live score polling — 30s when live matches exist, 120s otherwise.
  // Pauses when browser tab is hidden to save bandwidth.
  const hasMatches = allMatches.length > 0;
  const hasLiveMatches = useMemo(() => allMatches.some((m) => m.status === "live"), [allMatches]);
  const { lastUpdated: liveLastUpdated } = useLivePolling(fetchLiveScores, {
    hasMatches,
    hasLiveMatches,
    liveIntervalMs: 30_000,
    idleIntervalMs: 120_000,
  });

  // Force re-render every 30s when live matches exist — computeLiveInfo uses Date.now()
  // so the minute display updates even when backend polling returns cached data.
  useEffect(() => {
    if (!hasLiveMatches) return;
    const tick = setInterval(() => {
      setAllMatches((prev) => (prev.length ? [...prev] : prev));
    }, 30_000);
    return () => clearInterval(tick);
  }, [hasLiveMatches]);

  // Camada 1 (#071): safety timeout — if a match stays "live" for > 120min
  // since kickoff, mark as finished locally. Checks every 60s.
  useEffect(() => {
    if (!hasLiveMatches) return;
    const timer = setInterval(() => {
      setAllMatches((prev) => {
        let changed = false;
        const updated = prev.map((m) => {
          if (m.status !== "live") return m;
          const elapsed = elapsedMinutes(m.datetime);
          if (elapsed !== null && elapsed > 120) {
            console.log(`[live-scores] Safety timeout: ${m.homeTeam.name} vs ${m.awayTeam.name} (elapsed=${elapsed}min > 120)`);
            changed = true;
            return { ...m, status: "finished" as const };
          }
          return m;
        });
        return changed ? updated : prev;
      });
    }, 60_000);
    return () => clearInterval(timer);
  }, [hasLiveMatches]);

  const selectedMatch = useMemo(() => allMatches.find((m) => m.id === selectedMatchId), [allMatches, selectedMatchId]);

  useEffect(() => {
    if (selectedMatch?.id !== aiAnalysisMatchId) {
      setAiAnalysis(null);
      setAiAnalysisMatchId(selectedMatch?.id ?? null);
      setAuditResult(null);
      // Auto-fetch AI analysis when a new match is selected (#090)
      if (selectedMatch) {
        setAiLoading(true);
        getAiMatchAnalysis(selectedMatch.id, selectedMatch.homeTeam.name, selectedMatch.awayTeam.name)
          .then((analysis) => {
            setAiAnalysis(analysis);
            setAiAnalysisMatchId(selectedMatch.id);
          })
          .catch(() => { /* AI is optional */ })
          .finally(() => setAiLoading(false));
      }
    }
  }, [selectedMatch, aiAnalysisMatchId]);

  const handleGenerateAiAnalysis = useCallback(async () => {
    if (!selectedMatch) return;
    setAiLoading(true);
    setAuditResult(null);
    try {
      const analysis = await getAiMatchAnalysis(selectedMatch.id, selectedMatch.homeTeam.name, selectedMatch.awayTeam.name);
      setAiAnalysis(analysis);
      setAiAnalysisMatchId(selectedMatch.id);
    } finally {
      setAiLoading(false);
    }
  }, [selectedMatch]);


  const detailData = useMemo<MatchDetailData | null>(() => {
    if (!selectedMatch) return null;
    return toDetailData(selectedMatch, aiAnalysis, aiLoading);
  }, [selectedMatch, aiAnalysis, aiLoading]);

  const toggleLeague = useCallback((lid: string) => {
    setCollapsedLeagues((prev) => {
      const next = new Set(prev);
      next.has(lid) ? next.delete(lid) : next.add(lid);
      return next;
    });
  }, []);

  const displayMatches = useMemo(() => {
    let list = allMatches;
    if (selectedLeague) list = list.filter((m) => m.leagueId === selectedLeague);
    if (showFavoritesOnly) list = list.filter((m) => favoriteIds.has(m.id));
    if (statusFilter !== "all") list = list.filter((m) => m.status === statusFilter);
    return list;
  }, [allMatches, selectedLeague, showFavoritesOnly, favoriteIds, statusFilter]);

  const toggleFavorite = useCallback((matchId: string) => {
    setFavoriteIds((prev) => {
      const next = new Set(prev);
      if (next.has(matchId)) next.delete(matchId);
      else next.add(matchId);
      try {
        localStorage.setItem("sb-favorites", JSON.stringify(Array.from(next)));
      } catch { }
      return next;
    });
  }, []);

  // Persist bankroll to localStorage (#094)
  const handleBankrollChange = useCallback((v: number) => {
    setBankroll(v);
    try { localStorage.setItem("sportsbankzu-bankroll", v.toString()); } catch {}
  }, []);

  const handleTopbarShareWhatsApp = useCallback(async () => {
    const el = mainContentRef.current;
    if (!el) return;
    setShareLoading(true);
    try {
      const html2canvas = (await import("html2canvas")).default;
      const canvas = await html2canvas(el, {
        useCORS: true,
        scale: window.devicePixelRatio || 1,
        logging: false,
        backgroundColor: "var(--st-bg-primary, #0f0f12)",
      });
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/png", 0.95)
      );
      if (!blob) throw new Error("Falha ao gerar imagem");
      const file = new File([blob], "sportsbankzu-pro-dashboard.png", { type: "image/png" });
      const url = typeof window !== "undefined" ? window.location.href : "";
      const msg = encodeURIComponent(`Confira o dashboard SportsBankZU Pro: ${url}`);
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          title: "SportsBankZU Pro",
          text: `Confira o dashboard: ${url}`,
          files: [file],
        });
      } else {
        const a = document.createElement("a");
        a.href = canvas.toDataURL("image/png");
        a.download = "sportsbankzu-pro-dashboard.png";
        a.click();
        window.open(`https://wa.me/?text=${msg}`, "_blank", "noopener");
      }
    } catch (err) {
      console.error("Share error:", err);
      const url = typeof window !== "undefined" ? window.location.href : "";
      window.open(`https://wa.me/?text=${encodeURIComponent(`Confira o SportsBankZU Pro: ${url}`)}`, "_blank", "noopener");
    } finally {
      setShareLoading(false);
    }
  }, []);

  const handleAudit = useCallback(async () => {
    if (!selectedMatch || auditLoading) return;
    setAuditLoading(true);
    setAuditResult(null);
    try {
      const predictions = selectedMatch.predictions?.map((p: any) => ({
        mercado: p.mercado,
        status: p.status,
        prob_min: p.prob_min,
        prob_max: p.prob_max,
        odd_minima: p.odd_minima,
      }));
      // Only use aiAnalysis if it belongs to the currently selected match (prevent race condition)
      const safeAi = aiAnalysis && aiAnalysisMatchId === selectedMatch.id ? aiAnalysis : null;
      const aiSummary = safeAi
        ? { summary: safeAi.summary, key_points: safeAi.key_points, recommendation: safeAi.recommendation, confidence: safeAi.confidence }
        : undefined;
      const result = await postMatchAudit(
        selectedMatch.id,
        predictions,
        aiSummary,
        selectedMatch.homeTeam?.name,
        selectedMatch.awayTeam?.name,
      );
      if (result.ok) {
        setAuditResult(result.audit);
      } else {
        const msg = (result as { message: string }).message;
        setAuditResult({
          audit_confidence: 0,
          validation: {
            probabilities: { status: "UNKNOWN", notes: msg },
            lambdas: { status: "UNKNOWN", notes: msg },
            ev: { status: "UNKNOWN", notes: msg },
          },
          audit_type: "error",
        } as AuditResult);
      }
      // Scroll automático para o resultado da auditoria dentro do painel direito
      setTimeout(() => {
        if (auditResultRef.current && rightPanelRef.current) {
          rightPanelRef.current.scrollTo({
            top: auditResultRef.current.offsetTop - rightPanelRef.current.offsetTop,
            behavior: "smooth",
          });
        }
      }, 150);
    } catch (err) {
      console.error("Audit error:", err);
      const errMsg = err instanceof Error ? err.message : "Erro desconhecido";
      setAuditResult({
        audit_confidence: 0,
        validation: {
          probabilities: { status: "UNKNOWN", notes: `Erro ao executar auditoria: ${errMsg}` },
          lambdas: { status: "UNKNOWN", notes: "O backend pode estar indisponivel ou em cold start." },
          ev: { status: "UNKNOWN", notes: "Use 'Auditar Rodada' para auditoria instantanea sem depender do backend." },
        },
        audit_type: "error",
      } as AuditResult);
      // Scroll automático para o resultado mesmo em caso de erro
      setTimeout(() => {
        if (auditResultRef.current && rightPanelRef.current) {
          rightPanelRef.current.scrollTo({
            top: auditResultRef.current.offsetTop - rightPanelRef.current.offsetTop,
            behavior: "smooth",
          });
        }
      }, 150);
    } finally {
      setAuditLoading(false);
    }
  }, [selectedMatch, aiAnalysis, aiAnalysisMatchId, auditLoading]);

  const handleApplyCorrection = useCallback(async (correction: AuditCorrection) => {
    if (!selectedMatch) return;
    try {
      const result = await applyAuditCorrection(selectedMatch.id, {
        correction_type: correction.type,
        parameter_name: correction.parameter,
        old_value: correction.current_value,
        new_value: correction.suggested_value,
        reason: correction.reason,
        audit_confidence: correction.confidence,
      });
      if (result?.status === "success") {
        alert(`Correcao aplicada: ${correction.parameter}`);
      } else {
        alert("Falha ao aplicar correcao.");
      }
    } catch (err) {
      console.error("Apply correction error:", err);
      alert("Erro ao aplicar correcao.");
    }
  }, [selectedMatch]);

  // Batch audit handlers
  const finishedCount = useMemo(() => {
    return allMatches.filter((m) => m.status === "finished").length;
  }, [allMatches]);

  const handleReliabilityClick = useCallback(async () => {
    if (reliabilityOpen) { setReliabilityOpen(false); return; }
    setReliabilityOpen(true);
    setReliabilityLoading(true);
    try {
      const res = await fetch("/api/admin/reliability");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReliabilityData(await res.json());
    } catch {
      setReliabilityData(null);
    } finally {
      setReliabilityLoading(false);
    }
  }, [reliabilityOpen]);

  const handleBatchAudit = useCallback(async () => {
    if (batchAuditLoading) return;
    setBatchAuditLoading(true);
    try {
      // 1. Local deterministic audit — instant, no network
      const result = runLocalAudit(allMatches);
      setBatchAuditResult(result);
      setBatchAuditOpen(true);

      // 2. Fetch Mistral evaluation in background (lightweight call ~3-5s)
      if (result.audited_matches > 0) {
        fetchMistralEvaluation(result).then((evaluation) => {
          if (evaluation) {
            setBatchAuditResult((prev) => {
              if (!prev) return prev;
              const updates: Partial<typeof prev> = { model_evaluation: evaluation };
              // Store Mistral's recommendation separately for side-by-side comparison.
              // Local model_update_recommendation (deterministic) remains the primary.
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const mistralRec = (evaluation as any).model_update_recommendation;
              if (mistralRec && typeof mistralRec === "object") {
                updates.mistral_recommendation = mistralRec as typeof prev.model_update_recommendation;
              }
              return { ...prev, ...updates };
            });
          }
        });
      }
    } catch (err) {
      console.error("Batch audit error:", err);
      setBatchAuditResult({
        status: "error",
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
        message: "Erro ao executar auditoria em lote. Tente novamente.",
      });
      setBatchAuditOpen(true);
    } finally {
      setBatchAuditLoading(false);
    }
  }, [batchAuditLoading, allMatches]);

  const handleBatchApplyCorrections = useCallback(async (corrections: BatchAuditCorrection[]) => {
    try {
      const result = await applyBatchCorrections(corrections);
      if (result?.status === "success" || result?.status === "partial") {
        alert(`${result.applied} correcoes aplicadas com sucesso.`);
      } else {
        alert("Falha ao aplicar correcoes.");
      }
    } catch (err) {
      console.error("Batch apply corrections error:", err);
      alert("Erro ao aplicar correcoes em lote.");
    }
  }, []);

  const handleRetry = useCallback(async () => {
    setLoading(true);
    livePollAfterBatchRef.current = false;
    setHasError(false);
    setErrorMessage(null);
    setErrorCode(null);
    setDataSource(null);
    setAllMatches([]);
    const allLeagueIds = AVAILABLE_LEAGUES.map((l) => l.id).join(",");

    const onBatchReady = (batch: MatchesResponse) => {
      const raw = batch.matches ?? [];
      if (raw.length === 0) return;
      const normalized = raw.map((item: any, idx: number) => {
        const lid = item.leagueId ?? item.league ?? "unknown";
        return normalizeMatch(item, lid, idx);
      });
      setAllMatches((prev) => deduplicateMatches([...prev, ...normalized]));
      setDataSource((prev) => batch._dataSource ?? prev);
      setIsMockData((m) => m || !!batch._isMockData);
      setSelectedMatchId((prev) => prev ?? normalized[0].id);
      if (!livePollAfterBatchRef.current) {
        livePollAfterBatchRef.current = true;
        queueMicrotask(() => fetchLiveScores());
      }
    };

    try {
      let res: MatchesResponse = await getMatchesByLeague(allLeagueIds, dateMode, onBatchReady);
      let raw = res?.matches ?? [];

      // Auto-retry once on transient errors (Lambda cold start, network blip, etc.)
      const retryKinds = new Set(["TIMEOUT", "HTTP_ERROR", "CONNECTION_ERROR", "NETWORK_ERROR", "UNKNOWN"]);
      if (raw.length === 0 && res._error && retryKinds.has(res._error.kind)) {
        console.log(`[dashboard:retry] ${res._error.kind} on first attempt, retrying...`);
        res = await getMatchesByLeague(allLeagueIds, dateMode, onBatchReady);
        raw = res?.matches ?? [];
      }

      setDataSource(res._dataSource ?? null);
      setIsMockData(res._isMockData ?? false);

      if (res._error) {
        setHasError(true);
        setErrorMessage(res._error.message);
        setErrorCode(res._error.kind ?? null);
      }

      // Auto-fallback: if today returns empty (and no error), try week
      if (raw.length === 0 && dateMode === "today" && !res._error) {
        setAllMatches([]);
        livePollAfterBatchRef.current = false;
        res = await getMatchesByLeague(allLeagueIds, "week", onBatchReady);
        raw = res?.matches ?? [];
        if (raw.length > 0) {
          setDateMode("week");
          setDataSource(res._dataSource ?? null);
          setIsMockData(res._isMockData ?? false);
        }
        if (res._error) {
          setHasError(true);
          setErrorMessage(res._error.message);
          setErrorCode(res._error.kind ?? null);
        }
      }

      const normalized = raw.map((item: any, idx: number) => {
        const lid = item.leagueId ?? item.league ?? AVAILABLE_LEAGUES[0]?.id ?? "unknown";
        return normalizeMatch(item, lid, idx);
      });
      // Deduplicate: same match from different sources (e.g. "Wolves" vs "Wolverhampton Wanderers")
      setAllMatches(deduplicateMatches(normalized));
      if (normalized.length > 0) setSelectedMatchId(normalized[0].id);
    } catch {
      // Don't clear matches on error — preserve what we have
      setHasError(true);
      setErrorMessage("Erro inesperado ao carregar jogos. Tente novamente.");
      setErrorCode("CLIENT_EXCEPTION");
    } finally {
      setLoading(false);
    }
  }, [dateMode]);

  const handleEmptyDateChange = useCallback((direction: "prev" | "next") => {
    setDateMode((prev) => {
      if (direction === "prev") {
        return prev === "week" ? "tomorrow" : prev === "tomorrow" ? "today" : "today";
      }
      return prev === "today" ? "tomorrow" : prev === "tomorrow" ? "week" : "week";
    });
  }, []);

  /** Determine which empty state variant to show */
  const emptyVariant = useMemo<EmptyStateVariant | null>(() => {
    /* #119a: allow partial list while still loading more batches */
    if (loading && allMatches.length === 0) return null;
    if (hasError && dataSource === "mock-dev") return "mock-dev";
    if (hasError) return dataSource === "client-error" ? "client-error" : "backend-offline";
    if (allMatches.length === 0 && !hasError) return "no-games-date";
    return null;
  }, [loading, hasError, dataSource, allMatches.length]);

  const leagueGroups = useMemo<LeagueGroup[]>(() => {
    const byLeague = new Map<string, Match[]>();
    for (const m of displayMatches) {
      const list = byLeague.get(m.leagueId) ?? [];
      list.push(m);
      byLeague.set(m.leagueId, list);
    }
    const getBrazilPriority = (leagueId: string) => {
      if (leagueId === "brazil-serie-a") return 0;
      if (leagueId === "brazil-serie-b") return 1;
      return 2;
    };
    const leagueOrder = AVAILABLE_LEAGUES.reduce((map, l, i) => { map[l.id] = i; return map; }, {} as Record<string, number>);
    const sortedEntries = Array.from(byLeague.entries()).sort(([a], [b]) => {
      const pA = getBrazilPriority(a);
      const pB = getBrazilPriority(b);
      if (pA !== pB) return pA - pB;
      const nameA = AVAILABLE_LEAGUES.find((l) => l.id === a)?.name ?? a;
      const nameB = AVAILABLE_LEAGUES.find((l) => l.id === b)?.name ?? b;
      return nameA.localeCompare(nameB);
    });
    return sortedEntries.map(([leagueId, matches]) => {
      const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
      const dir = sortOrder === "asc" ? 1 : -1;
      const sorted = [...matches].sort((a, b) => {
        const da = new Date(a.datetime).getTime();
        const db = new Date(b.datetime).getTime();
        return (da - db) * dir;
      });
      return {
        leagueId,
        leagueName: league?.name ?? leagueId,
        countryFlag: league?.countryFlag ?? "🏆",
        country: league?.country ?? "",
        matches: sorted,
        collapsed: collapsedLeagues.has(leagueId),
      };
    });
  }, [displayMatches, collapsedLeagues, sortOrder]);

  const leagueIdForCapture = useMemo(() => {
    if (navView !== "matches") return null;
    const selectedLeagueId = selectedMatch?.leagueId;
    if (selectedLeagueId) {
      const selectedGroup = leagueGroups.find(
        (group) => group.leagueId === selectedLeagueId && !group.collapsed,
      );
      if (selectedGroup) return selectedLeagueId;
    }
    return leagueGroups.find((group) => !group.collapsed)?.leagueId ?? null;
  }, [leagueGroups, navView, selectedMatch?.leagueId]);

  const oddsTabs: { key: OddsTab; label: string }[] = [
    { key: "1x2", label: "1X2" },
    { key: "double-chance", label: "Dupla Chance" },
    { key: "btts", label: "BTTS" },
    { key: "goals", label: "Gols" },
    { key: "cards", label: "Cartoes" },
    { key: "corners", label: "Escanteios" },
  ];

  function setShareMessage(message: string, tone: ShareFeedbackTone) {
    setShareFeedback(message);
    setShareFeedbackTone(tone);
  }

  function downloadBlob(blob: Blob, filename: string) {
    const blobUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(blobUrl);
  }

  async function copyBlobToClipboard(blob: Blob): Promise<boolean> {
    if (typeof navigator === "undefined" || !navigator.clipboard || typeof ClipboardItem === "undefined") {
      return false;
    }
    try {
      const item = new ClipboardItem({ [blob.type]: blob });
      await navigator.clipboard.write([item]);
      return true;
    } catch {
      return false;
    }
  }

  async function captureLeftPanelBlob() {
    const panel = capturePanelRef.current;
    if (!panel) {
      throw new Error("Painel de captura nao encontrado.");
    }
    const target = navView === "matches"
      ? panel.querySelector<HTMLElement>("[data-capture-target='true']")
      : panel;
    if (!target) {
      throw new Error("Abra uma liga para capturar a imagem.");
    }
    const previousShareMode = target.getAttribute("data-share-mode");
    target.setAttribute("data-share-mode", "true");
    const controls = Array.from(target.querySelectorAll<HTMLElement>("[data-share-control='true']"));
    const prevVisibility = controls.map((el) => el.style.visibility);
    controls.forEach((el) => {
      el.style.visibility = "hidden";
    });
    try {
      const html2canvas = (await import("html2canvas")).default;
      const canvas = await html2canvas(target, {
        backgroundColor: "#0d0d0d",
        scale: Math.min(window.devicePixelRatio || 1, 2),
        useCORS: true,
        logging: false,
      });
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((result) => {
          if (result) resolve(result);
          else reject(new Error("Falha ao gerar imagem da captura."));
        }, "image/png");
      });
      return blob;
    } finally {
      controls.forEach((el, index) => {
        el.style.visibility = prevVisibility[index] ?? "";
      });
      if (previousShareMode == null) {
        target.removeAttribute("data-share-mode");
      } else {
        target.setAttribute("data-share-mode", previousShareMode);
      }
    }
  }

  async function handleCopyScreen() {
    setShareBusy("copy");
    setShareFeedback("");
    try {
      const blob = await captureLeftPanelBlob();
      const copied = await copyBlobToClipboard(blob);
      if (copied) {
        setShareMessage("Tela copiada. Agora voce pode colar no WhatsApp (Ctrl+V).", "success");
        return;
      }
      const filename = buildScreenshotName();
      downloadBlob(blob, filename);
      setShareMessage("Clipboard indisponivel. Imagem baixada automaticamente.", "info");
    } catch (error: any) {
      setShareMessage(error?.message || "Nao foi possivel capturar a tela agora.", "error");
    } finally {
      setShareBusy(null);
    }
  }

  async function handleShareWhatsApp() {
    setShareBusy("whatsapp");
    setShareFeedback("");
    try {
      const blob = await captureLeftPanelBlob();
      const file = new File([blob], buildScreenshotName(), { type: "image/png" });
      if (
        typeof navigator !== "undefined"
        && "share" in navigator
        && "canShare" in navigator
        && navigator.canShare({ files: [file] })
      ) {
        await navigator.share({
          title: "SportsBankZU Pro",
          text: SHARE_TEXT,
          files: [file],
        });
        setShareMessage("Compartilhamento concluido pelo menu do seu dispositivo.", "success");
        return;
      }
      const copied = await copyBlobToClipboard(blob);
      const prefilled = copied
        ? `${SHARE_TEXT}\n\nImagem copiada. Abra o chat no WhatsApp e cole (Ctrl+V).`
        : `${SHARE_TEXT}\n\nArquivo da imagem foi baixado para envio manual.`;
      window.open(`https://wa.me/?text=${encodeURIComponent(prefilled)}`, "_blank", "noopener,noreferrer");
      if (!copied) {
        downloadBlob(blob, buildScreenshotName());
      }
      setShareMessage(
        copied
          ? "WhatsApp aberto. Cole a imagem no chat para enviar."
          : "WhatsApp aberto e imagem baixada para anexo manual.",
        "info",
      );
    } catch (error: any) {
      if (error?.name === "AbortError") {
        setShareMessage("Compartilhamento cancelado.", "info");
      } else {
        setShareMessage(error?.message || "Nao foi possivel compartilhar no WhatsApp agora.", "error");
      }
    } finally {
      setShareBusy(null);
    }
  }

  return (
    <div className="st-app">
      {/* TOP NAV */}
      <nav className="st-nav">
        <div className="st-nav__logo">
          sports<span>bankzu</span>
        </div>
        <div className="st-nav__links">
          <button className={`st-nav__link ${navView === "campeonatos" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "campeonatos" ? "matches" : "campeonatos")}>
            <Trophy size={14} />
            Campeonatos
          </button>
          {canSeeFerramentas && (
          <button className={`st-nav__link ${navView === "ferramentas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "ferramentas" ? "matches" : "ferramentas")}>
            <Wrench size={14} />
            Ferramentas
          </button>
          )}
          <button className={`st-nav__link ${navView === "recomendadas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "recomendadas" ? "matches" : "recomendadas")}>
            <Sparkles size={14} />
            Destaques do Dia
          </button>
          <button className={`st-nav__link ${navView === "duplas" ? "st-nav__link--active" : ""}`} onClick={() => { const next = navView === "duplas" ? "matches" : "duplas"; setNavView(next); if (next === "duplas" && !combinadas && !combinadasLoading) fetchCombinadas(combinadasMinStatus); }}>
            <Layers size={14} />
            Duplas
          </button>
        </div>
        <div className="st-nav__right">
          <span className="st-badge-pro">{appVersion}</span>
          <button
            type="button"
            className="st-nav__link"
            onClick={handleTopbarShareWhatsApp}
            disabled={shareLoading}
            title="Copiar tela e compartilhar via WhatsApp"
            aria-label="Compartilhar via WhatsApp"
          >
            {shareLoading ? <Loader2 size={16} className="animate-spin" /> : <Share2 size={16} />}
            <span className="st-nav__share-label">Compartilhar</span>
          </button>
          <button className="st-nav__search">
            <Search size={14} />
            Buscar
            <kbd>Ctrl+K</kbd>
          </button>
          <button className="st-nav__link" aria-label="Notificacoes">
            <Bell size={16} />
          </button>
        </div>
      </nav>

      <div className="st-main" ref={mainContentRef}>
        {/* LEFT PANEL - Em mobile, esconder quando um jogo está selecionado */}
        {(!isMobile || !selectedMatchId) && (
          <div className="st-panel-left" ref={capturePanelRef}>

            {/* ── CAMPEONATOS VIEW ── */}
            {navView === "campeonatos" && (
              <div className="st-view-panel">
                <div className="st-view-header">
                  <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                  <h2 className="st-view-title"><Trophy size={16} /> Campeonatos</h2>
                </div>
                <div className="st-view-content">
                  {AVAILABLE_LEAGUES.map((league) => {
                    const matchCount = allMatches.filter((m) => m.leagueId === league.id).length;
                    return (
                      <div
                        key={league.id}
                        className="st-league-card"
                        onClick={() => { setSelectedLeague(league.id); setNavView("matches"); }}
                      >
                        <span className="st-league-card__flag">{league.countryFlag}</span>
                        <div className="st-league-card__info">
                          <span className="st-league-card__name">{league.name}</span>
                          <span className="st-league-card__country">{league.country} &middot; {league.season}</span>
                        </div>
                        <div className="st-league-card__right">
                          {matchCount > 0 && (
                            <span className="st-league-card__badge">{matchCount} jogos</span>
                          )}
                          <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── FERRAMENTAS VIEW ── */}
            {navView === "ferramentas" && (
              <div className="st-view-panel">
                <div className="st-view-header">
                  <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                  <h2 className="st-view-title"><Wrench size={16} /> Ferramentas</h2>
                </div>
                <div className="st-view-content">
                  <a href="/ai-audit" className="st-tool-card">
                    <div className="st-tool-card__icon" style={{ background: "rgba(0,255,136,0.1)" }}><Brain size={20} style={{ color: "#00ff88" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Auditoria AI (Mistral)</span>
                      <span className="st-tool-card__desc">Analise inteligente com recomendacoes de apostas</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </a>
                  <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("goals"); }}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(255,187,51,0.1)" }}><BarChart3 size={20} style={{ color: "#ffbb33" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Comparativo de Gols</span>
                      <span className="st-tool-card__desc">Lambda, xG, Over/Under e medias por liga</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                  <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("btts"); }}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(157,80,255,0.1)" }}><Target size={20} style={{ color: "#9d50ff" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Analise BTTS</span>
                      <span className="st-tool-card__desc">Both Teams To Score — probabilidades e odds</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                  <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("corners"); }}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(0,187,255,0.1)" }}><Zap size={20} style={{ color: "#00bbff" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Escanteios & Cartoes</span>
                      <span className="st-tool-card__desc">Medias de escanteios e cartoes por equipe</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                  <div className="st-tool-card" onClick={() => setNavView("recomendadas")}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(255,68,68,0.1)" }}><Sparkles size={20} style={{ color: "#ff4444" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Recomendadas do Dia</span>
                      <span className="st-tool-card__desc">Jogos com maior confianca da analise AI</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                  <div className="st-tool-card" onClick={() => { setNavView("duplas"); if (!combinadas && !combinadasLoading) fetchCombinadas(combinadasMinStatus); }}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(157,80,255,0.1)" }}><Layers size={20} style={{ color: "#c4a0ff" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Duplas (Intra/Inter)</span>
                      <span className="st-tool-card__desc">Combinadas intra-jogo e inter-jogo com alta probabilidade</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                  <a href="/bankroll" className="st-tool-card">
                    <div className="st-tool-card__icon" style={{ background: "rgba(34,197,94,0.1)" }}><Calculator size={20} style={{ color: "#22c55e" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Gestao de Banca</span>
                      <span className="st-tool-card__desc">Distribua sua banca com criterio de Kelly entre simples e duplas</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </a>
                  <div className="st-tool-card" onClick={() => setNavView("glossario")}>
                    <div className="st-tool-card__icon" style={{ background: "rgba(74,158,255,0.1)" }}><Search size={20} style={{ color: "#4a9eff" }} /></div>
                    <div className="st-tool-card__info">
                      <span className="st-tool-card__name">Glossario</span>
                      <span className="st-tool-card__desc">Termos, metricas e classificacoes explicados</span>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                  </div>
                </div>
              </div>
            )}

            {/* ── GLOSSARIO VIEW ── */}
            {navView === "glossario" && (
              <div className="st-view-panel">
                <div className="st-view-header">
                  <button className="st-view-back" onClick={() => setNavView("ferramentas")}><ArrowLeft size={14} /> Voltar</button>
                  <h2 className="st-view-title"><Search size={16} /> Glossario</h2>
                </div>
                <div className="st-view-content">
                  <Glossary />
                </div>
              </div>
            )}

            {/* ── RECOMENDADAS VIEW (#117) ── */}
            {navView === "recomendadas" && (
              <DestaquesDoDia
                matches={allMatches}
                bankroll={bankroll}
                onBankrollChange={(v) => {
                  setBankroll(v);
                  if (typeof window !== "undefined") localStorage.setItem("sportsbankzu-bankroll", v.toString());
                }}
                onBack={() => setNavView("matches")}
                onSelectMatch={(id) => { setSelectedMatchId(id); setNavView("matches"); }}
              />
            )}

            {/* ── DUPLAS VIEW ── */}
            {navView === "duplas" && (
              <div className="st-view-panel">
                <div className="st-view-header">
                  <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                  <h2 className="st-view-title"><Layers size={16} /> Duplas</h2>
                </div>
                <div className="st-view-subtitle">Combinadas intra-jogo e inter-jogo com maior probabilidade</div>

                {/* Sub-tabs + filtro */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 14px 4px" }}>
                  <div style={{ display: "flex", gap: 4 }}>
                    {(["intra", "inter"] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setCombindasSubTab(tab)}
                        style={{
                          padding: "4px 12px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: "0.72rem", fontWeight: 700,
                          background: combinadasSubTab === tab ? "rgba(157,80,255,0.18)" : "rgba(255,255,255,0.05)",
                          color: combinadasSubTab === tab ? "#c4a0ff" : "#777"
                        }}
                      >
                        {tab === "intra" ? "Intra-jogo" : "Inter-jogo"}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                    <span style={{ fontSize: "0.65rem", color: "#555" }}>Mín:</span>
                    {(["NEUTRO", "SAFE"] as const).map((s) => (
                      <button
                        key={s}
                        onClick={() => { setCombindasMinStatus(s); fetchCombinadas(s); }}
                        style={{
                          padding: "3px 9px", borderRadius: 5, border: "none", cursor: "pointer", fontSize: "0.65rem", fontWeight: 700,
                          background: combinadasMinStatus === s ? (s === "SAFE" ? "rgba(0,223,130,0.15)" : "rgba(255,136,0,0.12)") : "rgba(255,255,255,0.05)",
                          color: combinadasMinStatus === s ? (s === "SAFE" ? "#00df82" : "#ffaa44") : "#666"
                        }}
                      >
                        {s}
                      </button>
                    ))}
                    <button
                      onClick={() => fetchCombinadas(combinadasMinStatus)}
                      disabled={combinadasLoading}
                      style={{ marginLeft: 4, padding: "4px 8px", borderRadius: 6, border: "none", cursor: "pointer", background: "rgba(255,255,255,0.06)", color: "#888" }}
                      title="Recarregar"
                    >
                      <RefreshCw size={11} style={{ display: "block", animation: combinadasLoading ? "spin 1s linear infinite" : "none" }} />
                    </button>
                  </div>
                </div>

                <div className="st-view-content">
                  {combinadasLoading && (
                    <div style={{ textAlign: "center", padding: "40px 0", color: "#555" }}>
                      <Loader2 size={24} style={{ display: "inline-block", animation: "spin 1s linear infinite", marginBottom: 8 }} />
                      <div style={{ fontSize: "0.78rem" }}>Calculando combinadas...</div>
                    </div>
                  )}
                  {!combinadasLoading && combinadasError && (
                    <div style={{ textAlign: "center", padding: "32px 14px", color: "#ff5555", fontSize: "0.8rem" }}>
                      <div style={{ marginBottom: 8 }}>Erro ao carregar duplas.</div>
                      <div style={{ color: "#555", fontSize: "0.72rem" }}>{combinadasError}</div>
                      <button onClick={() => fetchCombinadas(combinadasMinStatus)} style={{ marginTop: 12, padding: "6px 14px", borderRadius: 6, border: "1px solid rgba(255,85,85,0.3)", background: "transparent", color: "#ff5555", cursor: "pointer", fontSize: "0.72rem" }}>
                        Tentar novamente
                      </button>
                    </div>
                  )}
                  {!combinadasLoading && !combinadasError && !combinadas && (
                    <div style={{ textAlign: "center", padding: "40px 14px", color: "#555", fontSize: "0.8rem" }}>
                      Clique em Duplas na barra de navegação para carregar as combinadas do dia.
                    </div>
                  )}
                  {!combinadasLoading && !combinadasError && combinadas && (() => {
                    const list = combinadasSubTab === "intra" ? (combinadas.intra ?? []) : (combinadas.inter ?? []);
                    const total = combinadasSubTab === "intra" ? combinadas.total_intra : combinadas.total_inter;
                    if (list.length === 0) {
                      return (
                        <div style={{ textAlign: "center", padding: "40px 14px", color: "#555", fontSize: "0.8rem" }}>
                          <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>{combinadasSubTab === "intra" ? "🔗" : "⛓️"}</div>
                          Nenhuma dupla {combinadasSubTab === "intra" ? "intra-jogo" : "inter-jogo"} encontrada com status mínimo {combinadasMinStatus}.
                        </div>
                      );
                    }
                    return (
                      <>
                        <div style={{ fontSize: "0.65rem", color: "#555", padding: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          {total} {combinadasSubTab === "intra" ? "combinadas intra-jogo" : "combinadas inter-jogo"}
                        </div>
                        {list.map((c, i) => <CombinadaCardDash key={i} c={c} />)}
                      </>
                    );
                  })()}
                </div>
              </div>
            )}

            {/* ── MATCHES VIEW (default) ── */}
            {navView === "matches" && <>
              {/* Sticky header: filter bar + odds tabs */}
              <div className="st-sticky-header">
                {/* Filter bar */}
                <div className="st-filters">
                  <div className="st-date-nav">
                    <button type="button" className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "week" ? "tomorrow" : prev === "tomorrow" ? "today" : "today")}><ChevronLeft size={14} /></button>
                    <span className="st-date-label">{dateLabel}</span>
                    <button type="button" className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "today" ? "tomorrow" : prev === "tomorrow" ? "week" : "week")}><ChevronRight size={14} /></button>
                  </div>
                  {hasLiveMatches && (
                    <span className="st-live-indicator" title={liveLastUpdated ? `Atualizado: ${liveLastUpdated.toLocaleTimeString("pt-BR")}` : "Polling ativo"}>
                      <span className="st-live-dot" />
                      <span className="st-live-text">LIVE</span>
                    </span>
                  )}
                  <button
                    type="button"
                    className={`st-filter-btn ${shareBusy === "copy" ? "st-filter-btn--active" : ""}`}
                    onClick={handleCopyScreen}
                    data-share-control="true"
                    disabled={shareBusy !== null}
                  >
                    {shareBusy === "copy" ? <Loader2 size={12} className="st-spin-icon" /> : <Copy size={12} />}
                    Copiar tela
                  </button>
                  <button
                    type="button"
                    className={`st-filter-btn ${shareBusy === "whatsapp" ? "st-filter-btn--active" : ""}`}
                    onClick={handleShareWhatsApp}
                    data-share-control="true"
                    disabled={shareBusy !== null}
                  >
                    {shareBusy === "whatsapp" ? <Loader2 size={12} className="st-spin-icon" /> : <MessageCircle size={12} />}
                    WhatsApp
                  </button>
                  {canSeeAudit && (
                  <button
                    type="button"
                    className={`st-filter-btn st-filter-btn--audit ${batchAuditLoading ? "st-filter-btn--active" : ""}`}
                    onClick={handleBatchAudit}
                    disabled={batchAuditLoading || finishedCount === 0}
                    title={finishedCount === 0 ? "Nenhum jogo finalizado para auditar" : `Auditar ${finishedCount} jogos finalizados`}
                  >
                    {batchAuditLoading ? <Loader2 size={12} className="st-spin-icon" /> : <ShieldCheck size={12} />}
                    {batchAuditLoading ? "Auditando..." : "Auditar Rodada"}
                  </button>
                  )}
                  {canSeeConfiabilidade && (
                  <button
                    type="button"
                    className={`st-filter-btn ${reliabilityOpen ? "st-filter-btn--active" : ""}`}
                    onClick={handleReliabilityClick}
                    title="Metricas de confiabilidade do sistema (Princeton framework)"
                    style={reliabilityOpen ? { borderColor: "rgba(96,165,250,0.5)", color: "#60a5fa" } : undefined}
                  >
                    {reliabilityLoading ? <Loader2 size={12} className="st-spin-icon" /> : <ShieldCheck size={12} />}
                    Confiabilidade
                  </button>
                  )}
                  <button
                    type="button"
                    className={`st-filter-btn st-filter-btn--mobile-hidden ${sortOrder === "desc" ? "st-filter-btn--active" : ""}`}
                    onClick={() => setSortOrder((v) => v === "asc" ? "desc" : "asc")}
                    title={sortOrder === "asc" ? "Ordenar: mais cedo primeiro" : "Ordenar: mais tarde primeiro"}
                  >
                    <SlidersHorizontal size={12} /> {sortOrder === "asc" ? "Mais cedo" : "Mais tarde"}
                  </button>
                  <button
                    type="button"
                    className={`st-filter-btn st-filter-btn--mobile-hidden ${showFavoritesOnly ? "st-filter-btn--active" : ""}`}
                    onClick={() => setShowFavoritesOnly((v) => !v)}
                  >
                    <Heart size={12} fill={showFavoritesOnly ? "currentColor" : "none"} /> Favoritos
                  </button>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as "all" | "live" | "finished" | "scheduled")}
                    className={`st-filter-btn st-filter-btn--mobile-hidden ${statusFilter !== "all" ? "st-filter-btn--active" : ""}`}
                    style={{ appearance: "none", WebkitAppearance: "none", background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, padding: "0 28px 0 12px", cursor: "pointer", color: "#e0e0e0", backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%23888' d='M0 0l5 6 5-6z'/%3E%3C/svg%3E\")", backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center" }}
                  >
                    <option value="all" style={{ background: "#1a1a2e", color: "#e0e0e0" }}>Todos os Jogos</option>
                    <option value="live" style={{ background: "#1a1a2e", color: "#e0e0e0" }}>Ao Vivo</option>
                    <option value="finished" style={{ background: "#1a1a2e", color: "#e0e0e0" }}>Finalizados</option>
                    <option value="scheduled" style={{ background: "#1a1a2e", color: "#e0e0e0" }}>Não Iniciados</option>
                  </select>
                </div>
                {shareFeedback && (
                  <div
                    className={`st-share-feedback st-share-feedback--${shareFeedbackTone}`}
                    role="status"
                    data-share-control="true"
                  >
                    {shareFeedback}
                  </div>
                )}

                <AuditBanner />

                {/* Odds tabs */}
                <div className="st-odds-tabs">
                  <span style={{ fontSize: "0.7rem", color: "var(--st-text-muted)", padding: "10px 8px 10px 0", whiteSpace: "nowrap" }}>COTACOES</span>
                  {oddsTabs.map((t) => (
                    <button
                      key={t.key}
                      className={`st-odds-tab ${oddsTab === t.key ? "st-odds-tab--active" : ""}`}
                      onClick={() => setOddsTab(t.key)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* #119a — partial data visible while more batches load */}
              {loading && allMatches.length > 0 && (
                <div
                  role="status"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "6px 14px",
                    fontSize: "0.68rem",
                    color: "#88aaff",
                    background: "rgba(96,165,250,0.08)",
                    borderBottom: "1px solid rgba(96,165,250,0.15)",
                  }}
                >
                  <Loader2 size={14} className="st-spin-icon" aria-hidden />
                  Carregando mais ligas...
                </div>
              )}

              {selectedLeague && (
                <div style={{ padding: "8px 12px" }}>
                  <button
                    onClick={() => setSelectedLeague(null)}
                    style={{
                      background: "rgba(255,165,0,0.15)",
                      border: "1px solid rgba(255,165,0,0.3)",
                      borderRadius: 6,
                      padding: "4px 12px",
                      color: "#ffaa33",
                      fontSize: "0.8rem",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    ✕ {AVAILABLE_LEAGUES.find((l) => l.id === selectedLeague)?.name ?? selectedLeague} — Ver todas as ligas
                  </button>
                </div>
              )}

              {/* Mock data dev banner */}
              {!loading && isMockData && allMatches.length > 0 && (
                <MockDataBanner />
              )}

              {/* #119a — initial fetch before first batch arrives */}
              {loading && allMatches.length === 0 && !hasError && (
                <div style={{ textAlign: "center", padding: "48px 24px", color: "#666" }}>
                  <Loader2 size={28} className="st-spin-icon" style={{ display: "inline-block", marginBottom: 10 }} />
                  <div style={{ fontSize: "0.78rem" }}>Carregando jogos...</div>
                </div>
              )}

              {/* Empty state / Error state */}
              {!loading && leagueGroups.length === 0 && emptyVariant && (
                <EmptyState
                  variant={emptyVariant}
                  errorMessage={errorMessage ?? undefined}
                  errorCode={errorCode ?? undefined}
                  dateLabel={dateLabel}
                  onRetry={handleRetry}
                  onChangeDate={emptyVariant === "no-games-date" ? handleEmptyDateChange : undefined}
                />
              )}

              {leagueGroups.length > 0 && <ConfidenceLegend />}

              {leagueGroups.length > 0 && leagueGroups.map((group, groupIdx) => {
                const isCaptureTarget = group.leagueId === leagueIdForCapture;
                const isBrazilian = group.leagueId === "brazil-serie-a" || group.leagueId === "brazil-serie-b";
                const prevGroup = groupIdx > 0 ? leagueGroups[groupIdx - 1] : null;
                const prevIsBrazilian = prevGroup ? (prevGroup.leagueId === "brazil-serie-a" || prevGroup.leagueId === "brazil-serie-b") : false;
                const showSeparator = !isBrazilian && prevIsBrazilian;
                return (
                  <div key={group.leagueId}>
                    {showSeparator && (
                      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px 6px", opacity: 0.5 }}>
                        <div style={{ flex: 1, height: 1, background: "linear-gradient(to right, rgba(255,165,0,0.4), transparent)" }} />
                        <span style={{ fontSize: "0.65rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "#888", whiteSpace: "nowrap" }}>Ligas Internacionais</span>
                        <div style={{ flex: 1, height: 1, background: "linear-gradient(to left, rgba(255,165,0,0.4), transparent)" }} />
                      </div>
                    )}
                  <div
                    className="st-league-group"
                    data-capture-target={isCaptureTarget ? "true" : "false"}
                  >
                    <div className="st-league-header" onClick={() => toggleLeague(group.leagueId)}>
                      <span className="st-league-flag">{group.countryFlag}</span>
                      <span className="st-league-name">
                        {group.country ? `${group.country} - ` : ""}{group.leagueName}
                        {leagueClassifications[group.leagueId] && (
                          <LeagueConfidenceBadge
                            classification={leagueClassifications[group.leagueId].classification}
                            accuracy={leagueClassifications[group.leagueId].accuracy}
                            brier={leagueClassifications[group.leagueId].brier}
                            nSamples={leagueClassifications[group.leagueId].n_samples}
                          />
                        )}
                        <span className="st-league-count"> ({group.matches.length})</span>
                        {group.matches.some((m) => m.status === "live") && (
                          <span className="st-league-live-badge">
                            <span className="st-live-dot" /> {group.matches.filter((m) => m.status === "live").length} AO VIVO
                          </span>
                        )}
                      </span>
                      <div className="st-league-actions" data-share-hide="true">
                        <button className="st-league-action-btn" onClick={(e) => { e.stopPropagation(); }}>
                          <Star size={14} />
                        </button>
                        <button className="st-league-action-btn" onClick={(e) => { e.stopPropagation(); }}>
                          <SlidersHorizontal size={14} />
                        </button>
                        {group.collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                      </div>
                    </div>

                    {!group.collapsed && group.matches.map((match) => {
                      const h = safeOdd(match.odds?.home);
                      const d = safeOdd(match.odds?.draw);
                      const a = safeOdd(match.odds?.away);
                      const hlSet = getHighlightedOddPositions(match.predictions, oddsTab);
                      const isSelected = match.id === selectedMatchId;
                      const liveInfo = computeLiveInfo(match);
                      const minsToKick = match.status === "scheduled" ? minutesToKickoff(match.datetime) : null;

                      // Safety net: infer live/finished when kickoff passed but overlay didn't update
                      let displayStatus = match.status;
                      let inferredLiveInfo: { period: string; minute: number | null } | null = null;
                      if (match.status === "scheduled" && minsToKick === null) {
                        try {
                          const elapsed = Math.floor((Date.now() - new Date(match.datetime).getTime()) / 60_000);
                          if (elapsed >= 0 && elapsed < 120) {
                            displayStatus = "live";
                            if (elapsed <= 47) inferredLiveInfo = { period: "1T", minute: Math.min(elapsed, 45) };
                            else if (elapsed <= 62) inferredLiveInfo = { period: "HT", minute: null };
                            else inferredLiveInfo = { period: "2T", minute: Math.min(elapsed - 15, 90) };
                          } else if (elapsed >= 120) {
                            displayStatus = "finished";
                          }
                        } catch { /* invalid datetime — keep scheduled */ }
                      }
                      // Normalize: "live" without liveInfo means match hasn't started
                      if (match.status === "live" && !liveInfo) {
                        const mk = minutesToKickoff(match.datetime);
                        if (mk !== null && mk > 0) {
                          displayStatus = "scheduled";
                        }
                      }
                      const effectiveLiveInfo = liveInfo ?? inferredLiveInfo;

                      return (
                        <div
                          key={match.id}
                          className={`st-match-row ${isSelected ? "st-match-row--selected" : ""} ${displayStatus === "live" ? "st-match-row--live" : ""}`}
                          onClick={() => setSelectedMatchId(match.id)}
                        >
                          <div className="st-match-row__status">
                            {displayStatus === "live" && effectiveLiveInfo ? (
                              <>
                                <div className="st-match-row__status-tag st-match-row__status-tag--live">VIVO</div>
                                <div className="st-match-row__status-period">{effectiveLiveInfo.period}</div>
                                {effectiveLiveInfo.minute != null && effectiveLiveInfo.period !== "HT" && (
                                  <div className="st-match-row__status-minute">{effectiveLiveInfo.minute}&apos;</div>
                                )}
                              </>
                            ) : displayStatus === "finished" ? (
                              <div className="st-match-row__status-tag st-match-row__status-tag--ft">FT</div>
                            ) : displayStatus === "postponed" ? (
                              <>
                                <div className="st-match-row__status-date">{formatDate(match.datetime)}</div>
                                <div className="st-match-row__status-tag st-match-row__status-tag--postponed">ADIADO</div>
                              </>
                            ) : minsToKick != null && minsToKick <= 30 ? (
                              <>
                                <div className="st-match-row__status-tag st-match-row__status-tag--soon">BREVE</div>
                                <div className="st-match-row__status-minute">{minsToKick}&apos;</div>
                              </>
                            ) : (
                              <>
                                <div className="st-match-row__status-date">{formatDate(match.datetime)}</div>
                                <div className="st-match-row__status-label st-match-row__status-label--scheduled">{formatTime(match.datetime)}</div>
                              </>
                            )}
                          </div>
                          <div className="st-match-row__teams">
                            <div className="st-match-row__team">
                              {match.homeTeam.logo ? (
                                <img src={match.homeTeam.logo} alt="" className="st-match-row__team-logo" />
                              ) : (
                                <div className="st-match-row__team-logo st-match-row__team-logo--placeholder">H</div>
                              )}
                              <span className="st-match-row__team-name">{match.homeTeam.name}</span>
                            </div>
                            <div className="st-match-row__team">
                              {match.awayTeam.logo ? (
                                <img src={match.awayTeam.logo} alt="" className="st-match-row__team-logo" />
                              ) : (
                                <div className="st-match-row__team-logo st-match-row__team-logo--placeholder">A</div>
                              )}
                              <span className="st-match-row__team-name">{match.awayTeam.name}</span>
                            </div>
                          </div>
                          {(match.score && typeof match.score.home === "number" && typeof match.score.away === "number") ? (
                            <div className={`st-match-row__score ${displayStatus === "live" ? "st-match-row__score--live" : ""}`}>
                              <span className="st-match-row__score-main">{match.score.home} - {match.score.away}</span>
                              {match.score.halftime && typeof match.score.halftime.home === "number" && (
                                <span className="st-match-row__score-ht">HT {match.score.halftime.home}-{match.score.halftime.away}</span>
                              )}
                            </div>
                          ) : displayStatus === "live" ? (
                            <div className="st-match-row__score st-match-row__score--live st-match-row__score--loading">
                              <span className="st-match-row__score-main">- : -</span>
                            </div>
                          ) : null}
                          {oddsTab === "1x2" && (
                            <div className="st-match-row__odds">
                              <div className={`st-match-row__odd ${hlSet.has("1") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">1</span>
                                <span className="st-match-row__odd-value">{h > 0 ? h.toFixed(2) : "\u2014"}</span>
                              </div>
                              <div className={`st-match-row__odd ${hlSet.has("X") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">X</span>
                                <span className="st-match-row__odd-value">{d > 0 ? d.toFixed(2) : "\u2014"}</span>
                              </div>
                              <div className={`st-match-row__odd ${hlSet.has("2") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">2</span>
                                <span className="st-match-row__odd-value">{a > 0 ? a.toFixed(2) : "\u2014"}</span>
                              </div>
                            </div>
                          )}
                          {oddsTab === "double-chance" && (() => {
                            const dc1x = h > 0 && d > 0 ? parseFloat((1 / (1 / h + 1 / d)).toFixed(2)) : 0;
                            const dc12 = h > 0 && a > 0 ? parseFloat((1 / (1 / h + 1 / a)).toFixed(2)) : 0;
                            const dcx2 = d > 0 && a > 0 ? parseFloat((1 / (1 / d + 1 / a)).toFixed(2)) : 0;
                            return (
                              <div className="st-match-row__odds">
                                <div className={`st-match-row__odd ${hlSet.has("1X") ? "st-match-row__odd--highlight" : ""}`}>
                                  <span className="st-match-row__odd-label">1X</span>
                                  <span className="st-match-row__odd-value">{dc1x > 0 ? dc1x.toFixed(2) : "-"}</span>
                                </div>
                                <div className={`st-match-row__odd ${hlSet.has("12") ? "st-match-row__odd--highlight" : ""}`}>
                                  <span className="st-match-row__odd-label">12</span>
                                  <span className="st-match-row__odd-value">{dc12 > 0 ? dc12.toFixed(2) : "-"}</span>
                                </div>
                                <div className={`st-match-row__odd ${hlSet.has("X2") ? "st-match-row__odd--highlight" : ""}`}>
                                  <span className="st-match-row__odd-label">X2</span>
                                  <span className="st-match-row__odd-value">{dcx2 > 0 ? dcx2.toFixed(2) : "-"}</span>
                                </div>
                              </div>
                            );
                          })()}
                          {oddsTab === "btts" && (
                            <div className="st-match-row__odds">
                              <div className={`st-match-row__odd ${hlSet.has("Sim") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">Sim</span>
                                <span className="st-match-row__odd-value">{safeOdd(match.odds?.bttsYes) > 0 ? safeOdd(match.odds?.bttsYes).toFixed(2) : "-"}</span>
                              </div>
                              <div className={`st-match-row__odd ${hlSet.has("Nao") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">Nao</span>
                                <span className="st-match-row__odd-value">{safeOdd(match.odds?.bttsNo) > 0 ? safeOdd(match.odds?.bttsNo).toFixed(2) : "-"}</span>
                              </div>
                              <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                                <span className="st-match-row__odd-label">Prob%</span>
                                <span className="st-match-row__odd-value">{match.stats?.bttsProb > 0 ? `${match.stats.bttsProb.toFixed(0)}%` : "-"}</span>
                              </div>
                            </div>
                          )}
                          {oddsTab === "goals" && (
                            <div className="st-match-row__odds">
                              <div className={`st-match-row__odd ${hlSet.has("O 1.5") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">O 1.5</span>
                                <span className="st-match-row__odd-value">{safeOdd(match.odds?.over15) > 0 ? safeOdd(match.odds?.over15).toFixed(2) : "-"}</span>
                              </div>
                              <div className={`st-match-row__odd ${hlSet.has("O 2.5") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">O 2.5</span>
                                <span className="st-match-row__odd-value">{safeOdd(match.odds?.over25) > 0 ? safeOdd(match.odds?.over25).toFixed(2) : "-"}</span>
                              </div>
                              <div className={`st-match-row__odd ${hlSet.has("O 3.5") ? "st-match-row__odd--highlight" : ""}`}>
                                <span className="st-match-row__odd-label">O 3.5</span>
                                <span className="st-match-row__odd-value">{safeOdd(match.odds?.over35) > 0 ? safeOdd(match.odds?.over35).toFixed(2) : "-"}</span>
                              </div>
                            </div>
                          )}
                          {oddsTab === "cards" && (
                            <div className="st-match-row__odds">
                              <div className="st-match-row__odd">
                                <span className="st-match-row__odd-label">Casa</span>
                                <span className="st-match-row__odd-value">{match.stats?.homeCardsPerMatch ? match.stats.homeCardsPerMatch.toFixed(1) : "-"}</span>
                              </div>
                              <div className="st-match-row__odd">
                                <span className="st-match-row__odd-label">Fora</span>
                                <span className="st-match-row__odd-value">{match.stats?.awayCardsPerMatch ? match.stats.awayCardsPerMatch.toFixed(1) : "-"}</span>
                              </div>
                              <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                                <span className="st-match-row__odd-label">Liga</span>
                                <span className="st-match-row__odd-value">{match.stats?.leagueAvgCards ? match.stats.leagueAvgCards.toFixed(1) : "-"}</span>
                              </div>
                            </div>
                          )}
                          {oddsTab === "corners" && (
                            <div className="st-match-row__odds">
                              <div className="st-match-row__odd">
                                <span className="st-match-row__odd-label">Casa</span>
                                <span className="st-match-row__odd-value">{match.stats?.homeCornersPerMatch ? match.stats.homeCornersPerMatch.toFixed(1) : "-"}</span>
                              </div>
                              <div className="st-match-row__odd">
                                <span className="st-match-row__odd-label">Fora</span>
                                <span className="st-match-row__odd-value">{match.stats?.awayCornersPerMatch ? match.stats.awayCornersPerMatch.toFixed(1) : "-"}</span>
                              </div>
                              <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                                <span className="st-match-row__odd-label">Liga</span>
                                <span className="st-match-row__odd-value">{match.stats?.leagueAvgCorners ? match.stats.leagueAvgCorners.toFixed(1) : "-"}</span>
                              </div>
                            </div>
                          )}
                          <button
                            type="button"
                            className="st-match-row__favorite"
                            data-share-hide="true"
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleFavorite(match.id); }}
                            aria-label={favoriteIds.has(match.id) ? "Remover dos favoritos" : "Adicionar aos favoritos"}
                          >
                            <Star size={14} fill={favoriteIds.has(match.id) ? "currentColor" : "none"} />
                          </button>
                          {match.predictions && match.predictions.length > 0 && (
                            <div className="st-match-row__predictions">
                              {match.predictions.map((pred, pidx) => (
                                <div key={pidx} className="st-prediction-badge">
                                  <span className={`st-prediction-status st-prediction-status--${(pred.classification || pred.status).toLowerCase().replace("*", "-star")}`} style={{ color: getClassificationDisplay(pred.classification || pred.status).color, backgroundColor: getClassificationDisplay(pred.classification || pred.status).bgColor }}>
                                    {getClassificationDisplay(pred.classification || pred.status).label}
                                  </span>
                                  {/* #130b: Sub-badge for direction-natural picks without EV */}
                                  {pred.reason_codes?.includes("DIRECTION_NATURAL_NO_EV") && (
                                    <span style={{ fontSize: "0.6em", color: "#60a5fa", background: "rgba(96,165,250,0.1)", border: "1px solid rgba(96,165,250,0.25)", borderRadius: 4, padding: "1px 5px", marginLeft: 3, whiteSpace: "nowrap" as const, fontWeight: 500 }} title="O modelo aponta nesta direção, mas sem valor de aposta (EV negativo)">↗ Direção</span>
                                  )}
                                  <span className="st-prediction-sep" aria-hidden="true">|</span>
                                  <span className="st-prediction-market">{pred.mercado}</span>
                                  <span className="st-prediction-sep" aria-hidden="true">|</span>
                                  <span className="st-prediction-prob">{pred.prob_min}-{pred.prob_max}%</span>
                                  {/* EV display — show real EV% when available, fallback to odd_minima */}
                                  {pred.ev != null ? (
                                    <>
                                      <span className="st-prediction-sep" aria-hidden="true">|</span>
                                      <span
                                        className="st-prediction-odd"
                                        style={{
                                          color: pred.ev >= 0.05 ? "#00df82" : pred.ev >= 0 ? "#ffaa44" : "#ff5555",
                                        }}
                                        title={`EV: ${(pred.ev * 100).toFixed(1)}% | Odd mín: ${pred.odd_minima?.toFixed(2) ?? "-"}`}
                                      >
                                        EV: {pred.ev >= 0 ? "+" : ""}{(pred.ev * 100).toFixed(1)}%
                                      </span>
                                    </>
                                  ) : pred.odd_minima != null ? (
                                    <>
                                      <span className="st-prediction-sep" aria-hidden="true">|</span>
                                      <span className="st-prediction-odd" style={{ opacity: 0.7 }} title="Odd mínima para EV positivo">
                                        Odd mín: {pred.odd_minima.toFixed(2)}
                                      </span>
                                    </>
                                  ) : null}
                                  {pred.alerta && (
                                    <>
                                      <span className="st-prediction-sep" aria-hidden="true">|</span>
                                      <span className="st-prediction-alert">{pred.alerta}</span>
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  </div>
                );
              })}
            </>}
          </div>
        )}

        {/* RIGHT PANEL - Em mobile, esconder quando nenhum jogo está selecionado */}
        {(!isMobile || selectedMatchId) && (
          <section ref={rightPanelRef} className="st-panel-right detail-card-section">
            {detailData ? (
              <>
              {/* Bankroll Card (#094) */}
              {detailData.predictions && detailData.predictions.length > 0 && (() => {
                const evPicks = detailData.predictions.filter((p) => (p.ev ?? 0) > 0 && p.book_odd != null && p.book_odd > 1);
                const stakes = evPicks.map((p) => calcQuarterKelly(
                  (p.calibrated_probability ?? (p.prob_max ?? 50) / 100),
                  p.book_odd!,
                  bankroll,
                ));
                const totalStake = stakes.reduce((s, k) => s + k.stake, 0);
                const avgEV = evPicks.length > 0 ? evPicks.reduce((s, p) => s + ((p.ev ?? 0) * 100), 0) / evPicks.length : 0;
                return (
                  <BankrollCard
                    bankroll={bankroll}
                    onBankrollChange={handleBankrollChange}
                    totalStake={totalStake}
                    avgEV={avgEV}
                    pickCount={evPicks.length}
                  />
                );
              })()}
              {process.env.NEXT_PUBLIC_USE_NEW_ANALYSIS === "1" ? (
                (() => {
                  const mapped = mapToMatchAnalysis(detailData);
                  return (
                    <MatchAnalysis
                      match={mapped.match}
                      picks={mapped.picks}
                      analysis={mapped.analysis}
                      bankroll={bankroll}
                    />
                  );
                })()
              ) : (
                <MatchDetailCard
                  match={detailData}
                  version={appVersion}
                  onAudit={handleAudit}
                  onApplyCorrection={handleApplyCorrection}
                  auditResult={auditResult}
                  auditLoading={auditLoading}
                  auditResultRef={auditResultRef}
                  onBack={() => setSelectedMatchId(null)}
                  showBackButton={isMobile}
                  isFavorite={selectedMatchId ? favoriteIds.has(selectedMatchId) : false}
                  onFavorite={selectedMatchId ? () => toggleFavorite(selectedMatchId) : undefined}
                  onRegenerate={handleGenerateAiAnalysis}
                  bankroll={bankroll}
                />
              )}
              </>
            ) : (
              <div className="muted">Selecione um jogo para visualizar os detalhes.</div>
            )}
          </section>
        )}
      </div>

      {/* Reliability Panel (#101) */}
      {reliabilityOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 900, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
          onClick={(e) => { if (e.target === e.currentTarget) setReliabilityOpen(false); }}>
          <div style={{ width: "100%", maxWidth: 620 }}>
            {reliabilityLoading ? (
              <div style={{ background: "rgba(10,15,26,0.97)", borderRadius: 12, padding: 40, textAlign: "center", color: "#64748b", border: "1px solid rgba(96,165,250,0.15)" }}>
                <Loader2 size={20} className="st-spin-icon" style={{ marginBottom: 8 }} />
                <div style={{ fontSize: "0.7rem" }}>Carregando metricas...</div>
              </div>
            ) : reliabilityData ? (
              <ReliabilityCard data={reliabilityData} onClose={() => setReliabilityOpen(false)} />
            ) : (
              <div style={{ background: "rgba(10,15,26,0.97)", borderRadius: 12, padding: 30, textAlign: "center", color: "#ef4444", border: "1px solid rgba(239,68,68,0.15)" }}>
                <div style={{ fontSize: "0.7rem", marginBottom: 10 }}>Dados indisponiveis</div>
                <button onClick={handleReliabilityClick} style={{ fontSize: "0.6rem", padding: "5px 14px", borderRadius: 6, border: "1px solid rgba(96,165,250,0.3)", background: "rgba(96,165,250,0.1)", color: "#60a5fa", cursor: "pointer" }}>Tentar novamente</button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Batch Audit Panel (modal overlay) */}
      {batchAuditOpen && batchAuditResult && (
        <BatchAuditPanel
          result={batchAuditResult}
          onClose={() => setBatchAuditOpen(false)}
          onApplyCorrections={handleBatchApplyCorrections}
        />
      )}
    </div>
  );
}
