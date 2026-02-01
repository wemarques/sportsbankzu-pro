"use client";

import React, { useState } from "react";
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
} from "lucide-react";

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

interface Match {
  id: number;
  league: string;
  leagueFlag?: string;
  time: string;
  home: Team;
  away: Team;
  prediction: MatchPrediction;
  mistral: MistralReview;
  featured?: boolean;
}

/* ========================================
   Dados mock (substituir por API real)
   ======================================== */
const MOCK_MATCHES: Match[] = [
  {
    id: 1,
    league: "ENGLAND \u2022 PREMIER LEAGUE",
    leagueFlag: "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67\uDB40\uDC7F",
    time: "11:00",
    home: { name: "MUN", logo: "https://placehold.co/40x40/cc0000/white?text=MU" },
    away: { name: "FUL", logo: "https://placehold.co/40x40/ffffff/black?text=FU" },
    prediction: { tip: "Home Win (1)", odds: "1.57" },
    mistral: {
      status: "CONFIRMED",
      auditOdds: "1.62",
      explanation:
        "System under-calculated the impact of home advantage in the opening fixture. Final value adjusted for confirmed starting line-up strength.",
      color: "purple",
    },
  },
  {
    id: 2,
    league: "ENGLAND \u2022 PREMIER LEAGUE",
    leagueFlag: "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67\uDB40\uDC7F",
    time: "11:00",
    home: { name: "AVL", logo: "https://placehold.co/40x40/670e36/white?text=AV" },
    away: { name: "BRE", logo: "https://placehold.co/40x40/e30613/white?text=BR" },
    prediction: { tip: "Home Win (1)", odds: "2.10" },
    mistral: {
      status: "ADJUSTED",
      auditOdds: "2.05",
      explanation:
        "System failed to account for mid-week travel fatigue. Regression analysis suggests a higher draw probability than calculated.",
      color: "orange",
    },
    featured: true,
  },
  {
    id: 3,
    league: "SPAIN \u2022 LA LIGA",
    leagueFlag: "\uD83C\uDDEA\uD83C\uDDF8",
    time: "16:00",
    home: { name: "RMA", logo: "https://placehold.co/40x40/ffffff/d4af37?text=RM" },
    away: { name: "ATM", logo: "https://placehold.co/40x40/cb3524/white?text=AT" },
    prediction: { tip: "Over 2.5", odds: "1.85" },
    mistral: {
      status: "CONFIRMED",
      auditOdds: "1.88",
      explanation:
        "Historical H2H data supports high-scoring encounter. Both teams in aggressive tactical setups this season. Lambda total = 2.8.",
      color: "purple",
    },
  },
  {
    id: 4,
    league: "BRAZIL \u2022 S\u00c9RIE A",
    leagueFlag: "\uD83C\uDDE7\uD83C\uDDF7",
    time: "20:00",
    home: { name: "FLA", logo: "https://placehold.co/40x40/cc0000/black?text=FL" },
    away: { name: "PAL", logo: "https://placehold.co/40x40/006633/white?text=PA" },
    prediction: { tip: "BTTS Yes", odds: "1.72" },
    mistral: {
      status: "ADJUSTED",
      auditOdds: "1.68",
      explanation:
        "Palmeiras missing key defender increases BTTS probability. System model didn't account for suspension data from last round.",
      color: "orange",
    },
    featured: true,
  },
];

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

function MatchCard({ match }: { match: Match }) {
  const [expanded, setExpanded] = useState(false);
  const mistralCardClass =
    match.mistral.status === "CONFIRMED" ? "card-mistral-confirmed" : "card-mistral-adjusted";
  const accentColor =
    match.mistral.status === "CONFIRMED" ? "text-purple-400" : "text-orange-400";

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
            : match.mistral.explanation.slice(0, 80) + (match.mistral.explanation.length > 80 ? "..." : "")}
        </div>
        {match.mistral.explanation.length > 80 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[11px] text-gray-500 hover:text-gray-300 mt-1 flex items-center gap-1 transition-colors"
          >
            {expanded ? "Ver menos" : "Ver mais"}
            <ChevronDown size={12} className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
          </button>
        )}
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
  const tabs = ["Predictions", "Top Value", "Mistral Picks"];

  // Agrupar jogos por liga
  const grouped = MOCK_MATCHES.reduce<Record<string, Match[]>>((acc, m) => {
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
        </div>
        <div className="flex gap-3">
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

      {/* Match List agrupada por liga */}
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
              <TrendingUp size={14} />
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

      {/* Floating Filter Button */}
      <button className="fixed bottom-24 right-6 w-14 h-14 bg-[#9d50ff] rounded-2xl flex items-center justify-center shadow-lg shadow-purple-900/20 z-20 hover:bg-[#b06aff] transition-colors">
        <Filter className="text-white" />
      </button>

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
