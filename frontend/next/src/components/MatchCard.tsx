import React from "react";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { format, parseISO } from "date-fns";

export type Match = {
  id: string;
  leagueId: string;
  leagueName: string;
  homeTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  awayTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  datetime: string;
  venue: string;
  status: "scheduled" | "live" | "finished" | "postponed";
  score?: {
    home: number;
    away: number;
    halftime?: { home: number; away: number };
  };
  odds: {
    home: number;
    draw: number;
    away: number;
    over25: number;
    under25: number;
    bttsYes: number;
    bttsNo: number;
  };
  stats: {
    homeWinProb: number;
    drawProb: number;
    awayWinProb: number;
    avgGoals: number;
    bttsProb: number;
    over25Prob: number;
    over05Prob?: number;
    over15Prob?: number;
    over35Prob?: number;
    homePossession?: number;
    awayPossession?: number;
    homeCornersPerMatch?: number;
    awayCornersPerMatch?: number;
    homeCardsPerMatch?: number;
    awayCardsPerMatch?: number;
    leagueAvgCorners?: number;
    leagueAvgCards?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    lambdaTotal?: number;
    regime?: string;
  };
  h2h: {
    totalMatches: number;
    homeWins: number;
    draws: number;
    awayWins: number;
    avgGoals: number;
  };
  source: "whoscored" | "footystats" | "packball";
  lastUpdated: string;
};

type Props = {
  data: Match;
  selected?: boolean;
  onSelectChange?: (id: string, selected: boolean) => void;
  onAnalyze?: (id: string) => void;
};

function TeamCell({
  name,
  logo,
  form,
  rating,
  align = "left",
}: {
  name: string;
  logo: string;
  form: string[];
  rating: number;
  align?: "left" | "right";
}) {
  const isRight = align === "right";
  return (
    <div className={`flex items-center ${isRight ? "justify-end" : "justify-start"} gap-3`}>
      <img
        src={logo}
        alt={name}
        className="h-8 w-8 rounded-full border border-[var(--border)] object-cover"
      />
      <div className={`${isRight ? "text-right" : "text-left"}`}>
        <div className="font-semibold">{name}</div>
        <div className="flex items-center gap-1">
          {form.map((f, i) => {
            const map: Record<string, string> = {
              W: "bg-[var(--primary)] text-black",
              D: "bg-[var(--warning)] text-black",
              L: "bg-[var(--danger)] text-white",
            };
            return (
              <span
                key={`${name}-form-${i}`}
                className={`badge ${map[f] ?? "bg-[var(--card)] text-[var(--text)] border border-[var(--border)]"}`}
              >
                {f}
              </span>
            );
          })}
        </div>
      </div>
      <Badge variant="accent">{rating.toFixed(1)}</Badge>
    </div>
  );
}

function ProbRow({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "success" | "warning" | "danger" | "info" | "accent";
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 muted">{label}</div>
      <div className="flex-1">
        <Progress value={Math.round(value)} color={color} />
      </div>
      <div className="w-12 text-right">{Math.round(value)}%</div>
    </div>
  );
}

export default function MatchCard({ data, selected, onSelectChange, onAnalyze }: Props) {
  const dt = parseISO(data.datetime);
  const dtLabel = isNaN(dt.getTime()) ? data.datetime : format(dt, "dd/MM HH:mm");
  const last = parseISO(data.lastUpdated);
  const lastLabel = isNaN(last.getTime()) ? data.lastUpdated : format(last, "dd/MM HH:mm");
  const statusColor =
    data.status === "live"
      ? "success"
      : data.status === "finished"
      ? "info"
      : data.status === "postponed"
      ? "warning"
      : "default";
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold">{data.leagueName}</span>
            <Badge variant={statusColor as any}>{data.status}</Badge>
            <Badge variant="default">{data.source}</Badge>
          </div>
          <div className="muted text-xs">Atualizado: {lastLabel}</div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 items-center gap-4">
          <TeamCell
            name={data.homeTeam.name}
            logo={data.homeTeam.logo}
            form={data.homeTeam.form}
            rating={data.homeTeam.rating}
            align="left"
          />
          <div className="text-center">
            <div className="text-sm muted">{data.venue}</div>
            <div className="text-xl font-semibold">{dtLabel}</div>
            {data.score && (
              <div className="mt-1">
                <Badge variant="accent">
                  {data.score.home} - {data.score.away}
                </Badge>
                {data.score.halftime && (
                  <span className="muted text-xs ml-2">
                    HT {data.score.halftime.home}-{data.score.halftime.away}
                  </span>
                )}
              </div>
            )}
          </div>
          <TeamCell
            name={data.awayTeam.name}
            logo={data.awayTeam.logo}
            form={data.awayTeam.form}
            rating={data.awayTeam.rating}
            align="right"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="font-medium">Odds</div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="default">1 {data.odds.home?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">X {data.odds.draw?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">2 {data.odds.away?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">O2.5 {data.odds.over25?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">U2.5 {data.odds.under25?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">BTTS S {data.odds.bttsYes?.toFixed(2) ?? "-"}</Badge>
              <Badge variant="default">BTTS N {data.odds.bttsNo?.toFixed(2) ?? "-"}</Badge>
            </div>
          </div>
          <div className="space-y-2">
            <div className="font-medium">Probabilidades</div>
            <div className="space-y-2">
              <ProbRow label="Home" value={data.stats.homeWinProb} color="success" />
              <ProbRow label="Draw" value={data.stats.drawProb} color="warning" />
              <ProbRow label="Away" value={data.stats.awayWinProb} color="danger" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="font-medium">Indicadores</div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="accent">μ {data.stats.avgGoals.toFixed(2)}</Badge>
              <Badge variant="accent">BTTS {(Math.round(data.stats.bttsProb))}%</Badge>
              <Badge variant="accent">O2.5 {(Math.round(data.stats.over25Prob))}%</Badge>
            </div>
            <div className="mt-2 text-xs muted">
              H2H {data.h2h.totalMatches} • {data.h2h.homeWins}–{data.h2h.awayWins}–{data.h2h.draws} • μ {data.h2h.avgGoals.toFixed(2)}
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!selected}
                onChange={(e) => onSelectChange?.(data.id, e.target.checked)}
              />
              <span className="muted text-sm">Selecionar para análise</span>
            </label>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="success" onClick={() => onAnalyze?.(data.id)}>
              Analisar
            </Button>
            <Button variant="ghost">Favoritar</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

