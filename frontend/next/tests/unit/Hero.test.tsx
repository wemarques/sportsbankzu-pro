import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Hero } from "@/components/marca/Hero";

afterEach(() => vi.unstubAllGlobals());

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

function stubFetchSequence(respostas: Array<{ url: RegExp; body: unknown }>): string[] {
  const chamadas: string[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    chamadas.push(url);
    const achou = respostas.find((r) => r.url.test(url));
    return Promise.resolve({ status: 200, json: () => Promise.resolve(achou?.body ?? {}) });
  }));
  return chamadas;
}

describe("Hero (#257, spec §5)", () => {
  it("sem talao hoje: cai para o de ONTEM no ledger, com a faixa de resultado", async () => {
    stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_VAZIO },
      { url: /ledger\/dia/, body: LEDGER_DIA_COM_PICK },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByText(/✓ fechou com/)).toBeInTheDocument());
    expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument();
  });

  it("talao de hoje existe: usa o de hoje, NAO chama /ledger/dia", async () => {
    const chamadas = stubFetchSequence([
      { url: /ledger\/agregado/, body: AGREGADO_OK },
      { url: /matches\/fetch/, body: FEED_COM_VALE },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByText("Middlesbrough × Millwall")).toBeInTheDocument());
    expect(screen.queryByText(/✓ fechou com/)).toBeNull();
    expect(chamadas.some((u) => /ledger\/dia/.test(u))).toBe(false);
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
