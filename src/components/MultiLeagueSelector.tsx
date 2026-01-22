 "use client";
import { useState } from "react";
import { Check, ChevronDown, Globe, Search, X } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Checkbox } from "./ui/checkbox";
import { ScrollArea } from "./ui/scroll-area";
import { AVAILABLE_LEAGUES } from "../lib/leagues";

type MultiLeagueSelectorProps = {
  selectedLeagues: string[];
  onSelectionChange: (leagues: string[]) => void;
  onFetchMatches: () => void;
  isLoading: boolean;
};

export default function MultiLeagueSelector({
  selectedLeagues,
  onSelectionChange,
  onFetchMatches,
  isLoading,
}: MultiLeagueSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const filteredLeagues = AVAILABLE_LEAGUES.filter(
    (league) =>
      league.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      league.country.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleLeague = (leagueId: string) => {
    if (selectedLeagues.includes(leagueId)) {
      onSelectionChange(selectedLeagues.filter((id) => id !== leagueId));
    } else {
      onSelectionChange([...selectedLeagues, leagueId]);
    }
  };

  const selectAll = () => {
    onSelectionChange(AVAILABLE_LEAGUES.map((l) => l.id));
  };

  const clearAll = () => {
    onSelectionChange([]);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Popover open={isOpen} onOpenChange={setIsOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-between bg-[#12121a] border border-[#1e1e2e] hover:bg-[#1a1a24]"
            >
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-[var(--accent)]" />
                <span>
                  {selectedLeagues.length === 0
                    ? "Selecionar Ligas"
                    : `${selectedLeagues.length} liga(s) selecionada(s)`}
                </span>
              </div>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0 bg-[#12121a] border-[#1e1e2e]">
            <div className="p-3 border-b border-[#1e1e2e]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <Input
                  placeholder="Buscar liga..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 bg-[#0a0a0f] border-[#1e1e2e]"
                />
              </div>
              <div className="flex gap-2 mt-2">
                <Button size="sm" variant="ghost" onClick={selectAll} className="text-xs">
                  Selecionar Todas
                </Button>
                <Button size="sm" variant="ghost" onClick={clearAll} className="text-xs">
                  Limpar
                </Button>
              </div>
            </div>
            <ScrollArea className="h-64">
              <div className="p-2 space-y-1">
                {filteredLeagues.map((league) => (
                  <div
                    key={league.id}
                    className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                      selectedLeagues.includes(league.id)
                        ? "bg-purple-500/20 border border-purple-500/50"
                        : "hover:bg-[#1a1a24]"
                    }`}
                    onClick={() => toggleLeague(league.id)}
                  >
                    <Checkbox checked={selectedLeagues.includes(league.id)} className="data-[state=checked]:bg-purple-500" />
                    <span className="text-xl">{league.countryFlag}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{league.name}</p>
                      <p className="text-xs text-zinc-500">{league.country}</p>
                    </div>
                    {league.matchesToday > 0 && (
                      <Badge className="bg-green-500/20 text-green-400 text-xs">{league.matchesToday} jogos</Badge>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>

        <Button
          onClick={onFetchMatches}
          disabled={selectedLeagues.length === 0 || isLoading}
          className="bg-[var(--accent)] hover:brightness-110"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin">⟳</span> Buscando...
            </span>
          ) : (
            "Buscar Jogos"
          )}
        </Button>
      </div>

      {selectedLeagues.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedLeagues.map((leagueId) => {
            const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
            return (
              <Badge
                key={leagueId}
                variant="default"
                className="bg-[#12121a] border border-[#1e1e2e] flex items-center gap-1"
              >
                {league?.countryFlag} {league?.name}
                <X
                  className="h-3 w-3 cursor-pointer hover:text-[var(--danger)]"
                  onClick={() => toggleLeague(leagueId)}
                />
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}
