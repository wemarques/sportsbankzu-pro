import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { Hero } from "@/components/marca/Hero";
import { HERO } from "@/lib/copy";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const AGREGADO_OK = {
  ok: true, periodo: "30d", familia: null, liga: null,
  acerto: { picks: 40, acertos: 26, jogos: 22, resolvidos: 40 },
  retorno: { valor: null, pct_banca: null, motivo: null },
  brier: null, amostra_curta: false, por_familia: {}, por_liga: {}, buckets: null,
};
const AGREGADO_CURTO = { ...AGREGADO_OK, acerto: { picks: 8, acertos: 5, jogos: 5, resolvidos: 8 } };
const FEED_VAZIO = { matches: [] };
const FEED_COM_VALE = {
  matches: [{
    id: "championship-Middlesbrough-Millwall-1798920000",
    leagueId: "championship", leagueName: "Championship",
    homeTeam: { name: "Middlesbrough", logo: "", form: [], rating: 0 },
    awayTeam: { name: "Millwall", logo: "", form: [], rating: 0 },
    datetime: "2026-09-17T20:00:00Z", status: "scheduled",
    mercados: [{
      mercado: "Over 2.5 Gols", classification: "SAFE", reason_codes: [],
      ev: 0.12, edge: 0.08, fair_odd: 1.55, book_odd: 1.75, calibrated_probability: 0.62,
    }],
    source: "footystats", lastUpdated: "2026-09-17T09:00:00Z",
  }],
};
const FEED_DOIS_VALEM = {
  matches: [{
    id: "championship-Middlesbrough-Millwall-1798920000",
    leagueId: "championship", leagueName: "Championship",
    homeTeam: { name: "Middlesbrough", logo: "", form: [], rating: 0 },
    awayTeam: { name: "Millwall", logo: "", form: [], rating: 0 },
    datetime: "2026-09-17T20:00:00Z", status: "scheduled",
    mercados: [{
      mercado: "Over 2.5 Gols", classification: "SAFE", reason_codes: [],
      ev: 0.10, edge: 0.05, fair_odd: 1.67, book_odd: 1.9, calibrated_probability: 0.6,
    }],
    source: "footystats", lastUpdated: "2026-09-17T09:00:00Z",
  }, {
    id: "premier-league-Fulham-Brentford-1798930000",
    leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Fulham", logo: "", form: [], rating: 0 },
    awayTeam: { name: "Brentford", logo: "", form: [], rating: 0 },
    datetime: "2026-09-17T19:00:00Z", status: "scheduled",
    mercados: [{
      mercado: "BTTS - Sim", classification: "SAFE", reason_codes: [],
      ev: 0.15, edge: 0.12, fair_odd: 1.72, book_odd: 1.8, calibrated_probability: 0.58,
    }],
    source: "footystats", lastUpdated: "2026-09-17T09:00:00Z",
  }],
};
const LEDGER_DIA_VAZIO = { ok: true, data: "2026-09-16", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 }, semana: {}, mes: {} };
const LEDGER_DIA_COM_PICK = {
  ok: true, data: "2026-09-16",
  picks: [{
    match_id: "championship-Middlesbrough-Millwall-1798840000", league_id: "championship",
    kickoff_utc: "2026-09-16T20:00:00Z", familia: "Over/Under", market: "Over/Under",
    selection: "Over 2.5 Gols", published_prob: 0.62, fair_odd: 1.61, book_odd: 1.75,
    classification: "SAFE", outcome: 1, detail: "2–1, 3 gols",
  }],
  resumo: { picks: 1, acertos: 1, jogos: 1, resolvidos: 1 }, semana: {}, mes: {},
};

// #258: `delayMs` adia a resolucao ate um PRAZO ABSOLUTO (inicio da stub +
// delayMs), nao um atraso relativo a cada chamada — o feed de hoje faz
// fan-out de 1 requisicao por liga (`LEAGUES_PER_BATCH=1`, `MAX_CONCURRENT=4`
// em `lib/api.ts`), entao um atraso relativo por chamada somaria a cada
// rodada do semaforo (~22 ligas / 4 = 6 rodadas) em vez de expirar uma vez.
// `erro` rejeita a promise em vez de resolver.
function stubFetchSequence(respostas: Array<{ url: RegExp; body?: unknown; delayMs?: number; erro?: boolean }>): string[] {
  const chamadas: string[] = [];
  const inicio = Date.now();
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    chamadas.push(url);
    const achou = respostas.find((r) => r.url.test(url));
    return new Promise((resolve, reject) => {
      const liquidar = () => {
        if (achou?.erro) reject(new Error("falha simulada"));
        else resolve({ status: 200, json: () => Promise.resolve(achou?.body ?? {}) });
      };
      const restante = achou?.delayMs ? Math.max(0, inicio + achou.delayMs - Date.now()) : 0;
      if (restante > 0) setTimeout(liquidar, restante);
      else liquidar();
    });
  }));
  return chamadas;
}

describe("Hero (#257, spec §5)", () => {
  it("sem talao hoje: cai para o de ONTEM no ledger, com a faixa de resultado (aparece ~1s)", async () => {
    vi.useFakeTimers();
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_VAZIO, delayMs: 100 },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK, delayMs: 100 },
    ]);
    render(<Hero />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText(/✓ fechou com/)).toBeInTheDocument();
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();
  });

  // #258 (M3): o card do hero e prova, nao decisao — nunca mostra a linha de
  // confianca da liga, mesmo com talao presente.
  it("card do hero nunca mostra linha de confianca", async () => {
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_COM_VALE },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument());
    expect(screen.queryByText(/confiança/i)).toBeNull();
    expect(screen.queryByText(/não verificada/i)).toBeNull();
  });

  // #258: contrato mudou — o ledger de ontem agora dispara SEMPRE, em
  // paralelo com o feed de hoje (nao mais so quando hoje falha/esvazia).
  // Hoje ainda vence quando tem talao; o nome reflete o que o teste prova.
  it("talao de hoje existe: usa o de hoje (ledger de ontem tambem dispara, em paralelo)", async () => {
    const chamadas = stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_COM_VALE },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument());
    expect(screen.queryByText(/✓ fechou com/)).toBeNull();
    expect(chamadas.some((u) => /ledger\/dia/.test(u))).toBe(true);
  });

  it("dois jogos valem hoje: usa o de MAIOR edge (ledger de ontem tambem dispara, em paralelo) (spec §5)", async () => {
    const chamadas = stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_DOIS_VALEM },
      { url: /ledger\/dia/, body: LEDGER_DIA_VAZIO },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByRole("link", { name: "Fulham × Brentford" })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Middlesbrough × Millwall" })).toBeNull();
    expect(chamadas.some((u) => /ledger\/dia/.test(u))).toBe(true);
  });

  // #258 (a): hoje demora (5s) mas tem talao; ontem responde rapido (0,3s).
  // Ontem aparece como ponte em ~1s; quando hoje finalmente resolve, sobrescreve.
  it("(a) hoje lento com talao, ontem rapido: ontem em ~1s, hoje sobrescreve depois", async () => {
    vi.useFakeTimers();
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_COM_VALE, delayMs: 5000 },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK, delayMs: 300 },
    ]);
    render(<Hero />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText(/✓ fechou com/)).toBeInTheDocument();
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();

    await act(async () => { await vi.advanceTimersByTimeAsync(4000); }); // total 5000ms
    expect(screen.queryByText(/✓ fechou com/)).toBeNull(); // hoje sobrescreveu a faixa de ontem
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();
  });

  // #258 (b): hoje responde rapido (0,5s) com talao; ontem so resolve depois do
  // marco de 1s (1,5s) — nunca deve aparecer, mesmo tendo talao.
  it("(b) hoje rapido com talao: hoje aparece, ontem nunca aparece mesmo resolvendo depois", async () => {
    vi.useFakeTimers();
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_COM_VALE, delayMs: 500 },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK, delayMs: 1500 },
    ]);
    render(<Hero />);
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();
    expect(screen.queryByText(/✓ fechou com/)).toBeNull();

    await act(async () => { await vi.advanceTimersByTimeAsync(2000); }); // passa 1s, 2s e a resolucao tardia de ontem
    expect(screen.queryByText(/✓ fechou com/)).toBeNull();
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();
  });

  // #258 (c): hoje e ontem resolvem cedo mas vazios — nada para mostrar ate o
  // marco de 2s, quando entra a frase de ausencia.
  it("(c) hoje vazio, ontem vazio: frase de ausencia em ~2s", async () => {
    vi.useFakeTimers();
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_VAZIO, delayMs: 500 },
      { url: /ledger\/dia/, body: LEDGER_DIA_VAZIO, delayMs: 300 },
    ]);
    render(<Hero />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.queryByText(HERO.semTalao)).toBeNull();

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); }); // total 2000ms
    expect(screen.getByText(HERO.semTalao)).toBeInTheDocument();
  });

  // #258 (d): hoje falha; ontem tem talao — ontem aparece em ~1s e fica (uma
  // falha tardia/posterior de hoje nunca some com o que ja apareceu).
  it("(d) hoje falha, ontem tem talao: ontem aparece e permanece", async () => {
    vi.useFakeTimers();
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, erro: true },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK, delayMs: 300 },
    ]);
    render(<Hero />);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText(/✓ fechou com/)).toBeInTheDocument();

    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByText(/✓ fechou com/)).toBeInTheDocument();
  });

  it("amostra curta (jogos=5): a frase de acerto some, CTA duplo continua", async () => {
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_CURTO },
      { url: /matches\/fetch/, body: FEED_VAZIO },
      { url: /ledger\/dia/, body: LEDGER_DIA_VAZIO },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByRole("link", { name: "Ver os jogos de hoje" })).toBeInTheDocument());
    expect(screen.queryByText(/de cada 100 picks fechados/)).toBeNull();
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Criar conta" })).toHaveAttribute("href", "/register");
  });
});
