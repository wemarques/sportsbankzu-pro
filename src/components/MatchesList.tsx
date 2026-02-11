 "use client";
import { useState } from "react";
import { Calendar, Clock, MapPin, TrendingUp, CheckCircle2 } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsList, TabsTrigger } from "./ui/tabs";
import { ScrollArea } from "./ui/scroll-area";
import { Progress } from "./ui/progress";
import { type Match } from "./MatchCard";
import { startOfDay, endOfDay, addDays } from "date-fns";

type MatchesListProps = {
  matches: Match[];
  selectedMatches: string[];
  onSelectMatch: (matchId: string) => void;
  isLoading: boolean;
};

export default function MatchesList({
  matches,
  selectedMatches,
  onSelectMatch,
  isLoading,
}: MatchesListProps) {
  const [dateFilter, setDateFilter] = useState<"today" | "tomorrow" | "week">("today");
  const [statusFilter, setStatusFilter] = useState<"all" | "scheduled" | "live">("all");
  const [picks, setPicks] = useState<Array<{ market: string; prob: number; odds?: number; ev?: number; risk?: string; reasons?: string[] }>>([]);

  function getRange() {
    const now = new Date();
    if (dateFilter === "today") return { start: startOfDay(now), end: endOfDay(now) };
    if (dateFilter === "tomorrow") {
      const d = addDays(now, 1);
      return { start: startOfDay(d), end: endOfDay(d) };
    }
    return { start: startOfDay(now), end: endOfDay(addDays(now, 7)) };
  }

  const { start, end } = getRange();

  const filteredMatches = matches
    .filter((match) => {
      if (statusFilter !== "all" && match.status !== statusFilter) return false;
      const d = new Date(match.datetime);
      return d >= start && d <= end;
    });

  const matchesByLeague = filteredMatches.reduce((acc, match) => {
    if (!acc[match.leagueId]) {
      acc[match.leagueId] = { leagueName: match.leagueName, matches: [] as Match[] };
    }
    acc[match.leagueId].matches.push(match);
    return acc;
  }, {} as Record<string, { leagueName: string; matches: Match[] }>);

  return (
    <Card className="bg-[#12121a] border-[#1e1e2e] p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Calendar className="h-5 w-5 text-[var(--accent)]" />
          Jogos da Rodada
        </h3>
        <div className="flex items-center gap-2">
          <Tabs value={dateFilter} onValueChange={(v) => setDateFilter(v as any)}>
            <TabsList className="bg-[#0a0a0f]">
              <TabsTrigger value="today">Hoje</TabsTrigger>
              <TabsTrigger value="tomorrow">Amanhã</TabsTrigger>
              <TabsTrigger value="week">Semana</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <Badge
          variant={statusFilter === "all" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setStatusFilter("all")}
        >
          Todos ({matches.length})
        </Badge>
        <Badge
          variant={statusFilter === "scheduled" ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setStatusFilter("scheduled")}
        >
          Agendados
        </Badge>
        <Badge
          variant={statusFilter === "live" ? "default" : "outline"}
          className="cursor-pointer bg-red-500/20 text-red-400"
          onClick={() => setStatusFilter("live")}
        >
          <span className="animate-pulse mr-1">●</span> Ao Vivo
        </Badge>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin text-4xl">⚽</div>
          <span className="ml-3 text-zinc-400">Buscando jogos...</span>
        </div>
      ) : (
        <ScrollArea className="h-[500px]">
          <div className="space-y-6">
            {Object.entries(matchesByLeague).map(([leagueId, { leagueName, matches }]) => (
              <div key={leagueId}>
                <h4 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
                  {leagueName}
                  <Badge variant="outline" className="text-xs">
                    {matches.length} jogos
                  </Badge>
                </h4>
                <div className="space-y-2">
                  {matches.map((match) => (
                    <InlineMatchCard
                      key={match.id}
                      match={match}
                      isSelected={selectedMatches.includes(match.id)}
                      onSelect={() => onSelectMatch(match.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}

      {selectedMatches.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[#1e1e2e]">
          <Button
            className="w-full bg-[var(--primary)] text-black hover:brightness-110"
            onClick={async () => {
              try {
                const payload = {
                  matches: matches.filter((m) => selectedMatches.includes(m.id)).map((m) => ({
                    id: m.id,
                    leagueId: m.leagueId,
                    homeTeam: m.homeTeam.name,
                    awayTeam: m.awayTeam.name,
                    odds: m.odds,
                    stats: m.stats,
                    datetime: m.datetime,
                  })),
                };
                const res = await fetch("/api/decision/pre", {
                  method: "POST",
                  headers: { "content-type": "application/json" },
                  body: JSON.stringify(payload),
                });
                const data = await res.json();
                setPicks(Array.isArray(data?.picks) ? data.picks : []);
              } catch {
                setPicks([]);
              }
            }}
          >
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Analisar {selectedMatches.length} jogo(s) selecionado(s)
          </Button>
          {picks.length > 0 && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {picks.map((p, i) => (
                <div key={i} className="p-3 rounded-lg border border-[var(--border)] bg-[#0a0a0f]">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{p.market}</span>
                    <Badge variant="outline">{p.risk ?? "—"}</Badge>
                  </div>
                  <div className="mt-2 text-sm">
                    <div>Prob: {(p.prob * 100).toFixed(1)}%</div>
                    {p.odds && <div>Odd: {p.odds.toFixed(2)}</div>}
                    {p.ev !== undefined && (
                      <div className={p.ev >= 0 ? "text-[var(--primary)]" : "text-[var(--danger)]"}>
                        EV: {(p.ev * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                  {p.reasons && p.reasons.length > 0 && (
                    <div className="mt-2 text-xs muted">{p.reasons.join(" • ")}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function InlineMatchCard({
  match,
  isSelected,
  onSelect,
}: {
  match: Match;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const matchTime = new Date(match.datetime);
  const timeString = matchTime.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      onClick={onSelect}
      className={`p-4 rounded-lg border cursor-pointer transition-all ${
        isSelected ? "bg-purple-500/20 border-purple-500" : "bg-[#0a0a0f] border-[#1e1e2e] hover:border-[#2e2e3e]"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Clock className="h-4 w-4" />
          {timeString}
          {match.status === "live" && (
            <Badge className="bg-red-500 text-white text-xs animate-pulse">AO VIVO</Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          <TrendingUp className="h-4 w-4 text-green-500" />
          <span className="text-sm text-green-400">EV +{Math.round(match.stats.homeWinProb)}%</span>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium">{match.homeTeam.name}</span>
            <div className="flex gap-0.5">
              {match.homeTeam.form.slice(0, 5).map((result, i) => (
                <span
                  key={i}
                  className={`w-4 h-4 rounded-full text-xs flex items-center justify-center ${
                    result === "W" ? "bg-green-500" : result === "D" ? "bg-yellow-500" : "bg-red-500"
                  }`}
                >
                  {result}
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium">{match.awayTeam.name}</span>
            <div className="flex gap-0.5">
              {match.awayTeam.form.slice(0, 5).map((result, i) => (
                <span
                  key={i}
                  className={`w-4 h-4 rounded-full text-xs flex items-center justify-center ${
                    result === "W" ? "bg-green-500" : result === "D" ? "bg-yellow-500" : "bg-red-500"
                  }`}
                >
                  {result}
                </span>
              ))}
            </div>
          </div>
        </div>

        {match.score && (
          <div className="text-2xl font-bold">
            {match.score.home} - {match.score.away}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-[#1a1a24] rounded p-2 text-center">
          <p className="text-xs text-zinc-500">Casa</p>
          <p className="font-bold text-green-400">{match.odds.home?.toFixed(2)}</p>
        </div>
        <div className="bg-[#1a1a24] rounded p-2 text-center">
          <p className="text-xs text-zinc-500">Empate</p>
          <p className="font-bold text-yellow-400">{match.odds.draw?.toFixed(2)}</p>
        </div>
        <div className="bg-[#1a1a24] rounded p-2 text-center">
          <p className="text-xs text-zinc-500">Fora</p>
          <p className="font-bold text-blue-400">{match.odds.away?.toFixed(2)}</p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-500">Prob. Vitória Casa</span>
          <span className="text-green-400">{Math.round(match.stats.homeWinProb)}%</span>
        </div>
        <Progress value={match.stats.homeWinProb} className="h-1" />

        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-500">BTTS (Ambas Marcam)</span>
          <span className="text-purple-400">{Math.round(match.stats.bttsProb)}%</span>
        </div>
        <Progress value={match.stats.bttsProb} className="h-1" />

        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-500">Over 2.5 Gols</span>
          <span className="text-amber-400">{Math.round(match.stats.over25Prob)}%</span>
        </div>
        <Progress value={match.stats.over25Prob} className="h-1" />
        <div className="grid grid-cols-3 gap-2 mt-2">
          <div
            className="bg-[#1a1a24] rounded p-2 text-center"
            title={`λH=${match.stats.lambdaHome ?? "-"} λA=${match.stats.lambdaAway ?? "-"} λT=${match.stats.lambdaTotal ?? "-"}`}
          >
            <p className="text-xs text-zinc-500">Over 0.5</p>
            <p className="text-sm text-amber-300">{match.stats.over05Prob != null ? `${Math.round(match.stats.over05Prob)}%` : "—"}</p>
          </div>
          <div
            className="bg-[#1a1a24] rounded p-2 text-center"
            title={`λH=${match.stats.lambdaHome ?? "-"} λA=${match.stats.lambdaAway ?? "-"} λT=${match.stats.lambdaTotal ?? "-"}`}
          >
            <p className="text-xs text-zinc-500">Over 1.5</p>
            <p className="text-sm text-amber-300">{match.stats.over15Prob != null ? `${Math.round(match.stats.over15Prob)}%` : "—"}</p>
          </div>
          <div
            className="bg-[#1a1a24] rounded p-2 text-center"
            title={`λH=${match.stats.lambdaHome ?? "-"} λA=${match.stats.lambdaAway ?? "-"} λT=${match.stats.lambdaTotal ?? "-"}`}
          >
            <p className="text-xs text-zinc-500">Over 3.5</p>
            <p className="text-sm text-amber-300">{match.stats.over35Prob != null ? `${Math.round(match.stats.over35Prob)}%` : "—"}</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-2">
          <div className="bg-[#1a1a24] rounded p-2 text-center">
            <p className="text-xs text-zinc-500">Posse</p>
            <p className="text-sm">
              {match.stats.homePossession != null && match.stats.awayPossession != null
                ? `${Math.round(match.stats.homePossession)}% / ${Math.round(match.stats.awayPossession)}%`
                : "—"}
            </p>
          </div>
          <div className="bg-[#1a1a24] rounded p-2 text-center">
            <p className="text-xs text-zinc-500">Escanteios/partida</p>
            <p className="text-sm">
              {match.stats.homeCornersPerMatch != null && match.stats.awayCornersPerMatch != null
                ? `${(match.stats.homeCornersPerMatch as number).toFixed(1)} / ${(match.stats.awayCornersPerMatch as number).toFixed(1)}`
                : "—"}
            </p>
          </div>
          <div className="bg-[#1a1a24] rounded p-2 text-center">
            <p className="text-xs text-zinc-500">Cartões/partida</p>
            <p className="text-sm">
              {match.stats.homeCardsPerMatch != null && match.stats.awayCardsPerMatch != null
                ? `${(match.stats.homeCardsPerMatch as number).toFixed(1)} / ${(match.stats.awayCardsPerMatch as number).toFixed(1)}`
                : "—"}
            </p>
          </div>
        </div>
        {match.stats.regime && (
          <div className="mt-2">
            <Badge variant="outline" className="text-xs">Regime {match.stats.regime}</Badge>
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center gap-1 text-xs text-zinc-500">
        <MapPin className="h-3 w-3" />
        {match.venue}
      </div>
    </div>
  );
}

