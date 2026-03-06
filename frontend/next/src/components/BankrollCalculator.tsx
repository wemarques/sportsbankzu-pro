"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
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
} from "lucide-react";
import {
  type BetInput,
  type BetAllocation,
  type BankrollSettings,
  distributeBankroll,
  loadSettings,
  saveSettings,
  DEFAULT_SETTINGS,
  KELLY_MULTIPLIERS,
} from "@/lib/kelly";

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
      if (!seenLegs.has(key) && leg.status.toUpperCase().startsWith("SAFE")) {
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

/* ── Slider Component ── */
function BankSlider({
  label,
  value,
  onChange,
  icon,
  color,
  description,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  icon: React.ReactNode;
  color: string;
  description: string;
}) {
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
            <div className="text-base font-black text-[var(--color-text-primary)]">
              {formatCurrency(allocation.stake)}
            </div>
            <div className="text-[0.6rem] text-[var(--color-text-muted)] uppercase tracking-wider">
              stake
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
          <div className="flex items-center gap-3">
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
            <div className="grid grid-cols-3 gap-3">
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

/* ── Main Component ── */
export default function BankrollCalculator() {
  const [settings, setSettings] = useState<BankrollSettings>(DEFAULT_SETTINGS);
  const [combinadas, setCombinadas] = useState<CombinadasData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [bankrollInput, setBankrollInput] = useState("");
  const [showKellyInfo, setShowKellyInfo] = useState(false);

  // Load settings on mount
  useEffect(() => {
    const saved = loadSettings();
    setSettings(saved);
    setBankrollInput(saved.bankroll.toString());
  }, []);

  // Save settings on change
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  // Fetch combinadas
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/combinadas?tipos=intra,inter&min_status=NEUTRO&limite_intra=15&limite_inter=15");
      if (!res.ok) throw new Error("Erro ao carregar dados");
      const data = await res.json();
      if (data._error) throw new Error(data._error.message || "Backend indisponivel");
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

  // Convert combinadas to bet inputs
  const bets = useMemo(() => {
    if (!combinadas) return [];
    return combinadasToBets(combinadas);
  }, [combinadas]);

  // Calculate distribution
  const distribution = useMemo(() => {
    if (bets.length === 0) return null;
    return distributeBankroll(
      bets,
      settings.bankroll,
      {
        simples: settings.pctSimples,
        dupla_intra: settings.pctIntra,
        dupla_inter: settings.pctInter,
      },
      KELLY_MULTIPLIERS[settings.kellyMode],
    );
  }, [bets, settings]);

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
                Gestao de Banca
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
            />

            <BankSlider
              label="Duplas Intra"
              value={settings.pctIntra}
              onChange={(v) => updateSetting("pctIntra", v)}
              icon={<Layers size={16} style={{ color: "#c4a0ff" }} />}
              color="#c4a0ff"
              description="Dois mercados no mesmo jogo"
            />

            <BankSlider
              label="Duplas Inter"
              value={settings.pctInter}
              onChange={(v) => updateSetting("pctInter", v)}
              icon={<Link2 size={16} style={{ color: "#00bbff" }} />}
              color="#00bbff"
              description="Mercados em jogos diferentes"
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
                  ? `Alocacao excede 100% em ${totalPct - 100}%. Ajuste os sliders.`
                  : `${100 - totalPct}% da banca nao sera alocado.`}
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

            <div className="grid grid-cols-3 gap-2">
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
                  className="relative py-3 px-2 rounded-xl border-2 transition-all duration-200 hover:scale-[1.02]"
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
                    className="text-sm font-bold mb-0.5"
                    style={{
                      color:
                        settings.kellyMode === mode
                          ? "#c4a0ff"
                          : "var(--color-text-primary)",
                    }}
                  >
                    {label}
                  </div>
                  <div className="text-[0.6rem] text-[var(--color-text-muted)]">{desc}</div>
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
          </div>
        )}

        {/* ── Footer disclaimer ── */}
        <div className="text-center pb-4">
          <p className="text-[0.62rem] text-[var(--color-text-muted)] leading-relaxed max-w-md mx-auto">
            Gestao de banca baseada no criterio de Kelly fracionario. Os valores sao
            sugestoes matematicas e nao garantem resultados. Aposte com responsabilidade.
          </p>
        </div>
      </div>
    </div>
  );
}
