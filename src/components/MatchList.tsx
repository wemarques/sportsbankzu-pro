"use client";
import { useEffect, useMemo, useState } from "react";
import { AVAILABLE_LEAGUES, Match } from "../lib/leagues";

type DateFilter = "today" | "tomorrow" | "week";
type StatusFilter = "all" | "scheduled" | "live" | "finished";

interface MatchesListProps {
  matches: Match[];
  league: string;
  dateFilter: DateFilter;
  statusFilter: StatusFilter;
  onSelectMatch: (match: Match) => void;
  selectedMatches: string[];
  loading?: boolean;
}

export default function MatchesList({ matches, league, dateFilter, statusFilter, onSelectMatch, selectedMatches, loading = false }: MatchesListProps) {
  const [localStatus, setLocalStatus] = useState<StatusFilter>(statusFilter);

  const filtered = useMemo(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    let end = new Date(start);
    if (dateFilter === "today") end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
    else if (dateFilter === "tomorrow") {
      const t = new Date(start.getTime() + 24 * 60 * 60 * 1000);
      start.setTime(t.getTime());
      end = new Date(t.getTime() + 24 * 60 * 60 * 1000);
    } else if (dateFilter === "week") end = new Date(start.getTime() + 7 * 24 * 60 * 60 * 1000);

    return matches.filter((m) => {
      const dt = new Date(m.datetime);
      const inRange = dt >= start && dt < end;
      const statusValue = unifyStatus(m.status);
      const statusOk = localStatus === "all" ? true : statusValue === localStatus || (localStatus === "finished" && statusValue === "finished") || (localStatus === "finished" && statusValue === "completed");
      return inRange && statusOk;
    });
  }, [matches, dateFilter, localStatus]);

  useEffect(() => { setLocalStatus(statusFilter); }, [statusFilter]);

  if (loading) return <div className="flex items-center justify-center p-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--primary)]"></div><span className="ml-3">Carregando jogos...</span></div>;
  if (!filtered?.length) return <div className="muted">Nenhum jogo disponível para {league} no período selecionado.</div>;

  return (
    <div className="overflow-x-auto">
      <div className="mb-3 flex gap-2">
        <button onClick={() => setLocalStatus("all")} className={`px-3 py-2 rounded-md border ${localStatus === "all" ? "bg-[var(--primary)] text-black" : "bg-[var(--card)] border-[var(--border)]"}`}>Todos</button>
        <button onClick={() => setLocalStatus("scheduled")} className={`px-3 py-2 rounded-md border ${localStatus === "scheduled" ? "bg-[var(--primary)] text-black" : "bg-[var(--card)] border-[var(--border)]"}`}>Agendados</button>
        <button onClick={() => setLocalStatus("finished")} className={`px-3 py-2 rounded-md border ${localStatus === "finished" ? "bg-[var(--primary)] text-black" : "bg-[var(--card)] border-[var(--border)]"}`}>Realizados</button>
      </div>
      <table className="w-full text-base">
        <thead className="text-left">
          <tr>
            <th className="py-2">Selecionar</th>
            <th>Liga</th>
            <th>Jogo</th>
            <th>Horário</th>
            <th>Estádio</th>
            <th>Status</th>
            <th>Odds 1X2</th>
            <th>BTTS</th>
            <th>O/U 2.5</th>
            <th>Prob 1X2</th>
            <th>Ratings</th>
            <th>Form</th>
            <th>H2H</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m) => (
            <tr key={m.id} className="border-t border-[var(--border)]">
              <td className="py-2">
                <input type="checkbox" checked={selectedMatches.includes(m.id)} onChange={() => onSelectMatch(m)} />
              </td>
              <td>{m.leagueName || "-"}</td>
              <td className="font-semibold">{m.homeTeam.name} vs {m.awayTeam.name}</td>
              <td>{new Date(m.datetime).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
              <td>{m.venue || "-"}</td>
              <td>{unifyStatus(m.status)}</td>
              <td>{`H ${m.odds.home} / D ${m.odds.draw} / A ${m.odds.away}`}</td>
              <td>{`Yes ${m.odds.bttsYes} / No ${m.odds.bttsNo}`}</td>
              <td>{`O ${m.odds.over25} / U ${m.odds.under25}`}</td>
              <td className="text-[var(--primary)]">{`${m.stats.homeWinProb}%`}</td>
              <td>{`${m.homeTeam.rating} / ${m.awayTeam.rating}`}</td>
              <td>
                <span className="muted text-xs">H: {m.homeTeam.form.join(" ")}</span><br />
                <span className="muted text-xs">A: {m.awayTeam.form.join(" ")}</span>
              </td>
              <td className="text-xs">{`H ${m.h2h.homeWins} / D ${m.h2h.draws} / A ${m.h2h.awayWins} (${m.h2h.avgGoals} gols)`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function unifyStatus(s: any): StatusFilter {
  const v = String(s || "").toLowerCase();
  if (v === "completed" || v === "finished") return "finished";
  if (v === "live") return "live";
  if (v === "scheduled") return "scheduled";
  return "all";
}

function normalizeMatches(raw: any, leagues: string[]): Match[] {
  const arr = Array.isArray(raw?.matches) ? raw.matches : Array.isArray(raw) ? raw : [];
  if (!arr.length) return [];
  return arr.map((item: any, idx: number) => {
    const home = item.homeTeam?.name ?? item.home_team ?? item.home ?? "Home";
    const away = item.awayTeam?.name ?? item.away_name ?? item.away ?? "Away";
    const dt = item.datetime ?? item.match_date ?? new Date().toISOString();
    const leagueId = item.leagueId ?? leagues?.[0] ?? "unknown";
    const leagueName = AVAILABLE_LEAGUES.find((l) => l.id === leagueId)?.name ?? (item.leagueName ?? leagueId);
    const statusRaw = item.status ?? "scheduled";
    const m: Match = {
      id: item.id ?? `${leagueId}-${idx}-${home}-${away}-${dt}`,
      leagueId,
      leagueName,
      homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? [], rating: item.homeTeam?.rating ?? 0 },
      awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? [], rating: item.awayTeam?.rating ?? 0 },
      datetime: dt,
      venue: item.venue ?? "",
      status: unifyStatus(statusRaw),
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
      },
      h2h: {
        totalMatches: item.h2h?.totalMatches ?? 0,
        homeWins: item.h2h?.homeWins ?? 0,
        draws: item.h2h?.draws ?? 0,
        awayWins: item.h2h?.awayWins ?? 0,
        avgGoals: item.h2h?.avgGoals ?? 0,
      },
      source: item.source ?? "backend",
      lastUpdated: item.lastUpdated ?? new Date().toISOString(),
    };
    return m;
  });
}
