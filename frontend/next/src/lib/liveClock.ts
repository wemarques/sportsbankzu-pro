/**
 * Relógio ao vivo — fonte única de verdade para período/minuto de um jogo.
 *
 * Regra de ouro: o feed manda. O horário de kickoff só é usado quando NÃO
 * existe nenhum dado de minuto vindo do backend. Antes desta versão o
 * dashboard fazia `Math.max(minutoDoFeed, estimativaPeloRelogio)`, o que
 * empurrava o placar de tempo para frente sempre que havia atraso de bola
 * rolando, intervalo longo ou acréscimos — o card chegou a mostrar 59'
 * enquanto o api_football reportava 49'.
 *
 * Entre dois polls (20s) o minuto é interpolado a partir da última amostra
 * recebida (âncora `minuteUpdatedAt`), com teto de MAX_DRIFT_MIN para que um
 * feed travado nunca invente tempo — passado esse teto o relógio congela e é
 * marcado como `stale`.
 */

export type LivePeriod = "1T" | "HT" | "2T";

/** Minutos regulamentares de cada tempo. */
const HALF = 45;
const FULL = 90;
/** Duração nominal do intervalo. */
const BREAK = 15;
/** Teto de acréscimos aceito para exibição (45+X / 90+X). */
const MAX_STOPPAGE_1T = 8;
const MAX_STOPPAGE_2T = 12;
/** Quantos minutos interpolamos além da última amostra do feed. */
const MAX_DRIFT_MIN = 3;
/**
 * Acréscimo assumido no 1T quando NÃO há feed. Menor que MAX_STOPPAGE_1T de
 * propósito: sem dado real, aos 52' de relógio o cenário mais provável é
 * intervalo, não sete minutos de acréscimo.
 */
const EST_STOPPAGE_1T = 3;

export interface LiveClockSource {
  status: "scheduled" | "live" | "finished" | "postponed";
  datetime: string;
  period?: LivePeriod | string | null;
  minute?: number | null;
  /** epoch ms de quando `minute` chegou do feed (carimbado no merge do overlay) */
  minuteUpdatedAt?: number | null;
  /**
   * true quando o backend derivou o minuto do horário de início em vez de ler
   * um cronômetro (o todays-matches do FootyStats não tem tempo de jogo).
   * Esse valor ainda é usado, mas nunca se apresenta como tempo real.
   */
  minuteIsEstimated?: boolean;
}

export interface LiveClock {
  period: LivePeriod;
  /** Minuto regulamentar (≤45 no 1T, ≤90 no 2T). null no intervalo. */
  minute: number | null;
  /** Minutos de acréscimo além do fim do tempo (0 quando não há). */
  stoppage: number;
  /** Texto pronto: "58'", "45+2'", "INT". Prefixo "~" quando o feed travou. */
  label: string;
  /** Minutos regulamentares que ainda faltam para o fim do jogo. */
  minutesLeft: number;
  /** true quando o valor veio do feed; false quando é estimativa pelo horário. */
  fromFeed: boolean;
  /** true quando o feed está parado há mais de MAX_DRIFT_MIN. */
  stale: boolean;
}

/** Aceita as variações de período que os provedores mandam. */
export function normalizePeriod(raw?: string | null): LivePeriod | null {
  if (!raw) return null;
  const p = String(raw).trim().toUpperCase();
  if (p === "HT" || p === "INT" || p === "HALFTIME" || p === "HALF_TIME") return "HT";
  if (p === "1T" || p === "1H" || p === "FIRST_HALF" || p === "1ST") return "1T";
  if (p === "2T" || p === "2H" || p === "SECOND_HALF" || p === "2ND") return "2T";
  // Prorrogação e pênaltis: tratamos como 2T para fins de exibição de tempo.
  if (p === "ET" || p === "AET" || p === "P" || p === "PEN") return "2T";
  return null;
}

function build(
  period: LivePeriod,
  rawMinute: number,
  fromFeed: boolean,
  stale: boolean,
): LiveClock {
  const end = period === "1T" ? HALF : FULL;
  const maxStoppage = period === "1T" ? MAX_STOPPAGE_1T : MAX_STOPPAGE_2T;
  const floor = period === "2T" ? HALF + 1 : 0;
  const capped = Math.min(Math.max(Math.round(rawMinute), floor), end + maxStoppage);
  const stoppage = Math.max(0, capped - end);
  const minute = Math.min(capped, end);
  const shown = stoppage > 0 ? `${end}+${stoppage}'` : `${minute}'`;
  const minutesLeft =
    period === "1T" ? HALF - minute + HALF : Math.max(0, FULL - minute);
  return {
    period,
    minute,
    stoppage,
    label: stale ? `~${shown}` : shown,
    minutesLeft,
    fromFeed,
    stale,
  };
}

function halftime(fromFeed: boolean): LiveClock {
  return {
    period: "HT",
    minute: null,
    stoppage: 0,
    label: "INT",
    minutesLeft: HALF,
    fromFeed,
    stale: false,
  };
}

/**
 * Calcula período/minuto para exibição. Retorna null quando o jogo não está
 * ao vivo (ou quando o kickoff ainda não chegou).
 */
export function getLiveClock(
  m: LiveClockSource,
  nowMs: number = Date.now(),
): LiveClock | null {
  if (m.status !== "live") return null;

  const feedPeriod = normalizePeriod(m.period);
  const feedMinute =
    typeof m.minute === "number" && Number.isFinite(m.minute) && m.minute >= 0
      ? m.minute
      : null;

  // 1) Intervalo declarado pelo feed tem prioridade absoluta: nunca exibir minuto.
  if (feedPeriod === "HT") return halftime(true);

  // 2) Caminho normal: feed com período e minuto. Interpola a partir da âncora.
  if (feedPeriod && feedMinute != null) {
    const anchor =
      typeof m.minuteUpdatedAt === "number" && m.minuteUpdatedAt > 0
        ? m.minuteUpdatedAt
        : nowMs;
    const driftMin = Math.max(0, Math.floor((nowMs - anchor) / 60_000));
    const stale = driftMin > MAX_DRIFT_MIN;
    const measured = m.minuteIsEstimated !== true;
    return build(
      feedPeriod,
      feedMinute + Math.min(driftMin, MAX_DRIFT_MIN),
      measured,
      stale,
    );
  }

  // 3) Último recurso: sem minuto do feed, estima pelo horário do kickoff.
  const kickoff = new Date(m.datetime).getTime();
  if (!Number.isFinite(kickoff)) {
    return feedPeriod ? build(feedPeriod, feedMinute ?? 0, true, false) : null;
  }
  const elapsed = Math.floor((nowMs - kickoff) / 60_000);
  if (elapsed < 0) return null;

  if (elapsed <= HALF + EST_STOPPAGE_1T) {
    return build(feedPeriod ?? "1T", elapsed, false, false);
  }
  if (elapsed <= HALF + BREAK) {
    // Janela típica de intervalo. Se o feed insiste num tempo, respeitamos ele.
    if (feedPeriod) return build(feedPeriod, feedMinute ?? HALF, false, false);
    return halftime(false);
  }
  return build(feedPeriod ?? "2T", elapsed - BREAK, false, false);
}

/** Atalho para os componentes que só precisam do texto. */
export function formatLiveClock(clock: LiveClock | null): string {
  if (!clock) return "";
  return clock.period === "HT" ? "INT" : `${clock.period} ${clock.label}`;
}
