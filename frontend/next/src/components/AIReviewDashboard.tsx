"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  Bell,
  Star,
  TrendingUp,
  Cpu,
  Layout,
  Trophy,
  BarChart3,
  User,
  Filter,
  ChevronDown,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { AVAILABLE_LEAGUES, type League } from "@/lib/leagues";

/* ========================================
   Tipos
   ======================================== */
interface Team {
  name: string;
  logo: string;
}

interface MistralReview {
  status: "CONFIRMED" | "ADJUSTED" | "REJECTED";
  auditOdds: string;
  explanation: string;
  color: "purple" | "orange" | "red";
}

interface MatchPrediction {
  tip: string;
  odds: string;
}

interface DisplayMatch {
  id: string;
  league: string;
  leagueId: string;
  leagueFlag?: string;
  time: string;
  home: Team;
  away: Team;
  prediction: MatchPrediction;
  mistral: MistralReview;
  featured?: boolean;
}

/* ========================================
   Utilitários de transformação
   ======================================== */

function getBestTip(
  stats: Record<string, number>,
  odds: Record<string, number>,
): { tip: string; odds: number; fairOdds: number } {
  const markets = [
    { tip: "Home Win (1)", prob: stats.homeWinProb ?? 0, marketOdds: odds.home ?? 0 },
    { tip: "Draw (X)", prob: stats.drawProb ?? 0, marketOdds: odds.draw ?? 0 },
    { tip: "Away Win (2)", prob: stats.awayWinProb ?? 0, marketOdds: odds.away ?? 0 },
    { tip: "Over 2.5", prob: stats.over25Prob ?? 0, marketOdds: odds.over25 ?? 0 },
    { tip: "BTTS Yes", prob: stats.bttsProb ?? 0, marketOdds: odds.bttsYes ?? 0 },
  ];

  let best = markets[0];
  let bestEdge = -Infinity;
  for (const m of markets) {
    if (m.prob > 0 && m.marketOdds > 0) {
      const edge = (m.marketOdds * m.prob) / 100 - 1;
      if (edge > bestEdge) {
        bestEdge = edge;
        best = m;
      }
    }
  }

  return {
    tip: best.tip,
    odds: best.marketOdds,
    fairOdds: best.prob > 0 ? 100 / best.prob : 0,
  };
}

function buildAIReview(
  marketOdds: number,
  fairOdds: number,
  stats: Record<string, number | string | undefined>,
  h2h: Record<string, number> | undefined,
): MistralReview {
  const diff = fairOdds > 0 ? Math.abs(marketOdds - fairOdds) / fairOdds : 0;

  let status: MistralReview["status"];
  let color: MistralReview["color"];

  if (diff <= 0.05) {
    status = "CONFIRMED";
    color = "purple";
  } else if (diff <= 0.15) {
    status = "ADJUSTED";
    color = "orange";
  } else {
    status = "REJECTED";
    color = "red";
  }

  const lambdaInfo =
    stats.lambdaTotal != null ? ` Lambda total = ${Number(stats.lambdaTotal).toFixed(1)}.` : "";
  const regimeInfo = stats.regime ? ` Regime: ${stats.regime}.` : "";
  const h2hInfo =
    h2h && h2h.totalMatches > 0
      ? ` H2H: ${h2h.totalMatches} jogos, média ${Number(h2h.avgGoals).toFixed(1)} gols.`
      : "";

  let explanation: string;
  if (status === "CONFIRMED") {
    explanation = `Market odds align with system model (fair: ${fairOdds.toFixed(2)} vs market: ${marketOdds.toFixed(2)}).${lambdaInfo}${h2hInfo}${regimeInfo}`;
  } else if (status === "ADJUSTED") {
    explanation = `Mild divergence detected between model and market (fair: ${fairOdds.toFixed(2)} vs market: ${marketOdds.toFixed(2)}). Consider external factors.${lambdaInfo}${h2hInfo}${regimeInfo}`;
  } else {
    explanation = `Significant divergence from market pricing (fair: ${fairOdds.toFixed(2)} vs market: ${marketOdds.toFixed(2)}). Model suggests caution.${lambdaInfo}${h2hInfo}${regimeInfo}`;
  }

  return { status, auditOdds: fairOdds.toFixed(2), explanation, color };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function transformAPIMatch(apiMatch: any, league: League): DisplayMatch {
  const stats = apiMatch.stats || {};
  const odds = apiMatch.odds || {};
  const h2h = apiMatch.h2h;

  const best = getBestTip(stats, odds);
  const review = buildAIReview(best.odds, best.fairOdds, stats, h2h);

  let timeStr = "--:--";
  try {
    const dt = new Date(apiMatch.datetime);
    if (!isNaN(dt.getTime())) {
      timeStr = dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    }
  } catch {
    /* fallback */
  }

  const edge = best.odds > 0 && best.fairOdds > 0 ? best.odds / best.fairOdds - 1 : 0;

  const homeName = apiMatch.homeTeam?.name || apiMatch.home?.name || "HOME";
  const awayName = apiMatch.awayTeam?.name || apiMatch.away?.name || "AWAY";

  return {
    id: apiMatch.id || `${homeName}-${awayName}-${apiMatch.datetime || ""}`,
    league: `${league.country.toUpperCase()} \u2022 ${league.name.toUpperCase()}`,
    leagueId: league.id,
    leagueFlag: league.countryFlag,
    time: timeStr,
    home: {
      name: homeName.length > 3 ? homeName.slice(0, 3).toUpperCase() : homeName.toUpperCase(),
      logo:
        apiMatch.homeTeam?.logo ||
        apiMatch.home?.logo ||
        `https://placehold.co/40x40/1a1a2e/white?text=${homeName.slice(0, 2).toUpperCase()}`,
    },
    away: {
      name: awayName.length > 3 ? awayName.slice(0, 3).toUpperCase() : awayName.toUpperCase(),
      logo:
        apiMatch.awayTeam?.logo ||
        apiMatch.away?.logo ||
        `https://placehold.co/40x40/1a1a2e/white?text=${awayName.slice(0, 2).toUpperCase()}`,
    },
    prediction: {
      tip: best.tip,
      odds: best.odds > 0 ? best.odds.toFixed(2) : "-",
    },
    mistral: review,
    featured: edge > 0.1,
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/* ========================================
   Sub-componentes
   ======================================== */

function StatusBadge({ status, auditOdds }: { status: string; auditOdds: string }) {
  const styles: Record<string, string> = {
    CONFIRMED: "bg-purple-900/50 text-purple-300",
    ADJUSTED: "bg-orange-900/50 text-orange-300",
    REJECTED: "bg-red-900/50 text-red-300",
  };
  return (
    <div className={`px-2 py-0.5 rounded text-[10px] font-bold ${styles[status] ?? styles.ADJUSTED}`}>
      {status}: {auditOdds}
    </div>
  );
}

function MatchCard({ match }: { match: DisplayMatch }) {
  const [expanded, setExpanded] = useState(false);
  const mistralCardClass =
    match.mistral.status === "CONFIRMED"
      ? "card-mistral-confirmed"
      : match.mistral.status === "REJECTED"
        ? "card-mistral-rejected"
        : "card-mistral-adjusted";
  const accentColor =
    match.mistral.status === "CONFIRMED"
      ? "text-purple-400"
      : match.mistral.status === "REJECTED"
        ? "text-red-400"
        : "text-orange-400";

  return (
    <div className="relative animate-card">
      {/* Info do jogo */}
      <div className="flex items-center justify-between mb-3 px-2">
        <span className="text-xs font-mono text-gray-400">{match.time}</span>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <img src={match.home.logo} className="w-6 h-6 rounded-md" alt={match.home.name} />
            <span className="font-bold text-sm">{match.home.name}</span>
          </div>
          <span className="text-[10px] text-gray-600 font-bold">VS</span>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm">{match.away.name}</span>
            <img src={match.away.logo} className="w-6 h-6 rounded-md" alt={match.away.name} />
          </div>
        </div>
        <Star
          size={18}
          className={match.featured ? "text-[#00df82] fill-[#00df82]" : "text-gray-600"}
        />
      </div>

      {/* Card System Prediction */}
      <div className="card-system rounded-xl p-4 mb-2">
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center gap-2 text-[10px] font-bold text-blue-400 uppercase tracking-wider">
            <Layout size={12} />
            System Prediction
          </div>
          <span className="text-blue-400 font-bold odds-value">{match.prediction.odds}</span>
        </div>
        <div className="text-lg font-bold">
          System Tip: <span className="text-white">{match.prediction.tip}</span>
        </div>
      </div>

      {/* Card Mistral AI Review */}
      <div className={`${mistralCardClass} rounded-xl p-4`}>
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center gap-2 text-[10px] font-bold text-purple-400 uppercase tracking-wider">
            <Cpu size={12} />
            Mistral AI Review
          </div>
          <StatusBadge status={match.mistral.status} auditOdds={match.mistral.auditOdds} />
        </div>
        <div className="text-sm leading-relaxed text-gray-300">
          <span className={`font-black mr-1 ${accentColor}`}>{match.mistral.status}:</span>
          {expanded
            ? match.mistral.explanation
            : match.mistral.explanation.slice(0, 80) +
              (match.mistral.explanation.length > 80 ? "..." : "")}
        </div>
        {match.mistral.explanation.length > 80 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[11px] text-gray-500 hover:text-gray-300 mt-1 flex items-center gap-1 transition-colors"
          >
            {expanded ? "Ver menos" : "Ver mais"}
            <ChevronDown
              size={12}
              className={`transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        )}
      </div>
    </div>
  );
}

function LeagueFilterPanel({
  selectedLeagues,
  onToggle,
  onSelectAll,
  onDeselectAll,
  onClose,
}: {
  selectedLeagues: Set<string>;
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-end">
      <div className="bg-[#141414] w-full max-h-[70vh] rounded-t-3xl p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Filtrar Ligas ({selectedLeagues.size}/22)</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-[#252525] rounded-full transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div className="flex gap-2 mb-4">
          <button
            onClick={onSelectAll}
            className="px-3 py-1.5 bg-[#9d50ff]/20 border border-[#9d50ff]/40 rounded-lg text-xs text-purple-300 hover:bg-[#9d50ff]/30 transition-colors"
          >
            Selecionar Todas
          </button>
          <button
            onClick={onDeselectAll}
            className="px-3 py-1.5 bg-[#1a1a1a] rounded-lg text-xs text-gray-400 hover:bg-[#252525] transition-colors"
          >
            Limpar Seleção
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {AVAILABLE_LEAGUES.map((league) => (
            <button
              key={league.id}
              onClick={() => onToggle(league.id)}
              className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
                selectedLeagues.has(league.id)
                  ? "bg-[#9d50ff]/20 border border-[#9d50ff]/40"
                  : "bg-[#1a1a1a] border border-transparent hover:border-gray-700"
              }`}
            >
              <span className="text-lg">{league.countryFlag}</span>
              <div>
                <div className="text-sm font-semibold">{league.name}</div>
                <div className="text-[10px] text-gray-500">{league.country}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ========================================
   Componente Principal
   ======================================== */

export default function AIReviewDashboard() {
  const [activeTab, setActiveTab] = useState("Predictions");
  const [activeNav, setActiveNav] = useState("AI AUDIT");
  const [matches, setMatches] = useState<DisplayMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilter, setShowFilter] = useState(false);
  const [selectedLeagues, setSelectedLeagues] = useState<Set<string>>(
    () => new Set(AVAILABLE_LEAGUES.map((l) => l.id)),
  );

  const tabs = ["Predictions", "Top Value", "Mistral Picks"];

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const leagueIds = Array.from(selectedLeagues).join(",");
      const today = new Date().toISOString().split("T")[0];
      const res = await fetch(
        `/api/matches/fetch?leagues=${encodeURIComponent(leagueIds)}&date=${today}`,
        { cache: "no-store" },
      );
      const data = await res.json();
      const rawMatches: unknown[] = data.matches || data.fixtures || [];

      if (!Array.isArray(rawMatches)) {
        setMatches([]);
        setLoading(false);
        return;
      }

      const leagueMap = new Map(AVAILABLE_LEAGUES.map((l) => [l.id, l]));

      /* eslint-disable @typescript-eslint/no-explicit-any */
      const transformed: DisplayMatch[] = rawMatches
        .filter((m: any) => m && (m.homeTeam || m.home))
        .map((m: any) => {
          const leagueId = m.leagueId || m.league_id || "";
          const league: League = leagueMap.get(leagueId) || {
            id: leagueId,
            name: m.leagueName || m.league_name || leagueId,
            country: m.country || "",
            countryFlag: "\u26BD",
            logo: "",
            season: "",
            totalMatches: 0,
            matchesToday: 0,
            apiEndpoints: { whoscored: "", footystats: "", packball: "" },
          };
          return transformAPIMatch(m, league);
        });
      /* eslint-enable @typescript-eslint/no-explicit-any */

      setMatches(transformed);
    } catch (err) {
      console.error("Error fetching matches:", err);
      setError("Erro ao carregar jogos. Verifique a conexão com o backend.");
      setMatches([]);
    }
    setLoading(false);
  }, [selectedLeagues]);

  useEffect(() => {
    fetchMatches();
  }, [fetchMatches]);

  const toggleLeague = (id: string) => {
    setSelectedLeagues((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllLeagues = () => {
    setSelectedLeagues(new Set(AVAILABLE_LEAGUES.map((l) => l.id)));
  };

  const deselectAllLeagues = () => {
    setSelectedLeagues(new Set());
  };

  // Filter matches based on active tab
  const filteredMatches = matches.filter((m) => {
    if (activeTab === "Top Value") return m.featured;
    if (activeTab === "Mistral Picks") return m.mistral.status === "CONFIRMED";
    return true;
  });

  // Group by league
  const grouped = filteredMatches.reduce<Record<string, DisplayMatch[]>>((acc, m) => {
    if (!acc[m.league]) acc[m.league] = [];
    acc[m.league].push(m);
    return acc;
  }, {});

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-gray-100 font-sans pb-24">
      {/* Header */}
      <header className="p-4 flex items-center justify-between sticky top-0 glass-effect z-10">
        <div className="flex items-center gap-2">
          <div className="bg-[#00df82] p-1.5 rounded-lg">
            <TrendingUp size={20} className="text-black" />
          </div>
          <h1 className="text-xl font-bold tracking-tight">AI Audit</h1>
          <span className="text-[10px] bg-[#1a1a1a] text-gray-400 px-2 py-0.5 rounded-full">
            {selectedLeagues.size} ligas
          </span>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchMatches}
            className="p-2 bg-[#1a1a1a] rounded-full hover:bg-[#252525] transition-colors"
            title="Recarregar"
          >
            <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
          </button>
          <button className="p-2 bg-[#1a1a1a] rounded-full hover:bg-[#252525] transition-colors">
            <Search size={20} />
          </button>
          <button className="p-2 bg-[#1a1a1a] rounded-full hover:bg-[#252525] transition-colors relative">
            <Bell size={20} />
            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border border-black pulse-active" />
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex px-4 gap-2 mb-6 overflow-x-auto no-scrollbar">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-full whitespace-nowrap text-sm font-semibold transition-all ${
              activeTab === tab
                ? "bg-[#00df82] text-black"
                : "bg-[#1a1a1a] text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Stats bar */}
      <div className="px-4 mb-6 flex gap-3 overflow-x-auto no-scrollbar">
        <div className="bg-[#1a1a1a] rounded-xl px-4 py-2 flex items-center gap-2 whitespace-nowrap">
          <span className="text-[10px] text-gray-500 uppercase">Total</span>
          <span className="text-sm font-bold">{matches.length}</span>
        </div>
        <div className="bg-[#1a1a1a] rounded-xl px-4 py-2 flex items-center gap-2 whitespace-nowrap">
          <span className="w-2 h-2 bg-purple-500 rounded-full" />
          <span className="text-[10px] text-gray-500 uppercase">Confirmed</span>
          <span className="text-sm font-bold text-purple-400">
            {matches.filter((m) => m.mistral.status === "CONFIRMED").length}
          </span>
        </div>
        <div className="bg-[#1a1a1a] rounded-xl px-4 py-2 flex items-center gap-2 whitespace-nowrap">
          <span className="w-2 h-2 bg-orange-500 rounded-full" />
          <span className="text-[10px] text-gray-500 uppercase">Adjusted</span>
          <span className="text-sm font-bold text-orange-400">
            {matches.filter((m) => m.mistral.status === "ADJUSTED").length}
          </span>
        </div>
        <div className="bg-[#1a1a1a] rounded-xl px-4 py-2 flex items-center gap-2 whitespace-nowrap">
          <span className="w-2 h-2 bg-red-500 rounded-full" />
          <span className="text-[10px] text-gray-500 uppercase">Rejected</span>
          <span className="text-sm font-bold text-red-400">
            {matches.filter((m) => m.mistral.status === "REJECTED").length}
          </span>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 size={40} className="animate-spin text-[#9d50ff]" />
          <p className="text-gray-400 text-sm">
            Carregando jogos de {selectedLeagues.size} ligas...
          </p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="px-4">
          <div className="bg-red-900/20 border border-red-900/40 rounded-xl p-4 text-center">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={fetchMatches}
              className="mt-3 px-4 py-2 bg-red-900/30 rounded-lg text-sm text-red-300 hover:bg-red-900/50 transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filteredMatches.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Trophy size={40} className="text-gray-600" />
          <p className="text-gray-500 text-sm text-center px-8">
            {matches.length === 0
              ? "Nenhum jogo encontrado para as ligas selecionadas."
              : `Nenhum jogo na aba "${activeTab}". Tente "Predictions" para ver todos.`}
          </p>
        </div>
      )}

      {/* Match List agrupada por liga */}
      {!loading && !error && filteredMatches.length > 0 && (
        <main className="px-4 space-y-8">
          {Object.entries(grouped).map(([league, leagueMatches]) => (
            <div key={league}>
              {/* Header da liga */}
              <div className="flex items-center justify-between mb-4 text-xs font-bold text-gray-500 tracking-widest uppercase">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 bg-blue-600 rounded-sm flex items-center justify-center text-[10px]">
                    {leagueMatches[0]?.leagueFlag ?? "\u26BD"}
                  </span>
                  {league}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-600 font-normal">
                    {leagueMatches.length} {leagueMatches.length === 1 ? "jogo" : "jogos"}
                  </span>
                  <TrendingUp size={14} />
                </div>
              </div>

              {/* Cards dos jogos */}
              <div className="space-y-6">
                {leagueMatches.map((match) => (
                  <MatchCard key={match.id} match={match} />
                ))}
              </div>
            </div>
          ))}
        </main>
      )}

      {/* Floating Filter Button */}
      <button
        onClick={() => setShowFilter(true)}
        className="fixed bottom-24 right-6 w-14 h-14 bg-[#9d50ff] rounded-2xl flex items-center justify-center shadow-lg shadow-purple-900/20 z-20 hover:bg-[#b06aff] transition-colors"
      >
        <Filter className="text-white" />
      </button>

      {/* League Filter Panel */}
      {showFilter && (
        <LeagueFilterPanel
          selectedLeagues={selectedLeagues}
          onToggle={toggleLeague}
          onSelectAll={selectAllLeagues}
          onDeselectAll={deselectAllLeagues}
          onClose={() => setShowFilter(false)}
        />
      )}

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 glass-effect px-6 py-3 flex justify-between items-center z-30">
        {[
          { icon: Layout, label: "HOME" },
          { icon: Trophy, label: "LEAGUES" },
          { icon: Cpu, label: "AI AUDIT", active: true },
          { icon: BarChart3, label: "TIPS" },
          { icon: User, label: "PROFILE" },
        ].map(({ icon: Icon, label, active }) => (
          <button
            key={label}
            onClick={() => setActiveNav(label)}
            className={`flex flex-col items-center gap-1 transition-colors ${
              activeNav === label ? "text-[#9d50ff]" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <div className="relative">
              <Icon size={22} />
              {active && (
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-[#00df82] rounded-full border-2 border-[#0d0d0d] pulse-active" />
              )}
            </div>
            <span
              className={`text-[10px] ${activeNav === label ? "font-bold tracking-tighter" : "font-medium"}`}
            >
              {label}
            </span>
          </button>
        ))}
      </nav>
    </div>
  );
}
