"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import {
  DollarSign,
  TrendingUp,
  Layers,
  Link2,
  Target,
  Zap,
  ShieldCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Loader2,
  Wallet,
  PieChart,
  ArrowLeft,
  Info,
  Pencil,
  Trash2,
  Check,
  X,
  Clock,
  Shuffle,
  ShieldAlert,
  Crown,
  Ban,
  CircleDollarSign,
  BarChart3,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  type BetInput,
  type BetAllocation,
  type BankrollSettings,
  type SystemBetSuggestion,
  type SystemBetScenario,
  type BankerSelection,
  distributeBankroll,
  loadSettings,
  saveSettings,
  DEFAULT_SETTINGS,
  KELLY_MULTIPLIERS,
  MAX_STAKE_PCT,
} from "@/lib/kelly";
import { getBankroll, subscribeBankroll } from "@/lib/bankrollStore";

/* ── Types from combinadas API ── */
interface CombinadaLeg {
  jogo: string;
  homeTeam: string;
  awayTeam: string;
  leagueId: string;
  leagueName: string;
  datetime: string;
  mercado: string;
  status: string;
  prob_min: number;
  prob_max: number;
  odd_minima: number;
}
interface Combinada {
  tipo: "intra" | "inter";
  leg1: CombinadaLeg;
  leg2: CombinadaLeg;
  odd_combinada: number;
  prob_combinada_min: number;
  prob_combinada_max: number;
  status_combinada: "SAFE" | "MISTA" | "NEUTRO";
}
interface CombinadasData {
  intra: Combinada[];
  inter: Combinada[];
  total_intra: number;
  total_inter: number;
}

/* ── Helpers ── */
function formatCurrency(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatTime(dt: string): string {
  try {
    const d = new Date(dt);
    return isNaN(d.getTime())
      ? "--:--"
      : d.toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
          timeZone: "America/Sao_Paulo",
        });
  } catch {
    return "--:--";
  }
}

function statusColor(status: string) {
  if (status === "SAFE")
    return { bg: "rgba(0,223,130,0.08)", border: "rgba(0,223,130,0.3)", text: "#00df82" };
  if (status === "MISTA")
    return { bg: "rgba(157,80,255,0.08)", border: "rgba(157,80,255,0.3)", text: "#c4a0ff" };
  return { bg: "rgba(255,136,0,0.06)", border: "rgba(255,136,0,0.25)", text: "#ffaa44" };
}

function evColor(ev: number): string {
  if (ev >= 0.15) return "#00df82";
  if (ev >= 0.05) return "#4ade80";
  if (ev > 0) return "#ffaa44";
  return "#ff5555";
}

function combinadasToBets(data: CombinadasData): BetInput[] {
  const bets: BetInput[] = [];

  // Simples from intra legs (unique legs)
  const seenLegs = new Set<string>();
  for (const c of [...data.intra, ...data.inter]) {
    for (const leg of [c.leg1, c.leg2]) {
      const key = `${leg.homeTeam}-${leg.awayTeam}-${leg.mercado}`;
      const st = leg.status.toUpperCase();
      if (!seenLegs.has(key) && (st.startsWith("SAFE") || st.startsWith("NEUTRO"))) {
        seenLegs.add(key);
        bets.push({
          id: `simple-${key}`,
          label: `${leg.homeTeam} x ${leg.awayTeam}`,
          homeTeam: leg.homeTeam,
          awayTeam: leg.awayTeam,
          market: leg.mercado,
          odd: leg.odd_minima,
          probMin: leg.prob_min,
          probMax: leg.prob_max,
          status: leg.status,
          datetime: leg.datetime,
          leagueName: leg.leagueName,
          category: "simples",
        });
      }
    }
  }

  // Duplas intra
  for (const c of data.intra) {
    bets.push({
      id: `intra-${c.leg1.homeTeam}-${c.leg1.mercado}-${c.leg2.mercado}`,
      label: `${c.leg1.homeTeam} x ${c.leg1.awayTeam}`,
      homeTeam: c.leg1.homeTeam,
      awayTeam: c.leg1.awayTeam,
      market: c.leg1.mercado,
      odd: c.odd_combinada,
      probMin: c.prob_combinada_min,
      probMax: c.prob_combinada_max,
      status: c.status_combinada,
      datetime: c.leg1.datetime,
      leagueName: c.leg1.leagueName,
      category: "dupla_intra",
      leg2Label: `${c.leg2.homeTeam} x ${c.leg2.awayTeam}`,
      leg2Market: c.leg2.mercado,
      leg2Odd: c.leg2.odd_minima,
      leg2Status: c.leg2.status,
    });
  }

  // Duplas inter
  for (const c of data.inter) {
    bets.push({
      id: `inter-${c.leg1.homeTeam}-${c.leg2.homeTeam}`,
      label: `${c.leg1.homeTeam} x ${c.leg1.awayTeam}`,
      homeTeam: c.leg1.homeTeam,
      awayTeam: c.leg1.awayTeam,
      market: c.leg1.mercado,
      odd: c.odd_combinada,
      probMin: c.prob_combinada_min,
      probMax: c.prob_combinada_max,
      status: c.status_combinada,
      datetime: c.leg1.datetime,
      leagueName: c.leg1.leagueName,
      category: "dupla_inter",
      leg2Label: `${c.leg2.homeTeam} x ${c.leg2.awayTeam}`,
      leg2Market: c.leg2.mercado,
      leg2Odd: c.leg2.odd_minima,
      leg2Status: c.leg2.status,
    });
  }

  return bets;
}

/* ── Animated Number ── */
function AnimatedValue({ value, prefix = "" }: { value: number; prefix?: string }) {
  return (
    <span className="tabular-nums font-bold transition-all duration-300">
      {prefix}
      {formatCurrency(value)}
    </span>
  );
}

/* ── Inline Stake Editor ── */
function InlineStakeEditor({
  value,
  onConfirm,
  onCancel,
  color,
}: {
  value: number;
  onConfirm: (v: number) => void;
  onCancel: () => void;
  color: string;
}) {
  const [input, setInput] = useState(value.toFixed(2));
  return (
    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <span className="text-[0.6rem] font-bold" style={{ color }}>R$</span>
      <input
        type="text"
        autoFocus
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            const num = parseFloat(input.replace(",", "."));
            if (!isNaN(num) && num >= 0) onConfirm(num);
          }
          if (e.key === "Escape") onCancel();
        }}
        className="w-16 text-[0.72rem] font-bold tabular-nums text-right rounded px-1 py-0.5 outline-none"
        style={{
          background: "rgba(255,255,255,0.08)",
          border: `1px solid ${color}40`,
          color: "var(--color-text-primary)",
        }}
      />
      <button
        onClick={() => {
          const num = parseFloat(input.replace(",", "."));
          if (!isNaN(num) && num >= 0) onConfirm(num);
        }}
        className="w-5 h-5 rounded flex items-center justify-center"
        style={{ background: "rgba(34,197,94,0.15)" }}
      >
        <Check size={10} className="text-[#22c55e]" />
      </button>
      <button
        onClick={onCancel}
        className="w-5 h-5 rounded flex items-center justify-center"
        style={{ background: "rgba(255,85,85,0.15)" }}
      >
        <X size={10} className="text-[#ff5555]" />
      </button>
    </div>
  );
}

/* ── Game Card for Simples ── */
function SimpleGameCard({
  a,
  color,
  onRemove,
  onStakeChange,
}: {
  a: BetAllocation;
  color: string;
  onRemove: (id: string) => void;
  onStakeChange: (id: string, stake: number) => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <div
      className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg border transition-all"
      style={{
        background: `${color}06`,
        borderColor: `${color}15`,
      }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <div className="text-[0.7rem] font-semibold text-[var(--color-text-primary)] truncate">
            {a.bet.homeTeam}{" "}
            <span className="text-[var(--color-text-muted)]">x</span>{" "}
            {a.bet.awayTeam}
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          <span
            className="text-[0.6rem] font-medium px-1.5 py-px rounded"
            style={{ background: `${color}15`, color }}
          >
            {a.bet.market}
          </span>
          <span className="text-[0.58rem] text-[var(--color-text-muted)]">
            {a.bet.leagueName}
          </span>
          <span className="text-[0.55rem] text-[var(--color-text-muted)] flex items-center gap-0.5">
            <Clock size={8} />
            {formatTime(a.bet.datetime)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div className="text-right">
          {editing ? (
            <InlineStakeEditor
              value={a.stake}
              color={color}
              onConfirm={(v) => { onStakeChange(a.bet.id, v); setEditing(false); }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              <div className="text-[0.78rem] font-black tabular-nums" style={{ color }}>
                {formatCurrency(a.stake)}
              </div>
              <div className="text-[0.55rem] text-[var(--color-text-muted)]">
                odd {a.bet.odd.toFixed(2)} &middot; EV{" "}
                <span style={{ color: evColor(a.ev) }}>
                  {a.ev > 0 ? "+" : ""}{(a.ev * 100).toFixed(1)}%
                </span>
              </div>
            </>
          )}
        </div>
        {!editing && (
          <div className="flex flex-col gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); setEditing(true); }}
              className="w-5 h-5 rounded flex items-center justify-center transition-colors hover:scale-110"
              style={{ background: `${color}15` }}
              title="Editar stake"
            >
              <Pencil size={9} style={{ color }} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onRemove(a.bet.id); }}
              className="w-5 h-5 rounded flex items-center justify-center transition-colors hover:scale-110"
              style={{ background: "rgba(255,85,85,0.1)" }}
              title="Remover"
            >
              <Trash2 size={9} className="text-[#ff5555]" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Game Card for Duplas (linked legs) ── */
function DuplaGameCard({
  a,
  color,
  onRemove,
  onStakeChange,
}: {
  a: BetAllocation;
  color: string;
  onRemove: (id: string) => void;
  onStakeChange: (id: string, stake: number) => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <div
      className="rounded-lg border transition-all overflow-hidden"
      style={{
        background: `${color}06`,
        borderColor: `${color}15`,
      }}
    >
      {/* Combined header with odd and actions */}
      <div className="flex items-center justify-between px-2.5 pt-2 pb-1">
        <div className="flex items-center gap-1.5">
          <span
            className="text-[0.58rem] font-bold uppercase tracking-wider px-1.5 py-px rounded"
            style={{ background: `${color}18`, color }}
          >
            {a.bet.category === "dupla_intra" ? "Intra" : "Inter"}
          </span>
          <span className="text-[0.58rem] text-[var(--color-text-muted)] flex items-center gap-0.5">
            <Clock size={8} />
            {formatTime(a.bet.datetime)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <InlineStakeEditor
              value={a.stake}
              color={color}
              onConfirm={(v) => { onStakeChange(a.bet.id, v); setEditing(false); }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              <div className="text-right">
                <div className="text-[0.78rem] font-black tabular-nums" style={{ color }}>
                  {formatCurrency(a.stake)}
                </div>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); setEditing(true); }}
                  className="w-5 h-5 rounded flex items-center justify-center hover:scale-110"
                  style={{ background: `${color}15` }}
                  title="Editar stake"
                >
                  <Pencil size={9} style={{ color }} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onRemove(a.bet.id); }}
                  className="w-5 h-5 rounded flex items-center justify-center hover:scale-110"
                  style={{ background: "rgba(255,85,85,0.1)" }}
                  title="Remover"
                >
                  <Trash2 size={9} className="text-[#ff5555]" />
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Linked legs */}
      <div className="flex items-stretch px-2.5 pb-2 gap-0">
        {/* Vertical connector line */}
        <div className="flex flex-col items-center w-4 shrink-0 py-1">
          <div
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: color }}
          />
          <div
            className="w-px flex-1 my-0.5"
            style={{ background: `${color}40` }}
          />
          <div
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: color }}
          />
        </div>

        <div className="flex-1 space-y-1.5 min-w-0">
          {/* Leg 1 */}
          <div>
            <div className="text-[0.68rem] font-semibold text-[var(--color-text-primary)] truncate">
              {a.bet.homeTeam}{" "}
              <span className="text-[var(--color-text-muted)]">x</span>{" "}
              {a.bet.awayTeam}
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="text-[0.58rem] font-medium px-1.5 py-px rounded"
                style={{ background: `${color}15`, color }}
              >
                {a.bet.market}
              </span>
              <span className="text-[0.55rem] text-[var(--color-text-muted)]">
                {a.bet.leagueName}
              </span>
            </div>
          </div>

          {/* Leg 2 */}
          {a.bet.leg2Label && (
            <div>
              <div className="text-[0.68rem] font-semibold text-[var(--color-text-primary)] truncate">
                {a.bet.leg2Label}
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className="text-[0.58rem] font-medium px-1.5 py-px rounded"
                  style={{ background: `${color}15`, color }}
                >
                  {a.bet.leg2Market}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer: combined odd + EV */}
      <div
        className="flex items-center justify-between px-2.5 py-1.5 border-t"
        style={{ borderColor: `${color}12` }}
      >
        <div className="flex items-center gap-3">
          <div className="text-[0.58rem] text-[var(--color-text-muted)]">
            Odd combinada{" "}
            <span className="font-bold text-[var(--color-text-primary)]">
              {a.bet.odd.toFixed(2)}
            </span>
          </div>
          <div className="text-[0.58rem] text-[var(--color-text-muted)]">
            EV{" "}
            <span className="font-bold" style={{ color: evColor(a.ev) }}>
              {a.ev > 0 ? "+" : ""}{(a.ev * 100).toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="text-[0.58rem] text-[var(--color-text-muted)]">
          Retorno{" "}
          <span className="font-bold text-[#00df82]">
            {formatCurrency(a.potentialReturn)}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Slider Component ── */
function BankSlider({
  label,
  value,
  onChange,
  icon,
  color,
  description,
  allocations,
  bankroll,
  onRemoveBet,
  onStakeChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  icon: React.ReactNode;
  color: string;
  description: string;
  allocations?: BetAllocation[];
  bankroll?: number;
  onRemoveBet?: (id: string) => void;
  onStakeChange?: (id: string, stake: number) => void;
}) {
  const hasAllocations = allocations && allocations.length > 0;
  const [showGames, setShowGames] = useState(true);
  const catBudget = bankroll ? bankroll * (value / 100) : 0;
  const totalStaked = allocations?.reduce((s, a) => s + a.stake, 0) ?? 0;
  const isOverBudget = totalStaked > catBudget + 0.01;
  const budgetPct = catBudget > 0 ? Math.min((totalStaked / catBudget) * 100, 100) : 0;

  // Sort by highest stake first
  const sortedAllocations = useMemo(() => {
    if (!allocations) return [];
    return [...allocations].sort((a, b) => b.stake - a.stake);
  }, [allocations]);

  const isDuplaCategory = sortedAllocations.some(
    (a) => a.bet.category === "dupla_intra" || a.bet.category === "dupla_inter",
  );

  return (
    <div className="group relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-transform group-hover:scale-110"
            style={{ background: `${color}15` }}
          >
            {icon}
          </div>
          <div>
            <span className="text-sm font-semibold text-[var(--color-text-primary)]">
              {label}
            </span>
            <p className="text-[0.65rem] text-[var(--color-text-muted)] leading-tight">
              {description}
            </p>
          </div>
        </div>
        <div
          className="text-xl font-black tabular-nums min-w-[60px] text-right transition-colors"
          style={{ color }}
        >
          {value}%
        </div>
      </div>
      <div className="relative h-2 rounded-full bg-[#1a1a2e] overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-200"
          style={{
            width: `${value}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            boxShadow: `0 0 12px ${color}40`,
          }}
        />
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="absolute bottom-0 left-0 w-full h-2 opacity-0 cursor-pointer"
        style={{ zIndex: 2 }}
      />

      {/* Game allocations inline */}
      {hasAllocations && (
        <div className="mt-3">
          {/* Toggle button with summary */}
          <button
            onClick={() => setShowGames(!showGames)}
            className="w-full text-left"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-[0.65rem] font-semibold transition-colors"
                style={{ color: isOverBudget ? "#ff5555" : `${color}cc` }}
              >
                {showGames ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {sortedAllocations.length}{" "}
                {sortedAllocations.length === 1 ? "jogo" : "jogos"}
              </div>
              <span
                className="text-[0.62rem] font-bold tabular-nums"
                style={{ color: isOverBudget ? "#ff5555" : "var(--color-text-muted)" }}
              >
                {formatCurrency(totalStaked)} / {formatCurrency(catBudget)}
              </span>
            </div>

            {/* Budget progress bar */}
            <div className="relative h-1 rounded-full bg-[#1a1a2e] overflow-hidden mt-1.5">
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                style={{
                  width: `${budgetPct}%`,
                  background: isOverBudget
                    ? "linear-gradient(90deg, #ff555588, #ff5555)"
                    : `linear-gradient(90deg, ${color}55, ${color})`,
                  boxShadow: isOverBudget ? "0 0 8px rgba(255,85,85,0.4)" : `0 0 6px ${color}30`,
                }}
              />
            </div>
          </button>

          {/* Over-budget alert */}
          {isOverBudget && (
            <div
              className="flex items-center gap-1.5 text-[0.62rem] mt-2 px-2 py-1.5 rounded-lg"
              style={{
                background: "rgba(255,85,85,0.08)",
                border: "1px solid rgba(255,85,85,0.2)",
                color: "#ff5555",
              }}
            >
              <AlertTriangle size={10} />
              Alocação excede o limite em{" "}
              <strong>{formatCurrency(totalStaked - catBudget)}</strong>. Ajuste as stakes ou aumente o %.
            </div>
          )}

          {/* Expanded game list */}
          {showGames && (
            <div className="mt-2 space-y-1.5 animate-in fade-in slide-in-from-top-1 duration-200">
              {sortedAllocations.map((a) => {
                const isDupla =
                  a.bet.category === "dupla_intra" || a.bet.category === "dupla_inter";

                if (isDupla) {
                  return (
                    <DuplaGameCard
                      key={a.bet.id}
                      a={a}
                      color={color}
                      onRemove={onRemoveBet ?? (() => {})}
                      onStakeChange={onStakeChange ?? (() => {})}
                    />
                  );
                }

                return (
                  <SimpleGameCard
                    key={a.bet.id}
                    a={a}
                    color={color}
                    onRemove={onRemoveBet ?? (() => {})}
                    onStakeChange={onStakeChange ?? (() => {})}
                  />
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Allocation Card ── */
function AllocationCard({
  allocation,
  index,
}: {
  allocation: BetAllocation;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const sc = statusColor(allocation.bet.status);
  const isDupla =
    allocation.bet.category === "dupla_intra" ||
    allocation.bet.category === "dupla_inter";

  return (
    <div
      className="relative overflow-hidden rounded-xl border transition-all duration-200 hover:scale-[1.01] cursor-pointer"
      style={{
        background: sc.bg,
        borderColor: sc.border,
      }}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Glow effect */}
      <div
        className="absolute top-0 left-0 w-full h-[1px]"
        style={{
          background: `linear-gradient(90deg, transparent, ${sc.text}60, transparent)`,
        }}
      />

      <div className="p-3.5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-[0.6rem] font-bold shrink-0"
              style={{ background: `${sc.text}20`, color: sc.text }}
            >
              {index + 1}
            </div>
            <div className="min-w-0">
              <div className="text-[0.78rem] font-semibold text-[var(--color-text-primary)] truncate">
                {allocation.bet.homeTeam}{" "}
                <span className="text-[var(--color-text-muted)]">x</span>{" "}
                {allocation.bet.awayTeam}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[0.65rem] text-[var(--color-text-muted)]">
                  {allocation.bet.leagueName}
                </span>
                <span className="text-[0.6rem] text-[var(--color-text-muted)]">
                  {formatTime(allocation.bet.datetime)}
                </span>
              </div>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="flex items-center justify-end gap-1">
              {allocation.capped && (
                <span title={`Stake limitada a ${(MAX_STAKE_PCT * 100).toFixed(0)}% da banca`}>
                  <ShieldAlert size={12} className="text-[#ffaa44]" />
                </span>
              )}
              <div className="text-base font-black text-[var(--color-text-primary)]">
                {formatCurrency(allocation.stake)}
              </div>
            </div>
            <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              {allocation.capped ? `stake (cap ${(MAX_STAKE_PCT * 100).toFixed(0)}%)` : "stake"}
            </div>
          </div>
        </div>

        {/* Market & stats row */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className="text-[0.68rem] font-medium px-2 py-0.5 rounded-md"
            style={{ background: `${sc.text}15`, color: sc.text }}
          >
            {allocation.bet.market}
          </span>
          {isDupla && allocation.bet.leg2Market && (
            <>
              <span className="text-[0.55rem] text-[var(--color-text-muted)]">+</span>
              <span
                className="text-[0.68rem] font-medium px-2 py-0.5 rounded-md"
                style={{ background: `${sc.text}15`, color: sc.text }}
              >
                {allocation.bet.leg2Market}
              </span>
            </>
          )}
          <span
            className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded ml-auto"
            style={{ background: `${sc.text}18`, color: sc.text }}
          >
            {allocation.bet.status}
          </span>
        </div>

        {/* Stats bar */}
        <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-white/5">
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <div className="text-center">
              <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
                Odd
              </div>
              <div className="text-sm font-bold text-[var(--color-text-primary)]">
                {allocation.bet.odd.toFixed(2)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
                Prob
              </div>
              <div className="text-sm font-bold text-[var(--color-text-primary)]">
                {allocation.bet.probMin}-{allocation.bet.probMax}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
                EV
              </div>
              <div className="text-sm font-bold" style={{ color: evColor(allocation.ev) }}>
                {allocation.ev > 0 ? "+" : ""}
                {(allocation.ev * 100).toFixed(1)}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
                Kelly
              </div>
              <div className="text-sm font-bold text-[#c4a0ff]">
                {(allocation.kellyFraction * 100).toFixed(1)}%
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              Retorno
            </div>
            <div className="text-sm font-bold text-[#00df82]">
              {formatCurrency(allocation.potentialReturn)}
            </div>
          </div>
        </div>

        {/* Expanded details */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-white/5 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
            {isDupla && allocation.bet.leg2Label && (
              <div className="flex items-center gap-2 text-[0.72rem]">
                <span className="text-[var(--color-text-muted)]">Perna 2:</span>
                <span className="text-[var(--color-text-primary)] font-medium">
                  {allocation.bet.leg2Label}
                </span>
                <span style={{ color: sc.text }}>{allocation.bet.leg2Market}</span>
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <div className="text-[0.6rem] text-[var(--color-text-muted)]">Lucro Potencial</div>
                <div className="text-sm font-bold text-[#00df82]">
                  +{formatCurrency(allocation.potentialProfit)}
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] text-[var(--color-text-muted)]">Edge</div>
                <div className="text-sm font-bold" style={{ color: evColor(allocation.edge) }}>
                  {(allocation.edge * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] text-[var(--color-text-muted)]">Prob. Implicita</div>
                <div className="text-sm font-bold text-[var(--color-text-secondary)]">
                  {allocation.impliedProb.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] text-[var(--color-text-muted)]">ROI Esperado</div>
                <div className="text-sm font-bold" style={{ color: evColor(allocation.ev) }}>
                  {(allocation.ev * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Section Header ── */
function SectionHeader({
  icon,
  title,
  count,
  totalStake,
  color,
  collapsed,
  onToggle,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  totalStake: number;
  color: string;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between py-3 px-1 group"
    >
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: `${color}15` }}
        >
          {icon}
        </div>
        <div className="text-left">
          <span className="text-sm font-bold text-[var(--color-text-primary)]">{title}</span>
          <span
            className="ml-2 text-[0.65rem] font-semibold px-1.5 py-0.5 rounded-full"
            style={{ background: `${color}18`, color }}
          >
            {count}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold text-[var(--color-text-primary)] tabular-nums">
          {formatCurrency(totalStake)}
        </span>
        {collapsed ? (
          <ChevronDown size={14} className="text-[var(--color-text-muted)]" />
        ) : (
          <ChevronUp size={14} className="text-[var(--color-text-muted)]" />
        )}
      </div>
    </button>
  );
}

/* ── System Bet Suggestion Card (Enhanced — 5 Rules) ── */
function SystemBetCard({ suggestion }: { suggestion: SystemBetSuggestion }) {
  const [expanded, setExpanded] = useState(false);
  const [showCombos, setShowCombos] = useState(false);

  // Color scheme based on recommendation status
  const accent = suggestion.recommended ? "#ffaa44" : "#ff5555";
  const accentBg = suggestion.recommended ? "rgba(255,170,68," : "rgba(255,85,85,";

  return (
    <div
      className="rounded-2xl border overflow-hidden"
      style={{
        background: suggestion.recommended
          ? "linear-gradient(135deg, rgba(255,170,68,0.04), rgba(255,136,0,0.06))"
          : "linear-gradient(135deg, rgba(255,85,85,0.03), rgba(255,85,85,0.05))",
        borderColor: `${accentBg}0.25)`,
      }}
    >
      {/* ── Hero headline ── */}
      {suggestion.recommended && (
        <div
          className="px-5 pt-4 pb-3"
          style={{ borderBottom: `1px solid ${accentBg}0.1)` }}
        >
          <p className="text-[0.72rem] leading-relaxed text-[var(--color-text-secondary)]">
            {suggestion.headline}
          </p>
        </div>
      )}

      {/* ── Not recommended warning ── */}
      {!suggestion.recommended && (
        <div
          className="flex items-start gap-2.5 px-5 pt-4 pb-3"
          style={{ borderBottom: "1px solid rgba(255,85,85,0.1)" }}
        >
          <Ban size={16} className="text-[#ff5555] shrink-0 mt-0.5" />
          <div>
            <div className="text-[0.72rem] font-bold text-[#ff5555] mb-1">
              Sistema nao recomendado
            </div>
            <p className="text-[0.65rem] text-[var(--color-text-muted)] leading-relaxed">
              {suggestion.breakEvenReason}
            </p>
          </div>
        </div>
      )}

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-5 text-left"
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2.5">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: `${accentBg}0.12)` }}
            >
              <Shuffle size={18} style={{ color: accent }} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-[var(--color-text-primary)]">
                  Aposta em Sistema
                </span>
                <span
                  className="text-[0.6rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                  style={{ background: `${accentBg}0.15)`, color: accent }}
                >
                  {suggestion.label}
                </span>
                {suggestion.recommended && (
                  <span
                    className="text-[0.55rem] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full"
                    style={{ background: "rgba(34,197,94,0.12)", color: "#22c55e" }}
                  >
                    Recomendado
                  </span>
                )}
              </div>
              <p className="text-[0.65rem] text-[var(--color-text-muted)] mt-0.5">
                {suggestion.description}
              </p>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-base font-black tabular-nums" style={{ color: accent }}>
              {formatCurrency(suggestion.totalStake)}
            </div>
            <div className="text-[0.55rem] text-[var(--color-text-muted)] uppercase">stake total</div>
          </div>
        </div>

        {/* Summary row */}
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/5">
          <div className="text-center flex-1">
            <div className="text-[0.58rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              Selecoes
            </div>
            <div className="text-sm font-bold text-[var(--color-text-primary)]">
              {suggestion.selections.length}
            </div>
          </div>
          <div className="text-center flex-1">
            <div className="text-[0.58rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              Linhas
            </div>
            <div className="text-sm font-bold text-[var(--color-text-primary)]">
              {suggestion.totalCombinations}
            </div>
          </div>
          <div className="text-center flex-1">
            <div className="text-[0.58rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              Stake/Linha
            </div>
            <div className="text-sm font-bold tabular-nums" style={{ color: accent }}>
              {formatCurrency(suggestion.stakePerLine)}
            </div>
          </div>
          <div className="text-center flex-1">
            <div className="text-[0.58rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              Melhor Cenario
            </div>
            <div className="text-sm font-bold text-[#22c55e]">
              {formatCurrency(suggestion.bestCaseReturn)}
            </div>
          </div>
          <div className="shrink-0">
            {expanded ? <ChevronUp size={14} className="text-[var(--color-text-muted)]" /> : <ChevronDown size={14} className="text-[var(--color-text-muted)]" />}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">

          {/* ── Rule 1: Scenario Breakdown ── */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <BarChart3 size={12} style={{ color: accent }} />
              <span className="text-[0.65rem] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                Cenarios de Retorno
              </span>
            </div>
            <div className="space-y-1">
              {suggestion.scenarios.map((sc) => {
                if (sc.hitsRequired === 0) return null; // Skip 0 hits (always loss)
                const pct = suggestion.selections.length > 0
                  ? (sc.hitsRequired / suggestion.selections.length) * 100
                  : 0;
                return (
                  <div
                    key={sc.hitsRequired}
                    className="flex items-center justify-between px-3 py-2 rounded-lg"
                    style={{
                      background: sc.coversInvestment ? "rgba(34,197,94,0.04)" : "rgba(255,85,85,0.03)",
                      border: `1px solid ${sc.coversInvestment ? "rgba(34,197,94,0.12)" : "rgba(255,85,85,0.1)"}`,
                    }}
                  >
                    <div className="flex items-center gap-2">
                      {sc.coversInvestment ? (
                        <CheckCircle2 size={12} className="text-[#22c55e]" />
                      ) : (
                        <XCircle size={12} className="text-[#ff5555]" />
                      )}
                      <span className="text-[0.68rem] font-semibold text-[var(--color-text-primary)]">
                        {sc.hitsRequired} de {suggestion.selections.length} acertos
                      </span>
                      <span className="text-[0.55rem] text-[var(--color-text-muted)]">
                        ({sc.winningCombos} {sc.winningCombos === 1 ? "combo paga" : "combos pagam"})
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[0.65rem] tabular-nums" style={{ color: sc.coversInvestment ? "#22c55e" : "#ff5555" }}>
                        Retorno {formatCurrency(sc.estimatedReturn)}
                      </span>
                      <span
                        className="text-[0.6rem] font-bold tabular-nums px-1.5 py-0.5 rounded"
                        style={{
                          background: sc.netProfit >= 0 ? "rgba(34,197,94,0.1)" : "rgba(255,85,85,0.1)",
                          color: sc.netProfit >= 0 ? "#22c55e" : "#ff5555",
                        }}
                      >
                        {sc.netProfit >= 0 ? "+" : ""}{formatCurrency(sc.netProfit)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Rule 4: Banker (Anchor Bet) ── */}
          {suggestion.banker && suggestion.recommended && (
            <div
              className="rounded-xl border overflow-hidden"
              style={{
                background: "linear-gradient(135deg, rgba(255,215,0,0.04), rgba(255,170,68,0.06))",
                borderColor: "rgba(255,215,0,0.2)",
              }}
            >
              <div className="px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: "rgba(255,215,0,0.15)" }}
                  >
                    <Crown size={14} className="text-[#ffd700]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[0.72rem] font-bold text-[#ffd700]">
                        Banker (Aposta Fixa)
                      </span>
                      <span
                        className="text-[0.5rem] font-bold uppercase tracking-wider px-1.5 py-px rounded-full"
                        style={{ background: "rgba(255,215,0,0.12)", color: "#ffd700" }}
                      >
                        Premium
                      </span>
                    </div>
                    <p className="text-[0.58rem] text-[var(--color-text-muted)]">
                      {suggestion.banker.reason}
                    </p>
                  </div>
                </div>
                <div
                  className="flex items-center justify-between px-3 py-2 rounded-lg"
                  style={{ background: "rgba(255,215,0,0.05)", border: "1px solid rgba(255,215,0,0.12)" }}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Crown size={10} className="text-[#ffd700] shrink-0" />
                    <span className="text-[0.7rem] font-semibold text-[var(--color-text-primary)] truncate">
                      {suggestion.banker.allocation.bet.homeTeam} x {suggestion.banker.allocation.bet.awayTeam}
                    </span>
                    <span
                      className="text-[0.58rem] font-medium px-1.5 py-px rounded shrink-0"
                      style={{ background: "rgba(255,215,0,0.1)", color: "#ffd700" }}
                    >
                      {suggestion.banker.allocation.bet.market}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[0.6rem] text-[var(--color-text-muted)] tabular-nums">
                      odd {suggestion.banker.allocation.bet.odd.toFixed(2)}
                    </span>
                    <span className="text-[0.6rem] font-bold tabular-nums" style={{ color: evColor(suggestion.banker.allocation.ev) }}>
                      EV +{(suggestion.banker.allocation.ev * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
                <p className="text-[0.58rem] text-[var(--color-text-muted)] mt-2 leading-relaxed">
                  O Banker esta presente em todas as combinacoes e aumenta o retorno potencial,
                  barateando o custo das multiplas linhas — mas a aposta inteira e perdida se o Banker falhar.
                </p>
              </div>
            </div>
          )}

          {/* ── Rule 2: Stake Distribution Info ── */}
          <div
            className="flex items-start gap-2.5 px-4 py-3 rounded-xl"
            style={{
              background: `${accentBg}0.05)`,
              border: `1px solid ${accentBg}0.12)`,
            }}
          >
            <CircleDollarSign size={14} style={{ color: accent }} className="shrink-0 mt-0.5" />
            <div className="text-[0.65rem] text-[var(--color-text-secondary)] leading-relaxed">
              <strong style={{ color: accent }}>Distribuicao de Stake (Kelly):</strong>{" "}
              O valor total de {formatCurrency(suggestion.totalStake)} (via criterio de Kelly fracionado)
              e dividido igualmente entre as {suggestion.totalCombinations} linhas de aposta.
              Cada linha recebe <strong style={{ color: "var(--color-text-primary)" }}>{formatCurrency(suggestion.stakePerLine)}</strong>.
              Isso impede que o valor total seja investido em cada linha separadamente.
            </div>
          </div>

          {/* ── Selections ── */}
          <div>
            <div className="text-[0.65rem] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
              Selecoes ({suggestion.selections.length} jogos +EV)
            </div>
            <div className="space-y-1.5">
              {suggestion.selections.map((a, i) => {
                const isBanker = suggestion.banker?.allocation.bet.id === a.bet.id;
                return (
                  <div
                    key={a.bet.id}
                    className="flex items-center justify-between px-2.5 py-2 rounded-lg"
                    style={{
                      background: isBanker ? "rgba(255,215,0,0.05)" : `${accentBg}0.04)`,
                      border: `1px solid ${isBanker ? "rgba(255,215,0,0.15)" : `${accentBg}0.1)`}`,
                    }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div
                        className="w-5 h-5 rounded-full flex items-center justify-center text-[0.55rem] font-bold shrink-0"
                        style={{
                          background: isBanker ? "rgba(255,215,0,0.15)" : `${accentBg}0.15)`,
                          color: isBanker ? "#ffd700" : accent,
                        }}
                      >
                        {isBanker ? <Crown size={10} /> : i + 1}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[0.7rem] font-semibold text-[var(--color-text-primary)] truncate">
                            {a.bet.homeTeam} x {a.bet.awayTeam}
                          </span>
                          {isBanker && (
                            <span
                              className="text-[0.48rem] font-bold uppercase px-1 py-px rounded"
                              style={{ background: "rgba(255,215,0,0.12)", color: "#ffd700" }}
                            >
                              Banker
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span
                            className="text-[0.58rem] font-medium px-1.5 py-px rounded"
                            style={{ background: `${accentBg}0.1)`, color: accent }}
                          >
                            {a.bet.market}
                          </span>
                          <span className="text-[0.55rem] text-[var(--color-text-muted)]">
                            odd {a.bet.odd.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-[0.68rem] font-bold" style={{ color: evColor(a.ev) }}>
                        EV {a.ev > 0 ? "+" : ""}{(a.ev * 100).toFixed(1)}%
                      </div>
                      <div className="text-[0.55rem] text-[var(--color-text-muted)]">
                        {a.bet.leagueName}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Combinations breakdown (collapsible) ── */}
          <div>
            <button
              onClick={(e) => { e.stopPropagation(); setShowCombos(!showCombos); }}
              className="flex items-center gap-1.5 text-[0.65rem] font-semibold uppercase tracking-wider mb-2 transition-colors"
              style={{ color: "var(--color-text-muted)" }}
            >
              {showCombos ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Detalhamento das {suggestion.totalCombinations} Combinacoes
            </button>
            {showCombos && (
              <div className="space-y-1 animate-in fade-in slide-in-from-top-1 duration-150">
                {suggestion.combinations.map((c, i) => {
                  const legsLabel = c.legs.length === 1
                    ? "Simples"
                    : c.legs.length === 2
                      ? "Dupla"
                      : c.legs.length === 3
                        ? "Tripla"
                        : "Quadrupla";
                  const teamsLabel = c.legs
                    .map((l) => l.bet.homeTeam.split(" ")[0])
                    .join(" + ");

                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[0.65rem]"
                      style={{
                        background: i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent",
                      }}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="text-[0.55rem] font-bold uppercase px-1.5 py-px rounded shrink-0"
                          style={{
                            background: c.legs.length === 1
                              ? "rgba(34,197,94,0.1)"
                              : c.legs.length === 2
                                ? "rgba(157,80,255,0.1)"
                                : c.legs.length === 3
                                  ? "rgba(0,187,255,0.1)"
                                  : "rgba(255,170,68,0.1)",
                            color: c.legs.length === 1
                              ? "#22c55e"
                              : c.legs.length === 2
                                ? "#c4a0ff"
                                : c.legs.length === 3
                                  ? "#00bbff"
                                  : "#ffaa44",
                          }}
                        >
                          {legsLabel}
                        </span>
                        <span className="text-[var(--color-text-secondary)] truncate">
                          {teamsLabel}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[var(--color-text-muted)] tabular-nums">
                          odd {c.combinedOdd.toFixed(2)}
                        </span>
                        <span className="text-[var(--color-text-muted)] tabular-nums">
                          {formatCurrency(c.stake)}
                        </span>
                        <span className="font-bold text-[#22c55e] tabular-nums">
                          {formatCurrency(c.potentialReturn)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Rule 5: Break-even status ── */}
          <div
            className="flex items-center gap-2 text-[0.65rem] px-3 py-2 rounded-lg"
            style={{
              background: suggestion.passesBreakEven ? "rgba(34,197,94,0.05)" : "rgba(255,85,85,0.05)",
              border: `1px solid ${suggestion.passesBreakEven ? "rgba(34,197,94,0.12)" : "rgba(255,85,85,0.12)"}`,
              color: "var(--color-text-secondary)",
            }}
          >
            {suggestion.passesBreakEven ? (
              <ShieldCheck size={12} className="text-[#22c55e] shrink-0" />
            ) : (
              <AlertTriangle size={12} className="text-[#ff5555] shrink-0" />
            )}
            <span>
              {suggestion.passesBreakEven
                ? `Filtro de rentabilidade aprovado — o acerto minimo cobre o investimento total de ${formatCurrency(suggestion.totalStake)}.`
                : suggestion.breakEvenReason}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Component ── */
export default function BankrollCalculator() {
  const [settings, setSettings] = useState<BankrollSettings>(DEFAULT_SETTINGS);
  const [combinadas, setCombinadas] = useState<CombinadasData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [bankrollInput, setBankrollInput] = useState("");
  const [showKellyInfo, setShowKellyInfo] = useState(false);
  const [excludedBets, setExcludedBets] = useState<Set<string>>(new Set());
  const [stakeOverrides, setStakeOverrides] = useState<Record<string, number>>({});
  const [showSystemBet, setShowSystemBet] = useState(false);

  // Load settings on mount
  useEffect(() => {
    const saved = loadSettings();
    setSettings(saved);
    setBankrollInput(saved.bankroll.toString());
  }, []);

  // Save settings on change (#190: skip the first pass so DEFAULT_SETTINGS never
  // overwrites the persisted bankroll before the load effect above lands)
  const skipFirstSave = useRef(true);
  useEffect(() => {
    if (skipFirstSave.current) {
      skipFirstSave.current = false;
      return;
    }
    saveSettings(settings);
  }, [settings]);

  // #190: reflect bankroll changes made on the dashboard / other tabs live
  useEffect(
    () =>
      subscribeBankroll(() => {
        const v = getBankroll();
        setSettings((s) => (s.bankroll === v ? s : { ...s, bankroll: v }));
        setBankrollInput((prev) => (parseFloat(prev) === v ? prev : v.toString()));
      }),
    []
  );

  // Fetch combinadas
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/combinadas?tipos=intra,inter&min_status=NEUTRO&limite_intra=15&limite_inter=15");
      if (!res.ok) throw new Error("Erro ao carregar dados");
      const data = await res.json();
      if (data._error) throw new Error(data._error.message || "Backend indisponível");
      setCombinadas(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Convert combinadas to bet inputs (excluding removed bets)
  const bets = useMemo(() => {
    if (!combinadas) return [];
    return combinadasToBets(combinadas).filter((b) => !excludedBets.has(b.id));
  }, [combinadas, excludedBets]);

  // Calculate distribution
  const distribution = useMemo(() => {
    if (bets.length === 0) return null;
    const dist = distributeBankroll(
      bets,
      settings.bankroll,
      {
        simples: settings.pctSimples,
        dupla_intra: settings.pctIntra,
        dupla_inter: settings.pctInter,
      },
      KELLY_MULTIPLIERS[settings.kellyMode],
    );
    // Apply stake overrides
    for (const cat of ["simples", "dupla_intra", "dupla_inter"] as const) {
      for (const alloc of dist[cat]) {
        if (stakeOverrides[alloc.bet.id] !== undefined) {
          alloc.stake = stakeOverrides[alloc.bet.id];
          alloc.potentialReturn = Math.round(alloc.stake * alloc.bet.odd * 100) / 100;
          alloc.potentialProfit = Math.round((alloc.potentialReturn - alloc.stake) * 100) / 100;
        }
      }
    }
    // Recalculate totals after overrides
    const allAllocs = [...dist.simples, ...dist.dupla_intra, ...dist.dupla_inter];
    dist.totalStaked = allAllocs.reduce((s, a) => s + a.stake, 0);
    dist.expectedReturn = allAllocs.reduce((s, a) => s + a.stake * (1 + a.ev), 0);
    dist.expectedProfit = dist.expectedReturn - dist.totalStaked;
    dist.unutilized = settings.bankroll - dist.totalStaked;
    return dist;
  }, [bets, settings, stakeOverrides]);

  const handleRemoveBet = useCallback((betId: string) => {
    setExcludedBets((prev) => { const next = new Set(Array.from(prev)); next.add(betId); return next; });
    setStakeOverrides((prev) => {
      const next = { ...prev };
      delete next[betId];
      return next;
    });
  }, []);

  const handleStakeChange = useCallback((betId: string, newStake: number) => {
    setStakeOverrides((prev) => ({ ...prev, [betId]: newStake }));
  }, []);

  const totalPct = settings.pctSimples + settings.pctIntra + settings.pctInter;

  const updateSetting = <K extends keyof BankrollSettings>(
    key: K,
    value: BankrollSettings[K],
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleBankrollChange = (val: string) => {
    setBankrollInput(val);
    const num = parseFloat(val.replace(/[^\d.,]/g, "").replace(",", "."));
    if (!isNaN(num) && num >= 0) {
      updateSetting("bankroll", num);
    }
  };

  const toggleSection = (key: string) => {
    setCollapsedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const allBets = distribution
    ? [...distribution.simples, ...distribution.dupla_intra, ...distribution.dupla_inter]
    : [];
  const totalEV = allBets.length > 0
    ? allBets.reduce((sum, a) => sum + a.ev, 0) / allBets.length
    : 0;

  return (
    <div className="min-h-screen" style={{ background: "var(--color-bg-primary)" }}>
      {/* Hero Header */}
      <div className="relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 30% 0%, rgba(34,197,94,0.08) 0%, transparent 60%), radial-gradient(ellipse at 70% 0%, rgba(157,80,255,0.06) 0%, transparent 60%)",
          }}
        />
        <div className="relative max-w-2xl mx-auto px-4 pt-6 pb-4">
          <div className="flex items-center gap-3 mb-1">
            <a
              href="/dashboard"
              className="flex items-center gap-1 text-[0.72rem] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
            >
              <ArrowLeft size={14} />
              Dashboard
            </a>
          </div>
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, rgba(34,197,94,0.2), rgba(157,80,255,0.2))",
                boxShadow: "0 0 24px rgba(34,197,94,0.15)",
              }}
            >
              <Wallet size={22} className="text-[#22c55e]" />
            </div>
            <div>
              <h1 className="text-xl font-black text-[var(--color-text-primary)] tracking-tight">
                Gestão de Banca
              </h1>
              <p className="text-[0.72rem] text-[var(--color-text-muted)]">
                Distribuicao inteligente com criterio de Kelly
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 pb-8 space-y-5">
        {/* ── Bankroll Input Card ── */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "var(--color-bg-card)",
            borderColor: "var(--color-border)",
          }}
        >
          <div className="p-5">
            <label className="text-[0.7rem] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3 block">
              Valor da Banca
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl font-bold text-[#22c55e]">
                R$
              </span>
              <input
                type="text"
                value={bankrollInput}
                onChange={(e) => handleBankrollChange(e.target.value)}
                className="w-full h-16 pl-14 pr-4 text-3xl font-black rounded-xl border-2 transition-all duration-200 focus:outline-none tabular-nums"
                style={{
                  background: "rgba(34,197,94,0.04)",
                  borderColor: "rgba(34,197,94,0.2)",
                  color: "var(--color-text-primary)",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "rgba(34,197,94,0.5)";
                  e.target.style.boxShadow = "0 0 20px rgba(34,197,94,0.1)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "rgba(34,197,94,0.2)";
                  e.target.style.boxShadow = "none";
                }}
                placeholder="1000"
              />
            </div>

            {/* Quick presets */}
            <div className="flex gap-2 mt-3">
              {[100, 500, 1000, 2000, 5000].map((v) => (
                <button
                  key={v}
                  onClick={() => {
                    updateSetting("bankroll", v);
                    setBankrollInput(v.toString());
                  }}
                  className="flex-1 py-1.5 rounded-lg text-[0.68rem] font-bold transition-all duration-150 hover:scale-105"
                  style={{
                    background:
                      settings.bankroll === v
                        ? "rgba(34,197,94,0.15)"
                        : "rgba(255,255,255,0.04)",
                    color:
                      settings.bankroll === v ? "#22c55e" : "var(--color-text-muted)",
                    border: `1px solid ${
                      settings.bankroll === v
                        ? "rgba(34,197,94,0.3)"
                        : "rgba(255,255,255,0.06)"
                    }`,
                  }}
                >
                  {v >= 1000 ? `${v / 1000}k` : v}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Allocation Sliders ── */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "var(--color-bg-card)",
            borderColor: "var(--color-border)",
          }}
        >
          <div className="p-5 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PieChart size={16} className="text-[var(--color-text-muted)]" />
                <span className="text-[0.7rem] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                  Alocacao por Categoria
                </span>
              </div>
              <div
                className="text-[0.7rem] font-bold tabular-nums px-2 py-0.5 rounded-md"
                style={{
                  color: totalPct === 100 ? "#22c55e" : totalPct > 100 ? "#ff5555" : "#ffaa44",
                  background:
                    totalPct === 100
                      ? "rgba(34,197,94,0.1)"
                      : totalPct > 100
                        ? "rgba(255,85,85,0.1)"
                        : "rgba(255,170,68,0.1)",
                }}
              >
                {totalPct}% / 100%
              </div>
            </div>

            <BankSlider
              label="Simples"
              value={settings.pctSimples}
              onChange={(v) => updateSetting("pctSimples", v)}
              icon={<Target size={16} style={{ color: "#22c55e" }} />}
              color="#22c55e"
              description="Apostas unitarias com alto EV"
              allocations={distribution?.simples}
              bankroll={settings.bankroll}
              onRemoveBet={handleRemoveBet}
              onStakeChange={handleStakeChange}
            />

            <BankSlider
              label="Duplas Intra"
              value={settings.pctIntra}
              onChange={(v) => updateSetting("pctIntra", v)}
              icon={<Layers size={16} style={{ color: "#c4a0ff" }} />}
              color="#c4a0ff"
              description="Dois mercados no mesmo jogo"
              allocations={distribution?.dupla_intra}
              bankroll={settings.bankroll}
              onRemoveBet={handleRemoveBet}
              onStakeChange={handleStakeChange}
            />

            <BankSlider
              label="Duplas Inter"
              value={settings.pctInter}
              onChange={(v) => updateSetting("pctInter", v)}
              icon={<Link2 size={16} style={{ color: "#00bbff" }} />}
              color="#00bbff"
              description="Mercados em jogos diferentes"
              allocations={distribution?.dupla_inter}
              bankroll={settings.bankroll}
              onRemoveBet={handleRemoveBet}
              onStakeChange={handleStakeChange}
            />

            {totalPct !== 100 && (
              <div
                className="flex items-center gap-2 text-[0.72rem] px-3 py-2 rounded-lg"
                style={{
                  background:
                    totalPct > 100
                      ? "rgba(255,85,85,0.08)"
                      : "rgba(255,170,68,0.08)",
                  color: totalPct > 100 ? "#ff5555" : "#ffaa44",
                }}
              >
                <AlertTriangle size={14} />
                {totalPct > 100
                  ? `Alocação excede 100% em ${totalPct - 100}%. Ajuste os sliders.`
                  : `${100 - totalPct}% da banca não será alocada.`}
              </div>
            )}
          </div>
        </div>

        {/* ── Kelly Mode Selector ── */}
        <div
          className="rounded-2xl border overflow-hidden"
          style={{
            background: "var(--color-bg-card)",
            borderColor: "var(--color-border)",
          }}
        >
          <div className="p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Zap size={16} className="text-[var(--color-text-muted)]" />
                <span className="text-[0.7rem] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                  Criterio de Kelly
                </span>
              </div>
              <button
                onClick={() => setShowKellyInfo(!showKellyInfo)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
              >
                <Info size={14} />
              </button>
            </div>

            {showKellyInfo && (
              <div
                className="mb-4 p-3 rounded-lg text-[0.72rem] leading-relaxed"
                style={{
                  background: "rgba(157,80,255,0.06)",
                  color: "var(--color-text-secondary)",
                  border: "1px solid rgba(157,80,255,0.15)",
                }}
              >
                <strong style={{ color: "#c4a0ff" }}>Criterio de Kelly</strong> calcula a
                fracao ideal da banca para cada aposta com base na probabilidade real vs
                odd oferecida. Versoes fracionarias (1/4, 1/2) reduzem a volatilidade.
                <br />
                <span className="text-[var(--color-text-muted)]">
                  Formula: f* = (p x b - q) / b, onde p = probabilidade, b = odd - 1, q =
                  1 - p
                </span>
              </div>
            )}

            <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
              {(
                [
                  { mode: "quarter" as const, label: "1/4 Kelly", desc: "Conservador" },
                  { mode: "half" as const, label: "1/2 Kelly", desc: "Moderado" },
                  { mode: "full" as const, label: "Full Kelly", desc: "Agressivo" },
                ] as const
              ).map(({ mode, label, desc }) => (
                <button
                  key={mode}
                  onClick={() => updateSetting("kellyMode", mode)}
                  className="relative py-2.5 px-1.5 sm:py-3 sm:px-2 rounded-xl border-2 transition-all duration-200 hover:scale-[1.02]"
                  style={{
                    background:
                      settings.kellyMode === mode
                        ? "rgba(157,80,255,0.08)"
                        : "rgba(255,255,255,0.02)",
                    borderColor:
                      settings.kellyMode === mode
                        ? "rgba(157,80,255,0.4)"
                        : "rgba(255,255,255,0.06)",
                  }}
                >
                  {settings.kellyMode === mode && (
                    <div
                      className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] rounded-b"
                      style={{
                        background: "#c4a0ff",
                        boxShadow: "0 0 8px rgba(157,80,255,0.5)",
                      }}
                    />
                  )}
                  <div
                    className="text-[0.78rem] sm:text-sm font-bold mb-0.5"
                    style={{
                      color:
                        settings.kellyMode === mode
                          ? "#c4a0ff"
                          : "var(--color-text-primary)",
                    }}
                  >
                    {label}
                  </div>
                  <div className="text-[0.55rem] sm:text-[0.6rem] text-[var(--color-text-muted)]">{desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Summary Stats ── */}
        {distribution && (
          <div
            className="rounded-2xl border overflow-hidden"
            style={{
              background: "linear-gradient(135deg, rgba(34,197,94,0.04), rgba(157,80,255,0.04))",
              borderColor: "rgba(34,197,94,0.2)",
            }}
          >
            <div className="p-5">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                    Total Apostado
                  </div>
                  <div className="text-lg font-black text-[var(--color-text-primary)] tabular-nums">
                    {formatCurrency(distribution.totalStaked)}
                  </div>
                </div>
                <div>
                  <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                    Retorno Esperado
                  </div>
                  <div className="text-lg font-black text-[#22c55e] tabular-nums">
                    {formatCurrency(distribution.expectedReturn)}
                  </div>
                </div>
                <div>
                  <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                    Lucro Esperado
                  </div>
                  <div
                    className="text-lg font-black tabular-nums"
                    style={{
                      color: distribution.expectedProfit > 0 ? "#22c55e" : "#ff5555",
                    }}
                  >
                    {distribution.expectedProfit > 0 ? "+" : ""}
                    {formatCurrency(distribution.expectedProfit)}
                  </div>
                </div>
                <div>
                  <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                    EV Medio
                  </div>
                  <div
                    className="text-lg font-black tabular-nums"
                    style={{ color: evColor(totalEV) }}
                  >
                    {totalEV > 0 ? "+" : ""}
                    {(totalEV * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {distribution.unutilized > 0.01 && (
                <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
                  <span className="text-[0.68rem] text-[var(--color-text-muted)]">
                    Reserva nao alocada
                  </span>
                  <span className="text-sm font-bold text-[var(--color-text-muted)] tabular-nums">
                    {formatCurrency(distribution.unutilized)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Loading / Error ── */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(157,80,255,0.1)" }}
            >
              <Loader2 size={24} className="text-[#c4a0ff] animate-spin" />
            </div>
            <span className="text-sm text-[var(--color-text-muted)]">
              Carregando apostas do dia...
            </span>
          </div>
        )}

        {error && (
          <div
            className="rounded-2xl border p-5 text-center"
            style={{
              background: "rgba(255,85,85,0.04)",
              borderColor: "rgba(255,85,85,0.2)",
            }}
          >
            <div className="text-[0.82rem] text-[#ff5555] mb-2">
              Erro ao carregar dados
            </div>
            <div className="text-[0.72rem] text-[var(--color-text-muted)] mb-3">
              {error}
            </div>
            <button
              onClick={fetchData}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[0.72rem] font-semibold transition-colors"
              style={{
                background: "rgba(255,85,85,0.1)",
                color: "#ff5555",
                border: "1px solid rgba(255,85,85,0.2)",
              }}
            >
              <RefreshCw size={12} />
              Tentar novamente
            </button>
          </div>
        )}

        {/* ── Empty state when no bets available ── */}
        {!distribution && !loading && !error && (
          <div
            className="rounded-2xl border p-8 text-center"
            style={{
              background: "var(--color-bg-card)",
              borderColor: "var(--color-border)",
            }}
          >
            <ShieldCheck
              size={32}
              className="mx-auto mb-3 text-[var(--color-text-muted)]"
            />
            <div className="text-sm text-[var(--color-text-muted)]">
              Nenhuma aposta disponivel no momento.
            </div>
            <div className="text-[0.7rem] text-[var(--color-text-muted)] mt-1">
              Aguarde os jogos do dia serem carregados ou verifique se o backend esta ativo.
            </div>
            <button
              onClick={fetchData}
              className="inline-flex items-center gap-1.5 px-4 py-2 mt-3 rounded-lg text-[0.72rem] font-semibold transition-colors"
              style={{
                background: "rgba(157,80,255,0.1)",
                color: "#c4a0ff",
                border: "1px solid rgba(157,80,255,0.2)",
              }}
            >
              <RefreshCw size={12} />
              Recarregar
            </button>
          </div>
        )}

        {/* ── Bet Allocations ── */}
        {distribution && !loading && (
          <div className="space-y-2">
            {/* Simples */}
            {distribution.simples.length > 0 && (
              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  background: "var(--color-bg-card)",
                  borderColor: "var(--color-border)",
                }}
              >
                <div className="px-4">
                  <SectionHeader
                    icon={<Target size={16} style={{ color: "#22c55e" }} />}
                    title="Simples"
                    count={distribution.simples.length}
                    totalStake={distribution.simples.reduce((s, a) => s + a.stake, 0)}
                    color="#22c55e"
                    collapsed={!!collapsedSections.simples}
                    onToggle={() => toggleSection("simples")}
                  />
                </div>
                {!collapsedSections.simples && (
                  <div className="px-4 pb-4 space-y-2">
                    {distribution.simples.map((a, i) => (
                      <AllocationCard key={a.bet.id} allocation={a} index={i} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Duplas Intra */}
            {distribution.dupla_intra.length > 0 && (
              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  background: "var(--color-bg-card)",
                  borderColor: "var(--color-border)",
                }}
              >
                <div className="px-4">
                  <SectionHeader
                    icon={<Layers size={16} style={{ color: "#c4a0ff" }} />}
                    title="Duplas Intra-jogo"
                    count={distribution.dupla_intra.length}
                    totalStake={distribution.dupla_intra.reduce((s, a) => s + a.stake, 0)}
                    color="#c4a0ff"
                    collapsed={!!collapsedSections.dupla_intra}
                    onToggle={() => toggleSection("dupla_intra")}
                  />
                </div>
                {!collapsedSections.dupla_intra && (
                  <div className="px-4 pb-4 space-y-2">
                    {distribution.dupla_intra.map((a, i) => (
                      <AllocationCard key={a.bet.id} allocation={a} index={i} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Duplas Inter */}
            {distribution.dupla_inter.length > 0 && (
              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  background: "var(--color-bg-card)",
                  borderColor: "var(--color-border)",
                }}
              >
                <div className="px-4">
                  <SectionHeader
                    icon={<Link2 size={16} style={{ color: "#00bbff" }} />}
                    title="Duplas Inter-jogo"
                    count={distribution.dupla_inter.length}
                    totalStake={distribution.dupla_inter.reduce((s, a) => s + a.stake, 0)}
                    color="#00bbff"
                    collapsed={!!collapsedSections.dupla_inter}
                    onToggle={() => toggleSection("dupla_inter")}
                  />
                </div>
                {!collapsedSections.dupla_inter && (
                  <div className="px-4 pb-4 space-y-2">
                    {distribution.dupla_inter.map((a, i) => (
                      <AllocationCard key={a.bet.id} allocation={a} index={i} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {allBets.length === 0 && (
              <div
                className="rounded-2xl border p-8 text-center"
                style={{
                  background: "var(--color-bg-card)",
                  borderColor: "var(--color-border)",
                }}
              >
                <ShieldCheck
                  size={32}
                  className="mx-auto mb-3 text-[var(--color-text-muted)]"
                />
                <div className="text-sm text-[var(--color-text-muted)]">
                  Nenhuma aposta com EV positivo encontrada.
                </div>
                <div className="text-[0.7rem] text-[var(--color-text-muted)] mt-1">
                  As odds atuais nao oferecem valor suficiente para distribuicao.
                </div>
              </div>
            )}

            {/* Rule 1: System Bet — button + card */}
            {distribution.systemBet && (
              <div className="space-y-3">
                {!showSystemBet ? (
                  <button
                    onClick={() => setShowSystemBet(true)}
                    className="w-full py-3.5 rounded-2xl border-2 border-dashed font-bold text-sm transition-all duration-200 hover:scale-[1.01] flex items-center justify-center gap-2"
                    style={{
                      borderColor: distribution.systemBet.recommended
                        ? "rgba(255,170,68,0.3)"
                        : "rgba(255,85,85,0.2)",
                      background: distribution.systemBet.recommended
                        ? "rgba(255,170,68,0.04)"
                        : "rgba(255,85,85,0.03)",
                      color: distribution.systemBet.recommended ? "#ffaa44" : "#ff5555",
                    }}
                  >
                    <Shuffle size={16} />
                    Montar Aposta em Sistema
                    <span
                      className="text-[0.58rem] font-bold uppercase px-2 py-0.5 rounded-full ml-1"
                      style={{
                        background: distribution.systemBet.recommended
                          ? "rgba(255,170,68,0.12)"
                          : "rgba(255,85,85,0.1)",
                      }}
                    >
                      {distribution.systemBet.label} &middot; {distribution.systemBet.totalCombinations} linhas
                    </span>
                  </button>
                ) : (
                  <SystemBetCard suggestion={distribution.systemBet} />
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Footer disclaimer ── */}
        <div className="text-center pb-4">
          <p className="text-[0.62rem] text-[var(--color-text-muted)] leading-relaxed max-w-md mx-auto">
            Gestão de banca baseada no criterio de Kelly fracionario. Os valores sao
            sugestoes matematicas e nao garantem resultados. Aposte com responsabilidade.
          </p>
        </div>
      </div>
    </div>
  );
}
