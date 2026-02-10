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
        // Try fetching from the fixtures endpoint with all leagues
        const res = await fetch(`${PY_BACKEND}/fixtures?leagues=&date=today`, {
          cache: "no-store",
        });
        if (res.ok) {
          const data = await res.json();
          const matches: MatchDetailData[] = data.matches || [];
          const found = matches.find((m) => String(m.id) === String(matchId));
          if (found) {
            setMatch(found);
            setLoading(false);
            return;
          }
        }
      } catch {
        // ignore, fallback below
      }

      // Fallback: use mock data
      setMatch({
        id: matchId,
        homeTeam: "Deportivo Tachira",
        awayTeam: "The Strongest",
        leagueName: "Copa Libertadores",
        datetime: new Date().toISOString(),
        stadium: "Estadio Polideportivo de Pueblo Nuevo",
        status: "scheduled",
        odds: {
          home: 1.66,
          draw: 3.6,
          away: 4.75,
          over25: 2.07,
          under25: 1.72,
          bttsYes: 2.0,
          bttsNo: 1.78,
        },
        stats: {
          homeWinProb: 38.5,
          drawProb: 28.3,
          awayWinProb: 33.2,
          avgGoals: 2.67,
          over25Prob: 65.8,
          bttsProb: 58.4,
          lambdaHome: 1.45,
          lambdaAway: 1.22,
          lambdaTotal: 2.67,
          homePossession: 54,
          awayPossession: 46,
          leagueRegime: "NORMAL",
          status: "SAFE",
        },
        h2h: {
          totalMatches: 4,
          homeWins: 2,
          draws: 1,
          awayWins: 1,
          avgGoals: 2.5,
        },
        homeForm: ["W", "D", "W", "L", "W"],
        awayForm: ["W", "W", "D", "W", "L"],
        ratings: { home: 6.8, away: 6.2 },
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
