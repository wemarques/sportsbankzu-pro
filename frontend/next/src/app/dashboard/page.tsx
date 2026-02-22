"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import MatchDetailCard, {
  type MatchDetailData,
  type AIAnalysis,
  type AuditResult,
  type AuditCorrection,
} from "@/components/MatchDetailCard";
import { AVAILABLE_LEAGUES, type Match } from "@/lib/leagues";
import { getMatchesByLeague, getAiMatchAnalysis, postMatchAudit, applyAuditCorrection } from "@/lib/api";
import {
  Star,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  Loader2,
  Flame,
  Radio,
  Bot,
  SlidersHorizontal,
  Heart,
  Filter,
  Bell,
  Trophy,
  Wrench,
  Sparkles,
  ArrowLeft,
  TrendingUp,
  BarChart3,
  Calculator,
  Brain,
  Target,
  Zap,
  Share2,
  Copy,
  MessageCircle,
} from "lucide-react";
import "@/styles/scoretabs-dashboard.css";

const APP_VERSION = "pro V2.6";
const SHARE_TEXT = "Confira os jogos e picks gerados no SportsBank Pro.";

type NavView = "matches" | "campeonatos" | "ferramentas" | "recomendadas";
type ShareFeedbackTone = "success" | "error" | "info";

type OddsTab = "1x2" | "double-chance" | "btts" | "goals" | "cards" | "corners";
type DateMode = "today" | "tomorrow" | "week";

type LeagueGroup = {
  leagueId: string;
  leagueName: string;
  countryFlag: string;
  country: string;
  matches: Match[];
  collapsed: boolean;
};

/* ── helpers ── */

function safeOdd(value?: number, fallback = 0) {
  if (!value || value <= 0) return fallback;
  return value;
}

function formatTime(dt: string) {
  try {
    const d = new Date(dt);
    return d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch {
    return "--:--";
  }
}

function formatDate(dt: string) {
  try {
    const d = new Date(dt);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch {
    return "--/--";
  }
}
/** Normaliza probabilidade para percentual 0-100. Aceita 0-1, 0-100 ou valores >100. */
function toPercent(value?: number | null): number {
  if (value == null || value < 0) return 0;
  if (value <= 1) return value * 100;
  if (value > 100) return value / 100;
  return value;
}

/** Normaliza e formata probabilidade em decimal (ex: 85.5%). */
function formatProb(value?: number | null): string {
  if (value == null || value < 0) return "-";
  const pct = toPercent(value);
  return `${pct.toFixed(1)}%`;
}

function statusInfo(status: Match["status"]) {
  switch (status) {
    case "live":
      return { label: "AO VIVO", cssClass: "st-match-row__status-label--live" };
    case "finished":
      return { label: "FT", cssClass: "st-match-row__status-label--ft" };
    case "postponed":
      return { label: "ADIADO", cssClass: "st-match-row__status-label--ft" };
    default:
      return { label: "", cssClass: "st-match-row__status-label--scheduled" };
  }
}

function getLowestOddIndex(home: number, draw: number, away: number): number {
  const vals = [home, draw, away];
  const min = Math.min(...vals.filter((v) => v > 0));
  return vals.indexOf(min);
}

function buildScreenshotName() {
  const stamp = new Date().toISOString().replace(/[:]/g, "-").replace("T", "_").slice(0, 19);
  return `sportsbank-picks-${stamp}.png`;
}

function normalizeMatch(item: any, leagueId: string, idx: number): Match {
  const home = item.home_team
    ?? (typeof item.homeTeam === "string" ? item.homeTeam : item.homeTeam?.name)
    ?? item.home ?? "Home";
  const away = item.away_team
    ?? (typeof item.awayTeam === "string" ? item.awayTeam : item.awayTeam?.name)
    ?? item.away ?? "Away";
  const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
  const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
  return {
    id: item.id ?? `${leagueId}-${idx}-${home}-${away}`,
    leagueId,
    leagueName: league?.name ?? leagueId,
    homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? [], rating: item.homeTeam?.rating ?? 0 },
    awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? [], rating: item.awayTeam?.rating ?? 0 },
    datetime: dt,
    venue: item.venue ?? item.stadium ?? "",
    status: item.status ?? "scheduled",
    score: item.score,
    odds: {
      home: item.odds?.home ?? 0,
      draw: item.odds?.draw ?? 0,
      away: item.odds?.away ?? 0,
      over15: item.odds?.over15 ?? 0,
      over25: item.odds?.over25 ?? 0,
      over35: item.odds?.over35 ?? 0,
      over45: item.odds?.over45 ?? 0,
      under25: item.odds?.under25 ?? 0,
      bttsYes: item.odds?.bttsYes ?? 0,
      bttsNo: item.odds?.bttsNo ?? 0,
    },
    stats: {
      homeWinProb: item.stats?.homeWinProb ?? 0,
      drawProb: item.stats?.drawProb ?? 0,
      awayWinProb: item.stats?.awayWinProb ?? 0,
      avgGoals: item.stats?.avgGoals ?? 0,
      bttsProb: item.stats?.bttsProb ?? 0,
      over15Prob: item.stats?.over15Prob ?? 0,
      over25Prob: item.stats?.over25Prob ?? 0,
      over35Prob: item.stats?.over35Prob ?? 0,
      over45Prob: item.stats?.over45Prob ?? 0,
      lambdaHome: item.stats?.lambdaHome ?? 0,
      lambdaAway: item.stats?.lambdaAway ?? 0,
      homePossession: item.stats?.homePossession ?? 0,
      awayPossession: item.stats?.awayPossession ?? 0,
      homeXG: item.stats?.homeXG ?? 0,
      awayXG: item.stats?.awayXG ?? 0,
      homeForm: item.stats?.homeForm ?? item.homeForm ?? item.homeTeam?.form ?? [],
      awayForm: item.stats?.awayForm ?? item.awayForm ?? item.awayTeam?.form ?? [],
      leagueRegime: item.stats?.leagueRegime ?? "",
      leagueVolatility: item.stats?.leagueVolatility ?? "",
      regime: item.stats?.regime ?? "",
      homeCornersPerMatch: item.stats?.homeCornersPerMatch ?? 0,
      awayCornersPerMatch: item.stats?.awayCornersPerMatch ?? 0,
      homeCardsPerMatch: item.stats?.homeCardsPerMatch ?? 0,
      awayCardsPerMatch: item.stats?.awayCardsPerMatch ?? 0,
      leagueAvgCorners: item.stats?.leagueAvgCorners ?? 0,
      leagueAvgCards: item.stats?.leagueAvgCards ?? 0,
    },
    h2h: {
      totalMatches: item.h2h?.totalMatches ?? 0,
      homeWins: item.h2h?.homeWins ?? 0,
      draws: item.h2h?.draws ?? 0,
      awayWins: item.h2h?.awayWins ?? 0,
      avgGoals: item.h2h?.avgGoals ?? 0,
    },
    predictions: item.mercados ?? item.predictions ?? [],
    source: item.source ?? "footystats",
    lastUpdated: item.lastUpdated ?? new Date().toISOString(),
  };
}

function toDetailData(match: Match, aiData: AIAnalysis | null, isAiLoading: boolean): MatchDetailData {
  const h = safeOdd(match.odds?.home, 1.7);
  const d = safeOdd(match.odds?.draw, 3.1);
  const a = safeOdd(match.odds?.away, 3.8);
  const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
  const ai: AIAnalysis | undefined = isAiLoading
    ? { summary: "Carregando analise Mistral...", key_points: ["Buscando insights..."], recommendation: "Aguardando.", confidence: 5, last_updated: new Date().toLocaleString("pt-BR") }
    : aiData ?? undefined;
  return {
    id: match.id,
    league: league?.name ?? match.leagueName ?? match.leagueId,
    leagueId: match.leagueId,
    season: league?.season ?? "2026",
    homeTeam: match.homeTeam.name,
    awayTeam: match.awayTeam.name,
    homeTeamLogo: match.homeTeam.logo || undefined,
    awayTeamLogo: match.awayTeam.logo || undefined,
    startTime: match.datetime,
    status: match.status === "postponed" ? "scheduled" : match.status,
    venue: { name: match.venue || "Estadio nao informado" },
    odds: { home: h, draw: d, away: a },
    doubleChance: {
      homeOrDraw: parseFloat((1 / (1 / h + 1 / d)).toFixed(2)),
      homeOrAway: parseFloat((1 / (1 / h + 1 / a)).toFixed(2)),
      drawOrAway: parseFloat((1 / (1 / d + 1 / a)).toFixed(2)),
    },
    btts: { yes: safeOdd(match.odds?.bttsYes, 2.0), no: safeOdd(match.odds?.bttsNo, 1.7) },
    matchStats: {
      homeWinProb: match.stats?.homeWinProb,
      drawProb: match.stats?.drawProb,
      awayWinProb: match.stats?.awayWinProb,
      avgGoals: match.stats?.avgGoals,
      bttsProb: match.stats?.bttsProb,
      over15Prob: match.stats?.over15Prob,
      over25Prob: match.stats?.over25Prob,
      over35Prob: match.stats?.over35Prob,
      over45Prob: match.stats?.over45Prob,
      lambdaHome: match.stats?.lambdaHome,
      lambdaAway: match.stats?.lambdaAway,
      homePossession: match.stats?.homePossession,
      awayPossession: match.stats?.awayPossession,
      homeXG: match.stats?.homeXG,
      awayXG: match.stats?.awayXG,
      leagueRegime: match.stats?.leagueRegime,
      leagueVolatility: match.stats?.leagueVolatility,
      homeCornersPerMatch: match.stats?.homeCornersPerMatch,
      awayCornersPerMatch: match.stats?.awayCornersPerMatch,
      homeCardsPerMatch: match.stats?.homeCardsPerMatch,
      awayCardsPerMatch: match.stats?.awayCardsPerMatch,
      leagueAvgCorners: match.stats?.leagueAvgCorners,
      leagueAvgCards: match.stats?.leagueAvgCards,
    },
    h2h: match.h2h,
    homeForm: match.stats?.homeForm ?? match.homeTeam.form,
    awayForm: match.stats?.awayForm ?? match.awayTeam.form,
    round: match.stats?.regime ?? "-",
    aiAnalysis: ai,
  };
}

/* ── COMPONENT ── */

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [allMatches, setAllMatches] = useState<Match[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [oddsTab, setOddsTab] = useState<OddsTab>("1x2");
  const [collapsedLeagues, setCollapsedLeagues] = useState<Set<string>>(new Set());
  const [dateMode, setDateMode] = useState<DateMode>("today");
  const [navView, setNavView] = useState<NavView>("matches");
  const [selectedLeague, setSelectedLeague] = useState<string | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => {
    if (typeof window !== "undefined") {
      try {
        const s = localStorage.getItem("sb-favorites");
        if (s) return new Set(JSON.parse(s));
      } catch {}
    }
    return new Set();
  });
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const mainContentRef = useRef<HTMLDivElement>(null);

  // Hook para detectar se estamos em mobile/tablet
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const [shareBusy, setShareBusy] = useState<"copy" | "whatsapp" | null>(null);
  const [shareFeedback, setShareFeedback] = useState("");
  const [shareFeedbackTone, setShareFeedbackTone] = useState<ShareFeedbackTone>("info");
  const capturePanelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { setMounted(true); }, []);

  const dateLabel = dateMode === "today" ? "Hoje" : dateMode === "tomorrow" ? "Amanha" : "Proxima Rodada";

  /* Fetch all leagues — fallback to "week" if today returns empty */
  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      const allLeagueIds = AVAILABLE_LEAGUES.map((l) => l.id).join(",");

      /** Backend espera "today" | "tomorrow" | "week" (timezone BRT), não YYYY-MM-DD */
      function dateParamFor(mode: DateMode): string {
        return mode;
      }

      try {
        let res = await getMatchesByLeague(allLeagueIds, dateParamFor(dateMode));
        let raw = res?.matches ?? [];

        // Auto-fallback: if today returns empty, try week
        if (raw.length === 0 && dateMode === "today") {
          res = await getMatchesByLeague(allLeagueIds, "week");
          raw = res?.matches ?? [];
          if (raw.length > 0) setDateMode("week");
        }

        const normalized = raw.map((item: any, idx: number) => {
          const lid = item.leagueId ?? AVAILABLE_LEAGUES[0]?.id ?? "unknown";
          return normalizeMatch(item, lid, idx);
        });
        setAllMatches(normalized);
        if (normalized.length > 0) setSelectedMatchId(normalized[0].id);
      } catch {
        setAllMatches([]);
      } finally {
        setLoading(false);
      }
    }
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateMode]);

  const selectedMatch = useMemo(() => allMatches.find((m) => m.id === selectedMatchId), [allMatches, selectedMatchId]);

  useEffect(() => {
    async function fetchAi() {
      if (!selectedMatch) {
        setAiAnalysis(null);
        setAuditResult(null);
        return;
      }
      setAiLoading(true);
      setAuditResult(null);
      const analysis = await getAiMatchAnalysis(selectedMatch.id, selectedMatch.homeTeam.name, selectedMatch.awayTeam.name);
      setAiAnalysis(analysis);
      setAiLoading(false);
    }
    fetchAi();
  }, [selectedMatch]);

  const detailData = useMemo<MatchDetailData | null>(() => {
    if (!selectedMatch) return null;
    return toDetailData(selectedMatch, aiAnalysis, aiLoading);
  }, [selectedMatch, aiAnalysis, aiLoading]);

  const toggleLeague = useCallback((lid: string) => {
    setCollapsedLeagues((prev) => {
      const next = new Set(prev);
      next.has(lid) ? next.delete(lid) : next.add(lid);
      return next;
    });
  }, []);

  const displayMatches = useMemo(() => {
    let list = allMatches;
    if (selectedLeague) list = list.filter((m) => m.leagueId === selectedLeague);
    if (showFavoritesOnly) list = list.filter((m) => favoriteIds.has(m.id));
    return list;
  }, [allMatches, selectedLeague, showFavoritesOnly, favoriteIds]);

  const toggleFavorite = useCallback((matchId: string) => {
    setFavoriteIds((prev) => {
      const next = new Set(prev);
      if (next.has(matchId)) next.delete(matchId);
      else next.add(matchId);
      try {
        localStorage.setItem("sb-favorites", JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  }, []);

  const handleTopbarShareWhatsApp = useCallback(async () => {
    const el = mainContentRef.current;
    if (!el) return;
    setShareLoading(true);
    try {
      const html2canvas = (await import("html2canvas")).default;
      const canvas = await html2canvas(el, {
        useCORS: true,
        scale: window.devicePixelRatio || 1,
        logging: false,
        backgroundColor: "var(--st-bg-primary, #0f0f12)",
      });
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/png", 0.95)
      );
      if (!blob) throw new Error("Falha ao gerar imagem");
      const file = new File([blob], "sportsbank-pro-dashboard.png", { type: "image/png" });
      const url = typeof window !== "undefined" ? window.location.href : "";
      const msg = encodeURIComponent(`Confira o dashboard SportsBank Pro: ${url}`);
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          title: "SportsBank Pro",
          text: `Confira o dashboard: ${url}`,
          files: [file],
        });
      } else {
        const a = document.createElement("a");
        a.href = canvas.toDataURL("image/png");
        a.download = "sportsbank-pro-dashboard.png";
        a.click();
        window.open(`https://wa.me/?text=${msg}`, "_blank", "noopener");
      }
    } catch (err) {
      console.error("Share error:", err);
      const url = typeof window !== "undefined" ? window.location.href : "";
      window.open(`https://wa.me/?text=${encodeURIComponent(`Confira o SportsBank Pro: ${url}`)}`, "_blank", "noopener");
    } finally {
      setShareLoading(false);
    }
  }, []);

  const handleAudit = useCallback(async () => {
    if (!selectedMatch || auditLoading) return;
    setAuditLoading(true);
    try {
      const predictions = selectedMatch.predictions?.map((p: any) => ({
        mercado: p.mercado,
        status: p.status,
        prob_min: p.prob_min,
        prob_max: p.prob_max,
        odd_minima: p.odd_minima,
      }));
      const aiSummary = aiAnalysis
        ? { summary: aiAnalysis.summary, key_points: aiAnalysis.key_points, recommendation: aiAnalysis.recommendation, confidence: aiAnalysis.confidence }
        : undefined;
      const result = await postMatchAudit(selectedMatch.id, predictions, aiSummary);
      setAuditResult(result);
    } catch (err) {
      console.error("Audit error:", err);
    } finally {
      setAuditLoading(false);
    }
  }, [selectedMatch, aiAnalysis, auditLoading]);

  const handleApplyCorrection = useCallback(async (correction: AuditCorrection) => {
    if (!selectedMatch) return;
    try {
      const result = await applyAuditCorrection(selectedMatch.id, {
        correction_type: correction.type,
        parameter_name: correction.parameter,
        old_value: correction.current_value,
        new_value: correction.suggested_value,
        reason: correction.reason,
        audit_confidence: correction.confidence,
      });
      if (result?.status === "success") {
        alert(`Correcao aplicada: ${correction.parameter}`);
      } else {
        alert("Falha ao aplicar correcao.");
      }
    } catch (err) {
      console.error("Apply correction error:", err);
      alert("Erro ao aplicar correcao.");
    }
  }, [selectedMatch]);

  const leagueGroups = useMemo<LeagueGroup[]>(() => {
    const byLeague = new Map<string, Match[]>();
    for (const m of displayMatches) {
      const list = byLeague.get(m.leagueId) ?? [];
      list.push(m);
      byLeague.set(m.leagueId, list);
    }
    return Array.from(byLeague.entries()).map(([leagueId, matches]) => {
      const league = AVAILABLE_LEAGUES.find((l) => l.id === leagueId);
      const sorted = [...matches].sort((a, b) => {
        const da = new Date(a.datetime).getTime();
        const db = new Date(b.datetime).getTime();
        return da - db;
      });
      return {
        leagueId,
        leagueName: league?.name ?? leagueId,
        countryFlag: league?.countryFlag ?? "🏆",
        country: league?.country ?? "",
        matches: sorted,
        collapsed: collapsedLeagues.has(leagueId),
      };
    });
  }, [displayMatches, collapsedLeagues]);

  const leagueIdForCapture = useMemo(() => {
    if (navView !== "matches") return null;
    const selectedLeagueId = selectedMatch?.leagueId;
    if (selectedLeagueId) {
      const selectedGroup = leagueGroups.find(
        (group) => group.leagueId === selectedLeagueId && !group.collapsed,
      );
      if (selectedGroup) return selectedLeagueId;
    }
    return leagueGroups.find((group) => !group.collapsed)?.leagueId ?? null;
  }, [leagueGroups, navView, selectedMatch?.leagueId]);

  const oddsTabs: { key: OddsTab; label: string }[] = [
    { key: "1x2", label: "1X2" },
    { key: "double-chance", label: "Dupla Chance" },
    { key: "btts", label: "BTTS" },
    { key: "goals", label: "Gols" },
    { key: "cards", label: "Cartoes" },
    { key: "corners", label: "Escanteios" },
  ];

  function setShareMessage(message: string, tone: ShareFeedbackTone) {
    setShareFeedback(message);
    setShareFeedbackTone(tone);
  }

  function downloadBlob(blob: Blob, filename: string) {
    const blobUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(blobUrl);
  }

  async function copyBlobToClipboard(blob: Blob): Promise<boolean> {
    if (typeof navigator === "undefined" || !navigator.clipboard || typeof ClipboardItem === "undefined") {
      return false;
    }
    try {
      const item = new ClipboardItem({ [blob.type]: blob });
      await navigator.clipboard.write([item]);
      return true;
    } catch {
      return false;
    }
  }

  async function captureLeftPanelBlob() {
    const panel = capturePanelRef.current;
    if (!panel) {
      throw new Error("Painel de captura nao encontrado.");
    }
    const target = navView === "matches"
      ? panel.querySelector<HTMLElement>("[data-capture-target='true']")
      : panel;
    if (!target) {
      throw new Error("Abra uma liga para capturar a imagem.");
    }
    const previousShareMode = target.getAttribute("data-share-mode");
    target.setAttribute("data-share-mode", "true");
    const controls = Array.from(target.querySelectorAll<HTMLElement>("[data-share-control='true']"));
    const prevVisibility = controls.map((el) => el.style.visibility);
    controls.forEach((el) => {
      el.style.visibility = "hidden";
    });
    try {
      const html2canvas = (await import("html2canvas")).default;
      const canvas = await html2canvas(target, {
        backgroundColor: "#0d0d0d",
        scale: Math.min(window.devicePixelRatio || 1, 2),
        useCORS: true,
        logging: false,
      });
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((result) => {
          if (result) resolve(result);
          else reject(new Error("Falha ao gerar imagem da captura."));
        }, "image/png");
      });
      return blob;
    } finally {
      controls.forEach((el, index) => {
        el.style.visibility = prevVisibility[index] ?? "";
      });
      if (previousShareMode == null) {
        target.removeAttribute("data-share-mode");
      } else {
        target.setAttribute("data-share-mode", previousShareMode);
      }
    }
  }

  async function handleCopyScreen() {
    setShareBusy("copy");
    setShareFeedback("");
    try {
      const blob = await captureLeftPanelBlob();
      const copied = await copyBlobToClipboard(blob);
      if (copied) {
        setShareMessage("Tela copiada. Agora voce pode colar no WhatsApp (Ctrl+V).", "success");
        return;
      }
      const filename = buildScreenshotName();
      downloadBlob(blob, filename);
      setShareMessage("Clipboard indisponivel. Imagem baixada automaticamente.", "info");
    } catch (error: any) {
      setShareMessage(error?.message || "Nao foi possivel capturar a tela agora.", "error");
    } finally {
      setShareBusy(null);
    }
  }

  async function handleShareWhatsApp() {
    setShareBusy("whatsapp");
    setShareFeedback("");
    try {
      const blob = await captureLeftPanelBlob();
      const file = new File([blob], buildScreenshotName(), { type: "image/png" });
      if (
        typeof navigator !== "undefined"
        && "share" in navigator
        && "canShare" in navigator
        && navigator.canShare({ files: [file] })
      ) {
        await navigator.share({
          title: "SportsBank Pro",
          text: SHARE_TEXT,
          files: [file],
        });
        setShareMessage("Compartilhamento concluido pelo menu do seu dispositivo.", "success");
        return;
      }
      const copied = await copyBlobToClipboard(blob);
      const prefilled = copied
        ? `${SHARE_TEXT}\n\nImagem copiada. Abra o chat no WhatsApp e cole (Ctrl+V).`
        : `${SHARE_TEXT}\n\nArquivo da imagem foi baixado para envio manual.`;
      window.open(`https://wa.me/?text=${encodeURIComponent(prefilled)}`, "_blank", "noopener,noreferrer");
      if (!copied) {
        downloadBlob(blob, buildScreenshotName());
      }
      setShareMessage(
        copied
          ? "WhatsApp aberto. Cole a imagem no chat para enviar."
          : "WhatsApp aberto e imagem baixada para anexo manual.",
        "info",
      );
    } catch (error: any) {
      if (error?.name === "AbortError") {
        setShareMessage("Compartilhamento cancelado.", "info");
      } else {
        setShareMessage(error?.message || "Nao foi possivel compartilhar no WhatsApp agora.", "error");
      }
    } finally {
      setShareBusy(null);
    }
  }

  return (
    <div className="st-app">
      {/* TOP NAV */}
      <nav className="st-nav">
        <div className="st-nav__logo">
          sports<span>bank</span>.
        </div>
        <div className="st-nav__links">
          <button className={`st-nav__link ${navView === "campeonatos" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "campeonatos" ? "matches" : "campeonatos")}>
            <Trophy size={14} />
            Campeonatos
          </button>
          <button className={`st-nav__link ${navView === "ferramentas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "ferramentas" ? "matches" : "ferramentas")}>
            <Wrench size={14} />
            Ferramentas
          </button>
          <button className={`st-nav__link ${navView === "recomendadas" ? "st-nav__link--active" : ""}`} onClick={() => setNavView(navView === "recomendadas" ? "matches" : "recomendadas")}>
            <Sparkles size={14} />
            Recomendadas 2026
          </button>
        </div>
        <div className="st-nav__right">
          <span className="st-badge-pro">{APP_VERSION}</span>
          <button
            type="button"
            className="st-nav__link"
            onClick={handleTopbarShareWhatsApp}
            disabled={shareLoading}
            title="Copiar tela e compartilhar via WhatsApp"
            aria-label="Compartilhar via WhatsApp"
          >
            {shareLoading ? <Loader2 size={16} className="animate-spin" /> : <Share2 size={16} />}
            <span className="st-nav__share-label">Compartilhar</span>
          </button>
          <button className="st-nav__search">
            <Search size={14} />
            Buscar
            <kbd>Ctrl+K</kbd>
          </button>
          <button className="st-nav__link" aria-label="Notificacoes">
            <Bell size={16} />
          </button>
        </div>
      </nav>

      <div className="st-main" ref={mainContentRef}>
        {/* LEFT PANEL - Em mobile, esconder quando um jogo está selecionado */}
        {(!isMobile || !selectedMatchId) && (
        <div className="st-panel-left" ref={capturePanelRef}>

          {/* ── CAMPEONATOS VIEW ── */}
          {navView === "campeonatos" && (
            <div className="st-view-panel">
              <div className="st-view-header">
                <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                <h2 className="st-view-title"><Trophy size={16} /> Campeonatos</h2>
              </div>
              <div className="st-view-content">
                {AVAILABLE_LEAGUES.map((league) => {
                  const matchCount = allMatches.filter((m) => m.leagueId === league.id).length;
                  return (
                    <div
                      key={league.id}
                      className="st-league-card"
                      onClick={() => { setSelectedLeague(league.id); setNavView("matches"); }}
                    >
                      <span className="st-league-card__flag">{league.countryFlag}</span>
                      <div className="st-league-card__info">
                        <span className="st-league-card__name">{league.name}</span>
                        <span className="st-league-card__country">{league.country} &middot; {league.season}</span>
                      </div>
                      <div className="st-league-card__right">
                        {matchCount > 0 && (
                          <span className="st-league-card__badge">{matchCount} jogos</span>
                        )}
                        <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── FERRAMENTAS VIEW ── */}
          {navView === "ferramentas" && (
            <div className="st-view-panel">
              <div className="st-view-header">
                <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                <h2 className="st-view-title"><Wrench size={16} /> Ferramentas</h2>
              </div>
              <div className="st-view-content">
                <a href="/ai-audit" className="st-tool-card">
                  <div className="st-tool-card__icon" style={{ background: "rgba(0,255,136,0.1)" }}><Brain size={20} style={{ color: "#00ff88" }} /></div>
                  <div className="st-tool-card__info">
                    <span className="st-tool-card__name">Auditoria AI (Mistral)</span>
                    <span className="st-tool-card__desc">Analise inteligente com recomendacoes de apostas</span>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                </a>
                <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("goals"); }}>
                  <div className="st-tool-card__icon" style={{ background: "rgba(255,187,51,0.1)" }}><BarChart3 size={20} style={{ color: "#ffbb33" }} /></div>
                  <div className="st-tool-card__info">
                    <span className="st-tool-card__name">Comparativo de Gols</span>
                    <span className="st-tool-card__desc">Lambda, xG, Over/Under e medias por liga</span>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                </div>
                <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("btts"); }}>
                  <div className="st-tool-card__icon" style={{ background: "rgba(157,80,255,0.1)" }}><Target size={20} style={{ color: "#9d50ff" }} /></div>
                  <div className="st-tool-card__info">
                    <span className="st-tool-card__name">Analise BTTS</span>
                    <span className="st-tool-card__desc">Both Teams To Score — probabilidades e odds</span>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                </div>
                <div className="st-tool-card" onClick={() => { setNavView("matches"); setOddsTab("corners"); }}>
                  <div className="st-tool-card__icon" style={{ background: "rgba(0,187,255,0.1)" }}><Zap size={20} style={{ color: "#00bbff" }} /></div>
                  <div className="st-tool-card__info">
                    <span className="st-tool-card__name">Escanteios & Cartoes</span>
                    <span className="st-tool-card__desc">Medias de escanteios e cartoes por equipe</span>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                </div>
                <div className="st-tool-card" onClick={() => setNavView("recomendadas")}>
                  <div className="st-tool-card__icon" style={{ background: "rgba(255,68,68,0.1)" }}><Sparkles size={20} style={{ color: "#ff4444" }} /></div>
                  <div className="st-tool-card__info">
                    <span className="st-tool-card__name">Recomendadas do Dia</span>
                    <span className="st-tool-card__desc">Jogos com maior confianca da analise AI</span>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--st-text-muted)" }} />
                </div>
              </div>
            </div>
          )}

          {/* ── RECOMENDADAS VIEW ── */}
          {navView === "recomendadas" && (
            <div className="st-view-panel">
              <div className="st-view-header">
                <button className="st-view-back" onClick={() => setNavView("matches")}><ArrowLeft size={14} /> Voltar</button>
                <h2 className="st-view-title"><Sparkles size={16} /> Recomendadas 2026</h2>
              </div>
              <div className="st-view-subtitle">Jogos com melhor potencial baseado em probabilidades, Lambda e analise estatistica</div>
              <div className="st-view-content">
                {allMatches.length === 0 && (
                  <div className="st-empty">
                    <div className="st-empty__icon">&#9917;</div>
                    Carregando jogos para analise...
                  </div>
                )}
                {allMatches
                  .filter((m) => m.status === "scheduled")
                  .sort((a, b) => {
                    // Score: higher homeWinProb or awayWinProb + high over25 + btts data
                    const scoreA = Math.max(a.stats?.homeWinProb ?? 0, a.stats?.awayWinProb ?? 0) + (a.stats?.over25Prob ?? 0) * 0.5;
                    const scoreB = Math.max(b.stats?.homeWinProb ?? 0, b.stats?.awayWinProb ?? 0) + (b.stats?.over25Prob ?? 0) * 0.5;
                    return scoreB - scoreA;
                  })
                  .slice(0, 15)
                  .map((match) => {
                    const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
                    const maxProb = Math.max(match.stats?.homeWinProb ?? 0, match.stats?.awayWinProb ?? 0);
                    const maxProbPct = toPercent(maxProb);
                    const probLabel = maxProb === (match.stats?.homeWinProb ?? 0) ? `${match.homeTeam.name} (${formatProb(maxProb)})` : `${match.awayTeam.name} (${formatProb(maxProb)})`;
                    const confidenceColor = maxProbPct >= 55 ? "#00ff88" : maxProbPct >= 40 ? "#ffbb33" : "#ff4444";
                    return (
                      <div
                        key={match.id}
                        className="st-rec-card"
                        onClick={() => { setSelectedMatchId(match.id); setNavView("matches"); }}
                      >
                        <div className="st-rec-card__header">
                          <span className="st-rec-card__league">{league?.countryFlag} {league?.name ?? match.leagueId}</span>
                          <span className="st-rec-card__time">{formatTime(match.datetime)}</span>
                        </div>
                        <div className="st-rec-card__teams">
                          <span className="st-rec-card__team">{match.homeTeam.name}</span>
                          <span className="st-rec-card__vs">vs</span>
                          <span className="st-rec-card__team">{match.awayTeam.name}</span>
                        </div>
                        <div className="st-rec-card__stats">
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">Favorito</span>
                            <span className="st-rec-card__stat-value" style={{ color: confidenceColor }}>{probLabel}</span>
                          </div>
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">Over 2.5</span>
                            <span className="st-rec-card__stat-value">{formatProb(match.stats?.over25Prob)}</span>
                          </div>
                          <div className="st-rec-card__stat">
                            <span className="st-rec-card__stat-label">BTTS</span>
                            <span className="st-rec-card__stat-value">{formatProb(match.stats?.bttsProb)}</span>
                          </div>
                        </div>
                        {match.odds?.home > 0 && (
                          <div className="st-rec-card__odds">
                            <span className="st-rec-card__odd">1: {match.odds.home.toFixed(2)}</span>
                            <span className="st-rec-card__odd">X: {match.odds.draw.toFixed(2)}</span>
                            <span className="st-rec-card__odd">2: {match.odds.away.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* ── MATCHES VIEW (default) ── */}
          {navView === "matches" && <>
          {/* Filter bar */}
          <div className="st-filters">
            <div className="st-date-nav">
              <button type="button" className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "week" ? "tomorrow" : prev === "tomorrow" ? "today" : "today")}><ChevronLeft size={14} /></button>
              <span className="st-date-label">{dateLabel}</span>
              <button type="button" className="st-date-nav__btn" onClick={() => setDateMode((prev) => prev === "today" ? "tomorrow" : prev === "tomorrow" ? "week" : "week")}><ChevronRight size={14} /></button>
            </div>
            <div className="st-live-dot" />
            <button
              type="button"
              className={`st-filter-btn ${shareBusy === "copy" ? "st-filter-btn--active" : ""}`}
              onClick={handleCopyScreen}
              data-share-control="true"
              disabled={shareBusy !== null}
            >
              {shareBusy === "copy" ? <Loader2 size={12} className="st-spin-icon" /> : <Copy size={12} />}
              Copiar tela
            </button>
            <button
              type="button"
              className={`st-filter-btn ${shareBusy === "whatsapp" ? "st-filter-btn--active" : ""}`}
              onClick={handleShareWhatsApp}
              data-share-control="true"
              disabled={shareBusy !== null}
            >
              {shareBusy === "whatsapp" ? <Loader2 size={12} className="st-spin-icon" /> : <MessageCircle size={12} />}
              WhatsApp
            </button>
            <button type="button" className="st-filter-btn st-filter-btn--mobile-hidden" title="Ordenar por data/hora"><SlidersHorizontal size={12} /> Ordenar</button>
            <button
              type="button"
              className={`st-filter-btn st-filter-btn--mobile-hidden ${showFavoritesOnly ? "st-filter-btn--active" : ""}`}
              onClick={() => setShowFavoritesOnly((v) => !v)}
            >
              <Heart size={12} fill={showFavoritesOnly ? "currentColor" : "none"} /> Favoritos
            </button>
            <button type="button" className="st-filter-btn st-filter-btn--mobile-hidden" title="Filtros em breve"><Filter size={12} /> Filtros</button>
          </div>
          {shareFeedback && (
            <div
              className={`st-share-feedback st-share-feedback--${shareFeedbackTone}`}
              role="status"
              data-share-control="true"
            >
              {shareFeedback}
            </div>
          )}

          {/* Odds tabs */}
          <div className="st-odds-tabs">
            <span style={{ fontSize: "0.7rem", color: "var(--st-text-muted)", padding: "10px 8px 10px 0", whiteSpace: "nowrap" }}>COTACOES</span>
            {oddsTabs.map((t) => (
              <button
                key={t.key}
                className={`st-odds-tab ${oddsTab === t.key ? "st-odds-tab--active" : ""}`}
                onClick={() => setOddsTab(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {selectedLeague && (
            <div style={{ padding: "8px 12px" }}>
              <button
                onClick={() => setSelectedLeague(null)}
                style={{
                  background: "rgba(255,165,0,0.15)",
                  border: "1px solid rgba(255,165,0,0.3)",
                  borderRadius: 6,
                  padding: "4px 12px",
                  color: "#ffaa33",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                ✕ {AVAILABLE_LEAGUES.find((l) => l.id === selectedLeague)?.name ?? selectedLeague} — Ver todas as ligas
              </button>
            </div>
          )}

          {!loading && leagueGroups.length === 0 && (
            <div className="st-empty">
              <div className="st-empty__icon">&#9917;</div>
              {dateMode === "week"
                ? "Nenhum jogo encontrado para esta semana. Tente novamente mais tarde."
                : "Nenhum jogo disponivel. Use as setas para navegar entre datas."}
            </div>
          )}

          {!loading && leagueGroups.map((group) => {
            const isCaptureTarget = group.leagueId === leagueIdForCapture;
            return (
              <div
                key={group.leagueId}
                className="st-league-group"
                data-capture-target={isCaptureTarget ? "true" : "false"}
              >
                <div className="st-league-header" onClick={() => toggleLeague(group.leagueId)}>
                <span className="st-league-flag">{group.countryFlag}</span>
                <span className="st-league-name">
                  {group.leagueName}
                  <span className="st-league-count"> ({group.matches.length})</span>
                </span>
                <div className="st-league-actions" data-share-hide="true">
                  <button className="st-league-action-btn" onClick={(e) => { e.stopPropagation(); }}>
                    <Star size={14} />
                  </button>
                  <button className="st-league-action-btn" onClick={(e) => { e.stopPropagation(); }}>
                    <SlidersHorizontal size={14} />
                  </button>
                  {group.collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                </div>
              </div>

                {!group.collapsed && group.matches.map((match) => {
                const si = statusInfo(match.status);
                const h = safeOdd(match.odds?.home);
                const d = safeOdd(match.odds?.draw);
                const a = safeOdd(match.odds?.away);
                const lowestIdx = getLowestOddIndex(h, d, a);
                const isSelected = match.id === selectedMatchId;

                return (
                  <div
                    key={match.id}
                    className={`st-match-row ${isSelected ? "st-match-row--selected" : ""}`}
                    onClick={() => setSelectedMatchId(match.id)}
                  >
                    <div className="st-match-row__status">
                      <div className="st-match-row__status-date">{formatDate(match.datetime)}</div>
                      <div className={`st-match-row__status-label ${si.cssClass}`}>
                        {si.label || formatTime(match.datetime)}
                      </div>
                      {si.label && (
                        <div className="st-match-row__status-time">{formatTime(match.datetime)}</div>
                      )}
                    </div>
                    <div className="st-match-row__teams">
                      <div className="st-match-row__team">
                        {match.homeTeam.logo ? (
                          <img src={match.homeTeam.logo} alt="" className="st-match-row__team-logo" />
                        ) : (
                          <div className="st-match-row__team-logo st-match-row__team-logo--placeholder">H</div>
                        )}
                        <span className="st-match-row__team-name">{match.homeTeam.name}</span>
                      </div>
                      <div className="st-match-row__team">
                        {match.awayTeam.logo ? (
                          <img src={match.awayTeam.logo} alt="" className="st-match-row__team-logo" />
                        ) : (
                          <div className="st-match-row__team-logo st-match-row__team-logo--placeholder">A</div>
                        )}
                        <span className="st-match-row__team-name">{match.awayTeam.name}</span>
                      </div>
                    </div>
                    {match.score && (
                      <div className="st-match-row__score">
                        {match.score.home ?? 0} - {match.score.away ?? 0}
                      </div>
                    )}
                    {oddsTab === "1x2" && (
                      <div className="st-match-row__odds">
                        <div className={`st-match-row__odd ${lowestIdx === 0 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">1</span>
                          <span className="st-match-row__odd-value">{h.toFixed(2)}</span>
                        </div>
                        <div className={`st-match-row__odd ${lowestIdx === 1 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">X</span>
                          <span className="st-match-row__odd-value">{d.toFixed(2)}</span>
                        </div>
                        <div className={`st-match-row__odd ${lowestIdx === 2 ? "st-match-row__odd--highlight" : ""}`}>
                          <span className="st-match-row__odd-label">2</span>
                          <span className="st-match-row__odd-value">{a.toFixed(2)}</span>
                        </div>
                      </div>
                    )}
                    {oddsTab === "double-chance" && (() => {
                      const dc1x = h > 0 && d > 0 ? parseFloat((1 / (1/h + 1/d)).toFixed(2)) : 0;
                      const dc12 = h > 0 && a > 0 ? parseFloat((1 / (1/h + 1/a)).toFixed(2)) : 0;
                      const dcx2 = d > 0 && a > 0 ? parseFloat((1 / (1/d + 1/a)).toFixed(2)) : 0;
                      return (
                        <div className="st-match-row__odds">
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">1X</span>
                            <span className="st-match-row__odd-value">{dc1x > 0 ? dc1x.toFixed(2) : "-"}</span>
                          </div>
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">12</span>
                            <span className="st-match-row__odd-value">{dc12 > 0 ? dc12.toFixed(2) : "-"}</span>
                          </div>
                          <div className="st-match-row__odd">
                            <span className="st-match-row__odd-label">X2</span>
                            <span className="st-match-row__odd-value">{dcx2 > 0 ? dcx2.toFixed(2) : "-"}</span>
                          </div>
                        </div>
                      );
                    })()}
                    {oddsTab === "btts" && (
                      <div className="st-match-row__odds">
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Sim</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.bttsYes) > 0 ? safeOdd(match.odds?.bttsYes).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Nao</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.bttsNo) > 0 ? safeOdd(match.odds?.bttsNo).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                          <span className="st-match-row__odd-label">Prob%</span>
                          <span className="st-match-row__odd-value">{match.stats?.bttsProb > 0 ? `${match.stats.bttsProb.toFixed(0)}%` : "-"}</span>
                        </div>
                      </div>
                    )}
                    {oddsTab === "goals" && (
                      <div className="st-match-row__odds">
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">O 1.5</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.over15) > 0 ? safeOdd(match.odds?.over15).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd st-match-row__odd--highlight">
                          <span className="st-match-row__odd-label">O 2.5</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.over25) > 0 ? safeOdd(match.odds?.over25).toFixed(2) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">O 3.5</span>
                          <span className="st-match-row__odd-value">{safeOdd(match.odds?.over35) > 0 ? safeOdd(match.odds?.over35).toFixed(2) : "-"}</span>
                        </div>
                      </div>
                    )}
                    {oddsTab === "cards" && (
                      <div className="st-match-row__odds">
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Casa</span>
                          <span className="st-match-row__odd-value">{match.stats?.homeCardsPerMatch ? match.stats.homeCardsPerMatch.toFixed(1) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Fora</span>
                          <span className="st-match-row__odd-value">{match.stats?.awayCardsPerMatch ? match.stats.awayCardsPerMatch.toFixed(1) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                          <span className="st-match-row__odd-label">Liga</span>
                          <span className="st-match-row__odd-value">{match.stats?.leagueAvgCards ? match.stats.leagueAvgCards.toFixed(1) : "-"}</span>
                        </div>
                      </div>
                    )}
                    {oddsTab === "corners" && (
                      <div className="st-match-row__odds">
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Casa</span>
                          <span className="st-match-row__odd-value">{match.stats?.homeCornersPerMatch ? match.stats.homeCornersPerMatch.toFixed(1) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd">
                          <span className="st-match-row__odd-label">Fora</span>
                          <span className="st-match-row__odd-value">{match.stats?.awayCornersPerMatch ? match.stats.awayCornersPerMatch.toFixed(1) : "-"}</span>
                        </div>
                        <div className="st-match-row__odd" style={{ opacity: 0.7 }}>
                          <span className="st-match-row__odd-label">Liga</span>
                          <span className="st-match-row__odd-value">{match.stats?.leagueAvgCorners ? match.stats.leagueAvgCorners.toFixed(1) : "-"}</span>
                        </div>
                      </div>
                    )}
                    <button
                      type="button"
                      className="st-match-row__favorite"
                      data-share-hide="true"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleFavorite(match.id); }}
                      aria-label={favoriteIds.has(match.id) ? "Remover dos favoritos" : "Adicionar aos favoritos"}
                    >
                      <Star size={14} fill={favoriteIds.has(match.id) ? "currentColor" : "none"} />
                    </button>
                    {match.predictions && match.predictions.length > 0 && (
                      <div className="st-match-row__predictions">
                        {match.predictions.map((pred, pidx) => (
                          <div key={pidx} className="st-prediction-badge">
                            <span className={`st-prediction-status st-prediction-status--${pred.status.toLowerCase().replace("*", "-star")}`}>
                              {pred.status}
                            </span>
                            <span className="st-prediction-market">{pred.mercado}</span>
                            <span className="st-prediction-prob">{pred.prob_min}-{pred.prob_max}%</span>
                            <span className="st-prediction-odd">EV+ &gt;= {pred.odd_minima != null ? pred.odd_minima.toFixed(2) : "-"}</span>
                            {pred.alerta && <span className="st-prediction-alert">△ {pred.alerta}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
                })}
              </div>
            );
          })}
          </>}
        </div>
        )}

        {/* RIGHT PANEL - Em mobile, esconder quando nenhum jogo está selecionado */}
        {(!isMobile || selectedMatchId) && (
        <section className="st-panel-right detail-card-section">
          {detailData ? (
            <MatchDetailCard
              match={detailData}
              version={APP_VERSION}
              onAudit={handleAudit}
              onApplyCorrection={handleApplyCorrection}
              auditResult={auditResult}
              auditLoading={auditLoading}
              onBack={() => setSelectedMatchId(null)}
              showBackButton={isMobile}
            />
          ) : (
            <div className="muted">Selecione um jogo para visualizar os detalhes.</div>
          )}
        </section>
        )}
      </div>
    </div>
  );
}
