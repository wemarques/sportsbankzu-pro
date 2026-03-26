"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Loader2, X } from "lucide-react";

interface StandingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  leagueName: string;
  leagueId: string;
  homeTeam: string;
  awayTeam: string;
}

interface StandingRow {
  position?: number;
  name?: string;
  cleanName?: string;
  team_name?: string;
  played?: number;
  matchesPlayed?: number;
  won?: number;
  wins?: number;
  drawn?: number;
  draws?: number;
  lost?: number;
  losses?: number;
  goalsFor?: number;
  goals_for?: number;
  goalsAgainst?: number;
  goals_against?: number;
  goalDifference?: number;
  goal_difference?: number;
  points?: number;
  pts?: number;
}

export default function StandingsModal({ isOpen, onClose, leagueName, leagueId, homeTeam, awayTeam }: StandingsModalProps) {
  const [data, setData] = useState<StandingRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !leagueId) return;
    setLoading(true);
    setError(null);
    fetch(`/api/standings?league=${encodeURIComponent(leagueId)}`)
      .then((r) => r.json())
      .then((res) => {
        const rows = res.standings ?? [];
        if (rows.length === 0) setError("Classificacao indisponivel para esta liga");
        else setData(rows);
      })
      .catch(() => setError("Erro ao carregar classificacao"))
      .finally(() => setLoading(false));
  }, [isOpen, leagueId]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const totalTeams = data.length;

  const getTeamName = (row: StandingRow) => row.cleanName || row.name || row.team_name || "—";
  const isMatchTeam = (row: StandingRow) => {
    const n = getTeamName(row).toLowerCase();
    return n === homeTeam.toLowerCase() || n === awayTeam.toLowerCase();
  };

  const getZoneClass = (pos: number) => {
    if (totalTeams === 0) return "";
    if (pos <= 4) return "standings-row--champions";
    if (pos > totalTeams - 3) return "standings-row--relegation";
    return "";
  };

  const gf = (row: StandingRow) => row.goalsFor ?? row.goals_for ?? null;
  const ga = (row: StandingRow) => row.goalsAgainst ?? row.goals_against ?? null;
  const gd = (row: StandingRow) => {
    if (row.goalDifference != null) return row.goalDifference;
    if (row.goal_difference != null) return row.goal_difference;
    const f = gf(row); const a = ga(row);
    if (f != null && a != null) return f - a;
    return null;
  };

  return (
    <div className="standings-overlay" onClick={onClose}>
      <div className="standings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="standings-header">
          <span className="standings-header__title">{leagueName || "Classificacao"}</span>
          <button className="standings-header__close" onClick={onClose} aria-label="Fechar">
            <X size={18} />
          </button>
        </div>
        <div className="standings-body">
          {loading ? (
            <div className="standings-loading">
              <Loader2 size={20} className="animate-spin" style={{ display: "inline-block" }} />
              <span>Carregando...</span>
            </div>
          ) : error ? (
            <div className="standings-error">{error}</div>
          ) : (
            <div className="standings-table-wrap">
              <table className="standings-table">
                <thead>
                  <tr>
                    <th className="standings-th standings-th--left">#</th>
                    <th className="standings-th standings-th--left standings-th--team">Time</th>
                    <th className="standings-th">P</th>
                    <th className="standings-th">V</th>
                    <th className="standings-th">E</th>
                    <th className="standings-th">D</th>
                    <th className="standings-th">GP</th>
                    <th className="standings-th">GC</th>
                    <th className="standings-th">SG</th>
                    <th className="standings-th standings-th--pts">Pts</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row, idx) => {
                    const pos = row.position ?? idx + 1;
                    const highlighted = isMatchTeam(row);
                    return (
                      <tr
                        key={idx}
                        className={`standings-row ${getZoneClass(pos)} ${highlighted ? "standings-row--highlight" : ""}`}
                      >
                        <td className="standings-td standings-td--pos">{pos}</td>
                        <td className="standings-td standings-td--team">{getTeamName(row)}</td>
                        <td className="standings-td">{row.played ?? row.matchesPlayed ?? "-"}</td>
                        <td className="standings-td">{row.won ?? row.wins ?? "-"}</td>
                        <td className="standings-td">{row.drawn ?? row.draws ?? "-"}</td>
                        <td className="standings-td">{row.lost ?? row.losses ?? "-"}</td>
                        <td className="standings-td">{gf(row) ?? "-"}</td>
                        <td className="standings-td">{ga(row) ?? "-"}</td>
                        <td className="standings-td">{gd(row) ?? "-"}</td>
                        <td className="standings-td standings-td--pts">{row.points ?? row.pts ?? "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
