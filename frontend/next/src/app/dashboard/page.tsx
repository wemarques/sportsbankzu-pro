"use client";

import { useEffect, useMemo, useState } from "react";
import MatchDetailCard, { MatchDetail } from "@/components/MatchDetailCard";
import { AVAILABLE_LEAGUES, Match } from "@/lib/leagues";
import { getAiMatchAnalysis, getMatchesByLeague } from "@/lib/api";

export const dynamic = "force-dynamic";

type AiAnalysis = {
  summary: string;
  key_points?: string[];
  keyPoints?: string[];
  recommendation: string;
  confidence: number;
  last_updated?: string;
  lastUpdated?: string;
};

export default function Dashboard() {
  const [selectedLeague, setSelectedLeague] = useState<string>(AVAILABLE_LEAGUES[0]?.id ?? "");
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMatches() {
      if (!selectedLeague) return;
      setLoading(true);
      setError(null);
      try {
        // Envia 'date=tomorrow' para pegar jogos futuros, já que 'today' pode estar vazio
        const today = new Date().toISOString().split('T')[0];
        const res = await getMatchesByLeague(selectedLeague, today);
        const normalized: Match[] = (res?.matches ?? []).map(toMatch(selectedLeague));
        setMatches(normalized);
        setSelectedMatchId((prev) => (prev && normalized.some((m) => m.id === prev) ? prev : normalized[0]?.id ?? null));
      } catch (err) {
        setError("Não foi possível carregar os jogos.");
        setMatches([]);
        setSelectedMatchId(null);
      } finally {
        setLoading(false);
      }
    }
    fetchMatches();
  }, [selectedLeague]);

  useEffect(() => {
    async function fetchAi() {
      if (!selectedMatchId) {
        setAiAnalysis(null);
        return;
      }
      setAiLoading(true);
      const analysis = await getAiMatchAnalysis(selectedMatchId);
      setAiAnalysis(analysis);
      setAiLoading(false);
    }
    fetchAi();
  }, [selectedMatchId]);

  const selectedMatch = useMemo(() => matches.find((m) => m.id === selectedMatchId) ?? matches[0], [matches, selectedMatchId]);

  const detailMatch = useMemo<MatchDetail | null>(() => {
    if (!selectedMatch) return null;
    return toMatchDetail(selectedMatch, aiAnalysis, aiLoading);
  }, [selectedMatch, aiAnalysis, aiLoading]);

  return (
    <main className="scoretabs-page">
      <div className="scoretabs-header">
        <div className="scoretabs-title">SportsBank Pro • Dashboard Scoretabs</div>
        <div className="scoretabs-meta" suppressHydrationWarning>
          {new Date().toLocaleString("pt-BR")}
        </div>
      </div>

      <div className="scoretabs-layout">
        <aside className="matches-sidebar">
          <div className="sidebar-title">Jogos da Rodada</div>
          <div className="sidebar-controls">
            <select className="sidebar-select" value={selectedLeague} onChange={(e) => setSelectedLeague(e.target.value)}>
              {AVAILABLE_LEAGUES.map((league) => (
                <option key={league.id} value={league.id}>
                  {league.name}
                </option>
              ))}
            </select>
          </div>

          {loading && <div className="muted">Carregando jogos...</div>}
          {error && <div className="muted">{error}</div>}

          {!loading && !matches.length && (
            <div className="muted">Nenhum jogo disponível para a liga selecionada.</div>
          )}

          <div className="match-list">
            {matches.map((match) => (
              <button
                key={match.id}
                className={`match-list-item ${match.id === selectedMatchId ? "match-list-item--active" : ""}`}
                onClick={() => setSelectedMatchId(match.id)}
              >
                <div className="match-list-time">
                  {new Date(match.datetime).toLocaleDateString("pt-BR")} • {new Date(match.datetime).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="match-list-status">{statusLabel(match.status)}</div>
                <div className="match-list-teams">
                  <span>{match.homeTeam.name}</span>
                  <span>{match.awayTeam.name}</span>
                </div>
                <div className="match-odds-grid">
                  <span className="match-odds-cell">1 {safeOdd(match.odds?.home).toFixed(2)}</span>
                  <span className="match-odds-cell">X {safeOdd(match.odds?.draw).toFixed(2)}</span>
                  <span className="match-odds-cell">2 {safeOdd(match.odds?.away).toFixed(2)}</span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section>
          {detailMatch ? (
            <MatchDetailCard match={detailMatch} />
          ) : (
            <div className="muted">Selecione um jogo para visualizar os detalhes.</div>
          )}
        </section>
      </div>
    </main>
  );
}

function safeOdd(value?: number, fallback = 1.5) {
  if (!value || value <= 0) return fallback;
  return value;
}

function toMatchDetail(match: Match, aiAnalysis: AiAnalysis | null, aiLoading: boolean): MatchDetail {
  const homeOdd = safeOdd(match.odds?.home, 1.7);
  const drawOdd = safeOdd(match.odds?.draw, 3.1);
  const awayOdd = safeOdd(match.odds?.away, 3.8);
  const bttsYes = safeOdd(match.odds?.bttsYes, 2.0);
  const bttsNo = safeOdd(match.odds?.bttsNo, 1.7);
  const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
  const ai = aiLoading
    ? {
        summary: "Carregando análise Mistral...",
        keyPoints: ["Buscando insights para este jogo."],
        recommendation: "Aguardando análise.",
        confidence: 5,
        lastUpdated: new Date().toLocaleString("pt-BR"),
      }
    : aiAnalysis
      ? {
          summary: aiAnalysis.summary,
          keyPoints: aiAnalysis.key_points ?? aiAnalysis.keyPoints ?? [],
          recommendation: aiAnalysis.recommendation,
          confidence: aiAnalysis.confidence,
          lastUpdated: aiAnalysis.last_updated ?? aiAnalysis.lastUpdated ?? new Date().toLocaleString("pt-BR"),
        }
      : undefined;

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
    venue: {
      name: match.venue || "Estádio não informado",
      capacity: 0,
    },
    odds: {
      home: homeOdd,
      draw: drawOdd,
      away: awayOdd,
    },
    doubleChance: {
      homeOrDraw: Math.max(1.05, homeOdd * 0.7),
      homeOrAway: Math.max(1.05, awayOdd * 0.6),
      drawOrAway: Math.max(1.05, awayOdd * 0.7),
    },
    btts: {
      yes: bttsYes,
      no: bttsNo,
    },
    round: match.stats?.regime ?? "-",
    aiAnalysis: ai,
  };
}

function statusLabel(status: Match["status"]) {
  switch (status) {
    case "live":
      return "● Ao vivo";
    case "finished":
      return "Encerrado";
    case "postponed":
      return "Adiado";
    default:
      return "Agendado";
  }
}

function toMatch(leagueId: string) {
  return (item: any, idx: number): Match => {
    const home = item.home_team ?? item.homeTeam?.name ?? item.home ?? "Home";
    const away = item.away_team ?? item.awayTeam?.name ?? item.away ?? "Away";
    const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
    const leagueName = AVAILABLE_LEAGUES.find((l) => l.id === leagueId)?.name ?? leagueId;
    const statusRaw = item.status ?? "scheduled";
    return {
      id: item.id ?? `${leagueId}-${idx}-${home}-${away}-${dt}`,
      leagueId,
      leagueName,
      homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? [], rating: item.homeTeam?.rating ?? 0 },
      awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? [], rating: item.awayTeam?.rating ?? 0 },
      datetime: dt,
      venue: item.venue ?? "",
      status: statusRaw,
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
  };
}
