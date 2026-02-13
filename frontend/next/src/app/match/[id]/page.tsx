"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import MatchDetailCard, {
  type MatchDetailData,
  type AIAnalysis,
} from "@/components/MatchDetailCard";

const PY_BACKEND = process.env.NEXT_PUBLIC_PY_BACKEND_URL || "http://127.0.0.1:5001";

/**
 * Maps raw fixture data from the Python backend into the MatchDetailData
 * shape expected by the new MatchDetailCard component.
 */
function mapFixtureToDetail(raw: Record<string, unknown>, matchId: string): MatchDetailData {
  const rawOdds = (raw.odds ?? {}) as Record<string, number>;
  return {
    id: String(raw.id ?? matchId),
    league: (raw.leagueName as string) ?? "",
    season: (raw.season as string) ?? undefined,
    homeTeam: (raw.homeTeam as string) ?? "",
    awayTeam: (raw.awayTeam as string) ?? "",
    startTime: (raw.datetime as string) ?? undefined,
    status: (raw.status as "scheduled" | "live" | "finished") ?? "scheduled",
    venue: raw.stadium
      ? { name: raw.stadium as string }
      : undefined,
    odds: {
      home: rawOdds.home,
      draw: rawOdds.draw,
      away: rawOdds.away,
    },
    doubleChance:
      rawOdds.home && rawOdds.draw && rawOdds.away
        ? {
            homeOrDraw: parseFloat((1 / (1 / rawOdds.home + 1 / rawOdds.draw)).toFixed(2)),
            homeOrAway: parseFloat((1 / (1 / rawOdds.home + 1 / rawOdds.away)).toFixed(2)),
            drawOrAway: parseFloat((1 / (1 / rawOdds.draw + 1 / rawOdds.away)).toFixed(2)),
          }
        : undefined,
    btts:
      rawOdds.bttsYes || rawOdds.bttsNo
        ? { yes: rawOdds.bttsYes, no: rawOdds.bttsNo }
        : undefined,
    round: (raw.round as string) ?? undefined,
  };
}

export default function MatchDetailPage() {
  const params = useParams();
  const matchId = params?.id as string;

  const [match, setMatch] = useState<MatchDetailData | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch match data from the backend fixtures endpoint
  useEffect(() => {
    if (!matchId) return;

    async function fetchMatch() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${PY_BACKEND}/fixtures?leagues=&date=today`, {
          cache: "no-store",
        });
        if (res.ok) {
          const data = await res.json();
          const matches = (data.matches || []) as Record<string, unknown>[];
          const found = matches.find((m) => String(m.id) === String(matchId));
          if (found) {
            setMatch(mapFixtureToDetail(found, matchId));
            setLoading(false);
            return;
          }
        }
      } catch {
        // ignore, fallback below
      }

      // Fallback: mock data matching the new interface
      const kickoff = new Date();
      kickoff.setHours(kickoff.getHours() + 3);
      setMatch({
        id: matchId,
        league: "Copa Libertadores",
        season: "2026",
        homeTeam: "Deportivo Tachira",
        awayTeam: "The Strongest",
        startTime: kickoff.toISOString(),
        status: "scheduled",
        venue: {
          name: "Estadio Polideportivo de Pueblo Nuevo",
          capacity: 38755,
        },
        odds: { home: 1.66, draw: 3.6, away: 4.75 },
        doubleChance: {
          homeOrDraw: 1.14,
          homeOrAway: 1.23,
          drawOrAway: 2.05,
        },
        btts: { yes: 2.0, no: 1.78 },
        round: "Fase de Grupos - Rodada 1",
      });
      setLoading(false);
    }

    fetchMatch();
  }, [matchId]);

  // Fetch AI analysis
  const fetchAI = useCallback(
    async (regenerate = false) => {
      if (!matchId) return;
      setAiLoading(true);
      try {
        const url = `/api/ai/match/${encodeURIComponent(matchId)}/analysis`;
        const res = await fetch(url, {
          method: regenerate ? "POST" : "GET",
          cache: "no-store",
        });
        if (res.ok) {
          const data: AIAnalysis = await res.json();
          setAiAnalysis(data);
        }
      } catch {
        // AI analysis is optional
      } finally {
        setAiLoading(false);
      }
    },
    [matchId],
  );

  useEffect(() => {
    fetchAI(false);
  }, [fetchAI]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex items-center gap-3 text-[#00ff88]">
          <Loader2 size={24} className="animate-spin" />
          <span>Carregando jogo...</span>
        </div>
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center gap-4 text-white">
        <div className="text-lg text-red-400">{error || "Jogo nao encontrado"}</div>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 text-[#00ff88] hover:underline"
        >
          <ArrowLeft size={16} />
          Voltar ao dashboard
        </Link>
      </div>
    );
  }

  const combined: MatchDetailData = {
    ...match,
    aiAnalysis: aiAnalysis ?? undefined,
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-4 md:p-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-sm text-[#888] hover:text-[#00ff88] transition-colors"
          >
            <ArrowLeft size={14} />
            Voltar ao dashboard
          </Link>
        </div>

        <MatchDetailCard
          match={combined}
          aiLoading={aiLoading}
          onRegenerate={() => fetchAI(true)}
        />
      </div>
    </div>
  );
}
