"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import MatchDetailCard, {
  type MatchDetailData,
  type AIAnalysis,
} from "@/components/MatchDetailCard";
import { AVAILABLE_LEAGUES, type Match } from "@/lib/leagues";
import { getMatchesByLeague, getAiMatchAnalysis } from "@/lib/api";
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
} from "lucide-react";
import "@/styles/scoretabs-dashboard.css";

const APP_VERSION = "pro V2.6";

type NavView = "matches" | "campeonatos" | "ferramentas" | "recomendadas";

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

function formatTime(dt: string) {
  try {
    const d = new Date(dt);
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--:--";
  }
}

function statusInfo(status: Match["status"]) {
  switch (status) {
    case "live":
      return { label: "AO VIVO", cssClass: "st-match-row__status-label--live" };
    case "finished":
      return { label: "FT", cssClass: "st-match-row__status-label--ft" };
    case "postponed":
      return { label: "ADIADO", cssClass: "st-match-row__status-label--ft" };
    default:
      return { label: "", cssClass: "st-match-row__status-label--scheduled" };
  }
}

function getLowestOddIndex(home: number, draw: number, away: number): number {
  const vals = [home, draw, away];
  const min = Math.min(...vals.filter((v) => v > 0));
  return vals.indexOf(min);
}

function normalizeMatch(item: any, leagueId: string, idx: number): Match {
  const home = item.home_team
    ?? (typeof item.homeTeam === "string" ? item.homeTeam : item.homeTeam?.name)
    ?? item.home ?? "Home";
  const away = item.away_team
    ?? (typeof item.awayTeam === "string" ? item.awayTeam : item.awayTeam?.name)
    ?? item.away ?? "Away";
  const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
  const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
  return {
    id: item.id ?? `${leagueId}-${idx}-${home}-${away}`,
    leagueId,
    leagueName: league?.name ?? leagueId,
    homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? [], rating: item.homeTeam?.rating ?? 0 },
    awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? [], rating: item.awayTeam?.rating ?? 0 },
    datetime: dt,
    venue: item.venue ?? item.stadium ?? "",
    status: item.status ?? "scheduled",
    score: item.score,
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
      leagueAvgCorners: item.stats?.leagueAvgCorners ?? 0,
      leagueAvgCards: item.stats?.leagueAvgCards ?? 0,
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
    season: league?.season ?? "2026",
    homeTeam: match.homeTeam.name,
    awayTeam: match.awayTeam.name,
    homeTeamLogo: match.homeTeam.logo || undefined,
    awayTeamLogo: match.awayTeam.logo || undefined,
    startTime: match.datetime,
    status: match.status === "postponed" ? "scheduled" : match.status,
    venue: { name: match.venue || "Estadio nao informado" },
    odds: { home: h, draw: d, away: a },
    doubleChance: {
      homeOrDraw: parseFloat((1 / (1 / h + 1 / d)).toFixed(2)),
      homeOrAway: parseFloat((1 / (1 / h + 1 / a)).toFixed(2)),
      drawOrAway: parseFloat((1 / (1 / d + 1 / a)).toFixed(2)),
    },
    btts: { yes: safeOdd(match.odds?.bttsYes, 2.0), no: safeOdd(match.odds?.bttsNo, 1.7) },
    matchStats: {
      homeWinProb: match.stats?.homeWinProb,
      drawProb: match.stats?.drawProb,
      awayWinProb: match.stats?.awayWinProb,
      avgGoals: match.stats?.avgGoals,
      bttsProb: match.stats?.bttsProb,
      over15Prob: match.stats?.over15Prob,
      over25Prob: match.stats?.over25Prob,
      over35Prob: match.stats?.over35Prob,
      over45Prob: match.stats?.over45Prob,
      lambdaHome: match.stats?.lambdaHome,
      lambdaAway: match.stats?.lambdaAway,
      homePossession: match.stats?.homePossession,
      awayPossession: match.stats?.awayPossession,
      homeXG: match.stats?.homeXG,
      awayXG: match.stats?.awayXG,
      leagueRegime: match.stats?.leagueRegime,
      leagueVolatility: match.stats?.leagueVolatility,
      homeCornersPerMatch: match.stats?.homeCornersPerMatch,
      awayCornersPerMatch: match.stats?.awayCornersPerMatch,
      homeCardsPerMatch: match.stats?.homeCardsPerMatch,
      awayCardsPerMatch: match.stats?.awayCardsPerMatch,
      leagueAvgCorners: match.stats?.leagueAvgCorners,
      leagueAvgCards: match.stats?.leagueAvgCards,
    },
    h2h: match.h2h,
    homeForm: match.stats?.homeForm ?? match.homeTeam.form,
    awayForm: match.stats?.awayForm ?? match.awayTeam.form,
    round: match.stats?.regime ?? "-",
    aiAnalysis: ai,
  };
}

/* ── COMPONENT ── */

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [oddsTab, setOddsTab] = useState<OddsTab>("1x2");
  const [collapsedLeagues, setCollapsedLeagues] = useState<Set<string>>(new Set());
  const [dateMode, setDateMode] = useState<DateMode>("today");
  const [navView, setNavView] = useState<NavView>("matches");
  
  // Hook para detectar se estamos em mobile/tablet
  const isMobile = useMediaQuery("(max-width: 1024px)");

  useEffect(() => { setMounted(true); }, []);

  const dateLabel = dateMode === "today" ? "Hoje" : dateMode === "tomorrow" ? "Amanha" : "Proxima Rodada";

  /* Fetch all leagues — fallback to "week" if today returns empty */
  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      const allLeagueIds = AVAILABLE_LEAGUES.map((l) => l.id).join(",");

      function dateParamFor(mode: DateMode): string {
        if (mode === "today") return new Date().toISOString().split("T")[0];
        if (mode === "tomorrow") {
          const d = new Date();
          d.setDate(d.getDate() + 1);
          return d.toISOString().split("T")[0];
        }
        return "week";
      }

      try {
        let res = await getMatchesByLeague(allLeagueIds, dateParamFor(dateMode));
        let raw = res?.matches ?? [];

        // Auto-fallback: if today returns empty, try week
        if (raw.length === 0 && dateMode === "today") {
          res = await getMatchesByLeague(allLeagueIds, "week");
          raw = res?.matches ?? [];
          if (raw.length > 0) setDateMode("week");
        }

        const normalized = raw.map((item: any, idx: number) => {
          const lid = item.leagueId ?? AVAILABLE_LEAGUES[0]?.id ?? "unknown";
          return normalizeMatch(item, lid, idx);
        });
        setAllMatches(normalized);
        if (normalized.length > 0) setSelectedMatchId(normalized[0].id);
      } catch {
        setAllMatches([]);
      } finally {
        setLoading(false);
      }
    }
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateMode]);

  const selectedMatch = useMemo(() => allMatches.find((m) => m.id === selectedMatchId), [allMatches, selectedMatchId]);

  useEffect(() => {
    async function fetchAi() {
      if (!selectedMatch) {
        setAiAnalysis(null);
        return;
      }
      setAiLoading(true);
      const analysis = await getAiMatchAnalysis(selectedMatch.id);
      setAiAnalysis(analysis);
      setAiLoading(false);
    }
    fetchAi();
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

  const leagueGroups = useMemo<LeagueGroup[]>(() => {
    const byLeague = new Map<string, Match[]>();
    for (const m of allMatches) {
      const list = byLeague.get(m.leagueId) ?? [];
      list.push(m);
      byLeague.set(m.leagueId, list);
    }
    return Array.from(byLeague.entries()).map(([leagueId, matches]) => {
      const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
      return {
        leagueId,
        leagueName: league?.name ?? leagueId,
        countryFlag: league?.countryFlag ?? "🏆",
        country: league?.country ?? "",
        matches,
        collapsed: collapsedLeagues.has(leagueId),
      };
    });
  }, [allMatches, collapsedLeagues]);

  const oddsTabs: { key: OddsTab; label: string }[] = [
    { key: "1x2", label: "1X2" },
    { key: "double-chance", label: "Dupla Chance" },
    { key: "btts", label: "BTTS" },
    { key: "goals", label: "Gols" },
    { key: "cards", label: "Cartoes" },
    { key: "corners", label: "Escanteios" },
  ];

  return (
    <div className="st-app">
      {/* TOP NAV */}
      <nav className="st-nav">
        <div className="st-nav__logo">
          sports<span>bank</span>.
        </div>
        <div className="st-nav__links">
          <button className={`st-nav__link ${navView === "campeonatos" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "campeonatos" ? "matches" : "campeonatos")}>
            <Trophy size={14} />
            Campeonatos
          </button>
          <button className={`st-nav__link ${navView === "ferramentas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "ferramentas" ? "matches" : "ferramentas")}>
            <Wrench size={14} />
            Ferramentas
          </button>
          <button className={`st-nav__link ${navView === "recomendadas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "recomendadas" ? "matches" : "recomendadas")}>
            <Sparkles size={14} />
            Recomendadas 2026
          </button>
        </div>
        <div className="st-nav__right">
          <span className="st-badge-pro">{APP_VERSION}</span>
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

      <div className="st-main">
        {/* LEFT PANEL - Em mobile, esconder quando um jogo está selecionado */}
        {(!isMobile || !selectedMatchId) && (
        <div className="st-panel-left">

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
                      onClick={() => { setNavView("matches"); }}
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
              </div>
            </div>
          )}

          {/* ── RECOMENDADAS VIEW ── */}
          {navView === "recomendadas" && (
            <div className="st-view-panel">
              <div className="st-view-header">
                <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                <h2 className="st-view-title"><Sparkles size={16} /> Recomendadas 2026</h2>
              </div>
              <div className="st-view-subtitle">Jogos com melhor potencial baseado em probabilidades, Lambda e analise estatistica</div>
              <div className="st-view-content">
                {allMatches.length === 0 && (
                  <div className="st-empty">
                    <div className="st-empty__icon">&#9917;</div>
                    Carregando jogos para analise...
                  </div>
                )}
                {allMatches
                  .filter((m) => m.status === "scheduled")
                  .sort((a, b) => {
                    // Score: higher homeWinProb or awayWinProb + high over25 + btts data
                    const scoreA = Math.max(a.stats?.homeWinProb ?? 0, a.stats?.awayWinProb ?? 0) + (a.stats?.over25Prob ?? 0) * 0.5;
                    const scoreB = Math.max(b.stats?.homeWinProb ?? 0, b.stats?.awayWinProb ?? 0) + (b.stats?.over25Prob ?? 0) * 0.5;
                    return scoreB - scoreA;
                  })
                  .slice(0, 15)
                  .map((match) => {
                    const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
                    const maxProb = Math.max(match.stats?.homeWinProb ?? 0, match.stats?.awayWinProb ?? 0);
                    const probLabel = maxProb === (match.stats?.homeWinProb ?? 0) ? `${match.homeTeam.name} (${maxProb.toFixed(0)}%)` : `${match.awayTeam.name} (${maxProb.toFixed(0)}%)`;
                    const confidenceColor = maxProb >= 55 ? "#00ff88" : maxProb >= 40 ? "#ffbb33" : "#ff4444";
                    return (
                      <div
                        key={match.id}
                        className="st-rec-card"
                        onClick={() => { setSelectedMatchId(match.id); setNavView("matches"); }}
                      >
                        <div className="st-rec-card__header">
                          <span className="st-rec-card__league">{league?.countryFlag} {league?.name ?? match.leagueId}</span>
                          <span className="st-rec-card__time">{formatTime(match.datetime)}</span>
                        </div>
                        <div className="st-rec-card__teams">
                          <span className="st-rec-card__team">{match.homeTeam.name}</span>
                          <span className="st-rec-card__vs">vs</span>
                          <span className="st-rec-card__team">{match.awayTeam.name}</span>
                        </div>
                        <div className="st-rec-card__stats">
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">Favorito</span>
                            <span className="st-rec-card__stat-value" style={{ color: confidenceColor }}>{probLabel}</span>
                          </div>
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">Over 2.5</span>
                            <span className="st-rec-card__stat-value">{match.stats?.over25Prob ? `${match.stats.over25Prob.toFixed(0)}%` : "-"}</span>
                          </div>
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">BTTS</span>
                            <span className="st-rec-card__stat-value">{match.stats?.bttsProb ? `${match.stats.bttsProb.toFixed(0)}%` : "-"}</span>
                          </div>
                        </div>
                        {match.odds?.home > 0 && (
                          <div className="st-rec-card__odds">
                            <span className="st-rec-card__odd">1: {match.odds.home.toFixed(2)}</span>
                            <span className="st-rec-card__odd">X: {match.odds.draw.toFixed(2)}</span>
                            <span className="st-rec-card__odd">2: {match.odds.away.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* ── MATCHES VIEW (default) ── */}
          {navView === "matches" && <>
          {/* Filter bar */}
          <div className="st-filters">
            <div className="st-date-nav">
              <button className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "week" ? "tomorrow" : prev === "tomorrow" ? "today" : "today")}><ChevronLeft size={14} /></button>
              <span className="st-date-label">{dateLabel}</span>
              <button className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "today" ? "tomorrow" : prev === "tomorrow" ? "week" : "week")}><ChevronRight size={14} /></button>
            </div>
            <div className="st-live-dot" />
            <button className="st-filter-btn"><SlidersHorizontal size={12} /> Ordenar</button>
            <button className="st-filter-btn"><Heart size={12} /> Favoritos</button>
            <button className="st-filter-btn"><Filter size={12} /> Filtros</button>
          </div>

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

          {!loading && leagueGroups.length === 0 && (
            <div className="st-empty">
              <div className="st-empty__icon">&#9917;</div>
              {dateMode === "week"
                ? "Nenhum jogo encontrado para esta semana. Tente novamente mais tarde."
                : "Nenhum jogo disponivel. Use as setas para navegar entre datas."}
            </div>
          )}

          {!loading && leagueGroups.map((group) => (
            <div key={group.leagueId} className="st-league-group">
              <div className="st-league-header" onClick={() => toggleLeague(group.leagueId)}>
                <span className="st-league-flag">{group.countryFlag}</span>
                <span className="st-league-name">
                  {group.leagueName}
                  <span className="st-league-count"> ({group.matches.length})</span>
                </span>
                <div className="st-league-actions">
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
                const si = statusInfo(match.status);
                const h = safeOdd(match.odds?.home);
                const d = safeOdd(match.odds?.draw);
                const a = safeOdd(match.odds?.away);
                const lowestIdx = getLowestOddIndex(h, d, a);
                const isSelected = match.id === selectedMatchId;

                return (
                  <div
                    key={match.id}
                    className={`st-match-row ${isSelected ? "st-match-row--selected" : ""}`}
                    onClick={() => setSelectedMatchId(match.id)}
                  >
                    <div className="st-match-row__status">
                      <div className={`st-match-row__status-label ${si.cssClass}`}>
                        {si.label || formatTime(match.datetime)}
                      </div>
                      {si.label && (
                        <div className="st-match-row__status-time">{formatTime(match.datetime)}</div>
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
                    {match.score && (
                      <div className="st-match-row__score">
                        {match.score.home ?? 0} - {match.score.away ?? 0}
                      </div>
                    )}
                    {oddsTab === "1x2" && (
                      <div className="st-match-row__odds">
                        <div className={`st-match-row__odd ${lowestIdx === 0 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">1</span>
                          <span className="st-match-row__odd-value">{h.toFixed(2)}</span>
                        </div>
                        <div className={`st-match-row__odd ${lowestIdx === 1 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">X</span>
                          <span className="st-match-row__odd-value">{d.toFixed(2)}</span>
                        </div>
                        <div className={`st-match-row__odd ${lowestIdx === 2 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">2</span>
                          <span className="st-match-row__odd-value">{a.toFixed(2)}</span>
                        </div>
                      </div>
                    )}
                    {oddsTab === "double-chance" && (() => {
                      const dc1x = h > 0 && d > 0 ? parseFloat((1 / (1/h + 1/d)).toFixed(2)) : 0;
                      const dc12 = h > 0 && a > 0 ? parseFloat((1 / (1/h + 1/a)).toFixed(2)) : 0;
                      const dcx2 = d > 0 && a > 0 ? parseFloat((1 / (1/d + 1/a)).toFixed(2)) : 0;
                      return (
                        <div className="st-match-row__odds">
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">1X</span>
                            <span className="st-match-row__odd-value">{dc1x > 0 ? dc1x.toFixed(2) : "-"}</span>
                          </div>
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">12</span>
                            <span className="st-match-row__odd-value">{dc12 > 0 ? dc12.toFixed(2) : "-"}</span>
                          </div>
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">X2</span>
                            <span className="st-match-row__odd-value">{dcx2 > 0 ? dcx2.toFixed(2) : "-"}</span>
                          </div>
                        </div>
                      );
                    })()}
                    {oddsTab === "btts" && (
                      <div className="st-match-row__odds">
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Sim</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.bttsYes) > 0 ? safeOdd(match.odds?.bttsYes).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
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
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">O 1.5</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.over15) > 0 ? safeOdd(match.odds?.over15).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd st-match-row__odd--highlight">
                          <span className="st-match-row__odd-label">O 2.5</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.over25) > 0 ? safeOdd(match.odds?.over25).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
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
                    <button className="st-match-row__favorite" onClick={(e) => e.stopPropagation()} aria-label="Favoritar">
                      <Star size={14} />
                    </button>
                    {match.predictions && match.predictions.length > 0 && (
                      <div className="st-match-row__predictions">
                        {match.predictions.map((pred, pidx) => (
                          <div key={pidx} className="st-prediction-badge">
                            <span className={`st-prediction-status st-prediction-status--${pred.status.toLowerCase().replace("*", "-star")}`}>
                              {pred.status}
                            </span>
                            <span className="st-prediction-market">{pred.mercado}</span>
                            <span className="st-prediction-prob">prob {pred.prob_min}-{pred.prob_max}%</span>
                            <span className="st-prediction-odd">odd min. EV+ {pred.odd_minima != null ? `≈${pred.odd_minima.toFixed(2)}` : "-"}</span>
                            {pred.alerta && <span className="st-prediction-alert">△ {pred.alerta}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          </>}
        </div>
        )}

        {/* RIGHT PANEL - Em mobile, esconder quando nenhum jogo está selecionado */}
        {(!isMobile || selectedMatchId) && (
        <section className="st-panel-right detail-card-section">
          {detailData ? (
            <MatchDetailCard 
              match={detailData} 
              version={APP_VERSION}
              onBack={() => setSelectedMatchId(null)}
              showBackButton={isMobile}
            />
          ) : (
            <div className="muted">Selecione um jogo para visualizar os detalhes.</div>
          )}
        </section>
        )}
      </div>
    </div>
  );
}
