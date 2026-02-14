"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Search,
  Bell,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  Star,
  ArrowUpDown,
  Loader2,
} from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AVAILABLE_LEAGUES } from "@/lib/leagues";
import type { Match } from "@/components/MatchCard";

const MARKET_TABS = [
  { id: "cotacoes", label: "COTACOES" },
  { id: "1x2", label: "1X2" },
  { id: "dupla-chance", label: "Dupla Chance" },
  { id: "btts", label: "BTTS" },
  { id: "gols", label: "Gols" },
  { id: "cartoes", label: "Cartoes" },
  { id: "escanteios", label: "Escanteios" },
];

const BOTTOM_TABS = [
  { id: "destaques", label: "Destaques" },
  { id: "radar", label: "Radar Esportivo" },
  { id: "bots", label: "ST Bots" },
];

function formatDate(date: Date): string {
  return date.toLocaleDateString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
  });
}

export default function Page() {
  const [activeMarket, setActiveMarket] = useState("1x2");
  const [activeBottomTab, setActiveBottomTab] = useState("destaques");
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showFavorites, setShowFavorites] = useState(false);

  const isToday =
    selectedDate.toDateString() === new Date().toDateString();

  const navigateDate = (direction: number) => {
    setSelectedDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + direction);
      return next;
    });
  };

  const fetchMatches = useCallback(async () => {
    const leagueIds =
      selectedLeagues.length > 0
        ? selectedLeagues
        : AVAILABLE_LEAGUES.map((l) => l.id);
    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/matches/fetch?leagues=${encodeURIComponent(leagueIds.join(","))}&date=today`,
        { cache: "no-store" }
      );
      const data = await response.json();
      setMatches(Array.isArray(data?.matches) ? data.matches : []);
    } catch {
      setMatches([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedLeagues]);

  useEffect(() => {
    fetchMatches();
  }, [fetchMatches]);

  const toggleLeague = (id: string) => {
    setSelectedLeagues((prev) =>
      prev.includes(id) ? prev.filter((l) => l !== id) : [...prev, id]
    );
  };

  const filteredMatches = matches.filter((m) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        m.homeTeam.name.toLowerCase().includes(q) ||
        m.awayTeam.name.toLowerCase().includes(q) ||
        m.leagueName.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const getOddsForMarket = (match: Match) => {
    switch (activeMarket) {
      case "1x2":
        return [
          { label: "1", value: match.odds.home },
          { label: "X", value: match.odds.draw },
          { label: "2", value: match.odds.away },
        ];
      case "dupla-chance":
        return [
          { label: "1X", value: +(1 / (1 / match.odds.home + 1 / match.odds.draw)).toFixed(2) },
          { label: "12", value: +(1 / (1 / match.odds.home + 1 / match.odds.away)).toFixed(2) },
          { label: "X2", value: +(1 / (1 / match.odds.draw + 1 / match.odds.away)).toFixed(2) },
        ];
      case "btts":
        return [
          { label: "Sim", value: match.odds.bttsYes },
          { label: "Nao", value: match.odds.bttsNo },
        ];
      case "gols":
        return [
          { label: "O 2.5", value: match.odds.over25 },
          { label: "U 2.5", value: match.odds.under25 },
        ];
      default:
        return [
          { label: "1", value: match.odds.home },
          { label: "X", value: match.odds.draw },
          { label: "2", value: match.odds.away },
        ];
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-xl font-bold tracking-tight">sportsbank.</span>
            <span className="bg-primary text-primary-foreground text-[10px] font-bold px-1.5 py-0.5 rounded">
              PRO
            </span>
          </div>

          {/* Search */}
          <div className="flex-1 max-w-md mx-auto">
            {searchOpen ? (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                <input
                  autoFocus
                  type="text"
                  placeholder="Buscar jogos, times, ligas..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onBlur={() => !searchQuery && setSearchOpen(false)}
                  className="w-full bg-secondary rounded-lg pl-9 pr-16 py-2 text-sm outline-none placeholder:text-muted-foreground"
                />
                <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground bg-background px-1.5 py-0.5 rounded border border-border">
                  Esc
                </kbd>
              </div>
            ) : (
              <button
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-2 w-full bg-secondary rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-secondary/80 transition-colors"
              >
                <Search size={16} />
                <span>Buscar</span>
                <kbd className="ml-auto text-[10px] bg-background px-1.5 py-0.5 rounded border border-border">
                  Ctrl+K
                </kbd>
              </button>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0">
            <ThemeToggle />
            <button className="p-2 rounded-lg hover:bg-secondary transition-colors relative" aria-label="Notificacoes">
              <Bell size={18} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full" />
            </button>
          </div>
        </div>
      </header>

      {/* Date navigation bar */}
      <div className="border-b border-border bg-card/50">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center gap-3">
          <button
            onClick={() => navigateDate(-1)}
            className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
            aria-label="Dia anterior"
          >
            <ChevronLeft size={18} />
          </button>

          <button
            onClick={() => setSelectedDate(new Date())}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-secondary transition-colors font-medium text-sm"
          >
            {isToday && <span className="w-2 h-2 bg-primary rounded-full" />}
            {isToday ? "Hoje" : formatDate(selectedDate)}
          </button>

          <button
            onClick={() => navigateDate(1)}
            className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
            aria-label="Proximo dia"
          >
            <ChevronRight size={18} />
          </button>

          <div className="flex-1" />

          <button
            onClick={() => setShowFavorites(!showFavorites)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              showFavorites ? "bg-primary/20 text-primary" : "hover:bg-secondary"
            }`}
          >
            <Star size={14} />
            Favoritos
          </button>

          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm hover:bg-secondary transition-colors">
            <ArrowUpDown size={14} />
            Ordenar
          </button>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              showFilters ? "bg-primary/20 text-primary" : "hover:bg-secondary"
            }`}
          >
            <SlidersHorizontal size={14} />
            Filtros
          </button>
        </div>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="border-b border-border bg-card/30 animate-fade-in">
          <div className="max-w-7xl mx-auto px-4 py-3">
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_LEAGUES.map((league) => (
                <button
                  key={league.id}
                  onClick={() => toggleLeague(league.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    selectedLeagues.includes(league.id)
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                  }`}
                >
                  <span>{league.countryFlag}</span>
                  {league.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Market tabs */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex gap-1 overflow-x-auto no-scrollbar" aria-label="Mercados">
            {MARKET_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveMarket(tab.id)}
                className={`relative px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                  activeMarket === tab.id
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
                {activeMarket === tab.id && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
                )}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main content: match list + detail panel */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-4 h-full">
          {/* Match list */}
          <div className="space-y-2">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <Loader2 className="animate-spin mb-3" size={32} />
                <p className="text-sm">Carregando jogos...</p>
              </div>
            ) : filteredMatches.length > 0 ? (
              filteredMatches.map((match) => (
                <button
                  key={match.id}
                  onClick={() => setSelectedMatch(match)}
                  className={`w-full text-left rounded-xl border transition-colors p-4 ${
                    selectedMatch?.id === match.id
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:border-primary/30"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-muted-foreground">
                      {match.leagueName}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(match.datetime).toLocaleTimeString("pt-BR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <p className="font-medium text-sm">{match.homeTeam.name}</p>
                      <p className="font-medium text-sm mt-1">{match.awayTeam.name}</p>
                    </div>

                    <div className="flex gap-2">
                      {getOddsForMarket(match).map((odd) => (
                        <div
                          key={odd.label}
                          className="flex flex-col items-center bg-secondary rounded-lg px-3 py-1.5 min-w-[48px]"
                        >
                          <span className="text-[10px] text-muted-foreground">
                            {odd.label}
                          </span>
                          <span className="text-sm font-semibold">
                            {odd.value.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {match.status === "live" && (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                      <span className="text-xs text-red-400 font-medium">AO VIVO</span>
                      {match.score && (
                        <span className="text-xs font-bold ml-1">
                          {match.score.home} - {match.score.away}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <div className="text-5xl mb-4">&#9917;</div>
                <p className="text-sm">Nenhum jogo disponivel para hoje.</p>
                <p className="text-xs mt-1">
                  Tente selecionar outra data ou liga.
                </p>
              </div>
            )}
          </div>

          {/* Detail panel */}
          <aside className="hidden lg:block">
            <div className="sticky top-[130px] rounded-xl border border-border bg-card p-6">
              {selectedMatch ? (
                <div className="space-y-4">
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground mb-3">
                      {selectedMatch.leagueName}
                    </p>
                    <div className="flex items-center justify-center gap-4">
                      <div className="text-center">
                        <p className="font-semibold">{selectedMatch.homeTeam.name}</p>
                        <div className="flex gap-0.5 mt-1 justify-center">
                          {selectedMatch.homeTeam.form?.slice(0, 5).map((f, i) => (
                            <span
                              key={i}
                              className={`w-5 h-5 rounded text-[10px] font-bold flex items-center justify-center ${
                                f === "W"
                                  ? "bg-primary/20 text-primary"
                                  : f === "L"
                                    ? "bg-destructive/20 text-destructive"
                                    : "bg-secondary text-muted-foreground"
                              }`}
                            >
                              {f}
                            </span>
                          ))}
                        </div>
                      </div>
                      <span className="text-2xl font-bold text-muted-foreground">vs</span>
                      <div className="text-center">
                        <p className="font-semibold">{selectedMatch.awayTeam.name}</p>
                        <div className="flex gap-0.5 mt-1 justify-center">
                          {selectedMatch.awayTeam.form?.slice(0, 5).map((f, i) => (
                            <span
                              key={i}
                              className={`w-5 h-5 rounded text-[10px] font-bold flex items-center justify-center ${
                                f === "W"
                                  ? "bg-primary/20 text-primary"
                                  : f === "L"
                                    ? "bg-destructive/20 text-destructive"
                                    : "bg-secondary text-muted-foreground"
                              }`}
                            >
                              {f}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Probabilities */}
                  <div className="space-y-2 pt-4 border-t border-border">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Probabilidades
                    </h3>
                    <div className="grid grid-cols-3 gap-2">
                      <div className="text-center bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">Casa</p>
                        <p className="font-semibold text-sm">{(selectedMatch.stats.homeWinProb * 100).toFixed(0)}%</p>
                      </div>
                      <div className="text-center bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">Empate</p>
                        <p className="font-semibold text-sm">{(selectedMatch.stats.drawProb * 100).toFixed(0)}%</p>
                      </div>
                      <div className="text-center bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">Fora</p>
                        <p className="font-semibold text-sm">{(selectedMatch.stats.awayWinProb * 100).toFixed(0)}%</p>
                      </div>
                    </div>
                  </div>

                  {/* Market stats */}
                  <div className="space-y-2 pt-4 border-t border-border">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Mercados
                    </h3>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">Over 2.5</p>
                        <p className="font-semibold text-sm">{(selectedMatch.stats.over25Prob * 100).toFixed(0)}%</p>
                      </div>
                      <div className="bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">BTTS</p>
                        <p className="font-semibold text-sm">{(selectedMatch.stats.bttsProb * 100).toFixed(0)}%</p>
                      </div>
                      <div className="bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">Media Gols</p>
                        <p className="font-semibold text-sm">{selectedMatch.stats.avgGoals.toFixed(1)}</p>
                      </div>
                      <div className="bg-secondary rounded-lg p-2">
                        <p className="text-xs text-muted-foreground">H2H</p>
                        <p className="font-semibold text-sm">{selectedMatch.h2h.totalMatches} jogos</p>
                      </div>
                    </div>
                  </div>

                  {/* H2H detail */}
                  {selectedMatch.h2h.totalMatches > 0 && (
                    <div className="space-y-2 pt-4 border-t border-border">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Confronto Direto
                      </h3>
                      <div className="flex justify-between text-sm">
                        <span>Vit. Casa: {selectedMatch.h2h.homeWins}</span>
                        <span>Emp: {selectedMatch.h2h.draws}</span>
                        <span>Vit. Fora: {selectedMatch.h2h.awayWins}</span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <div className="text-3xl mb-3">&#9917;</div>
                  <p className="text-sm">Selecione um jogo para ver os detalhes</p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>

      {/* Bottom navigation */}
      <nav className="sticky bottom-0 z-30 border-t border-border bg-card/95 backdrop-blur" aria-label="Navegacao principal">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-around">
            {BOTTOM_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveBottomTab(tab.id)}
                className={`flex-1 py-3 text-sm font-medium text-center transition-colors relative ${
                  activeBottomTab === tab.id
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
                {activeBottomTab === tab.id && (
                  <span className="absolute top-0 left-1/4 right-1/4 h-0.5 bg-primary rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Keyboard shortcut handler */}
      <KeyboardShortcuts onSearch={() => setSearchOpen(true)} />
    </div>
  );
}

function KeyboardShortcuts({ onSearch }: { onSearch: () => void }) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onSearch();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSearch]);
  return null;
}
