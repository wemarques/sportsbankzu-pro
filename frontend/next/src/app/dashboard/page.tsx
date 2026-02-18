"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
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
} from "lucide-react";
import "@/styles/scoretabs-dashboard.css";

const APP_VERSION = "pro V2.3";

type OddsTab = "1x2" | "double-chance" | "btts" | "goals" | "cards" | "corners";

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
      over25: item.odds?.over25 ?? 0,
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
      over25Prob: item.stats?.over25Prob ?? 0,
      regime: item.stats?.regime ?? "",
    },
    h2h: {
      totalMatches: item.h2h?.totalMatches ?? 0,
      homeWins: item.h2h?.homeWins ?? 0,
      draws: item.h2h?.draws ?? 0,
      awayWins: item.h2h?.awayWins ?? 0,
      avgGoals: item.h2h?.avgGoals ?? 0,
    },
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

  useEffect(() => { setMounted(true); }, []);

  /* Fetch all leagues on mount */
  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      const today = new Date().toISOString().split("T")[0];
      const allLeagueIds = AVAILABLE_LEAGUES.map((l) => l.id).join(",");
      try {
        const res = await getMatchesByLeague(allLeagueIds, today);
        const raw = res?.matches ?? [];
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
  }, []);

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
          <button className="st-nav__link">Campeonatos</button>
          <button className="st-nav__link">Ferramentas</button>
          <button className="st-nav__link">Recomendadas 2026</button>
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
        {/* LEFT PANEL */}
        <div className="st-panel-left">
          {/* Filter bar */}
          <div className="st-filters">
            <div className="st-date-nav">
              <button className="st-date-nav__btn"><ChevronLeft size={14} /></button>
              <span className="st-date-label">Hoje</span>
              <button className="st-date-nav__btn"><ChevronRight size={14} /></button>
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
              Nenhum jogo disponivel para hoje.
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
                    <button className="st-match-row__favorite" onClick={(e) => e.stopPropagation()} aria-label="Favoritar">
                      <Star size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <section className="st-panel-right detail-card-section">
          {detailData ? (
            <MatchDetailCard match={detailData} version={APP_VERSION} />
          ) : (
            <div className="muted">Selecione um jogo para visualizar os detalhes.</div>
          )}
        </section>
      </div>
    </div>
  );
}
