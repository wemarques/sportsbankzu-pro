import { describe, expect, it } from "vitest";
import { mesmoJogo } from "@/lib/ledgerCasamento";
import { toJogoView } from "@/lib/jogoView";
import { normalizeMatch } from "@/lib/normalizeMatch";
import type { LedgerPick } from "@/lib/ledgerApi";
import feedCuiabaNautico from "./fixtures/producao-2026-09-21-cuiaba-nautico-feed.json";
import ledgerCuiabaNautico from "./fixtures/producao-2026-09-21-cuiaba-nautico-ledger.json";

/**
 * #261 — Etapa 2 do SDD (contrato de id): `mesmoJogo` casa `JogoView`
 * (produtor `/fixtures`) com `LedgerPick` (produtor `/ledger/dia`) por
 * liga + kickoff + times, NUNCA por igualdade crua de id — os dois
 * produtores grafam o id de forma diferente (spec, emenda #261 §4.2).
 */

function pick(over: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "mls-Toronto-Nashville SC-1788985800.0", league_id: "mls",
    kickoff_utc: "2026-09-14T23:30:00+00:00", familia: "Corners", market: "Corners",
    selection: "Corners Over 6.5", published_prob: 0.585, fair_odd: 1.67, book_odd: 1.75,
    classification: "SAFE", outcome: null, detail: null, ...over,
  };
}

describe("mesmoJogo — par real Cuiabá × Náutico (produção, 2026-09-21, ver tests/unit/fixtures/README.md)", () => {
  // Produtor real: /fixtures devolve `leagueId: "brasileirao-serie-b"` (slug do
  // backend); normalizeMatch recebe esse valor como 2º argumento, exatamente
  // como Feed.tsx faz (`normalizeMatch(m, m.leagueId ?? "", i)`).
  const match = normalizeMatch(feedCuiabaNautico, feedCuiabaNautico.leagueId, 0);
  const view = toJogoView(match, new Date("2026-09-22T06:00:00Z"));
  const picksDoJogo = ledgerCuiabaNautico as LedgerPick[];

  it("view carrega liga/kickoff/times do jogo real, id no formato do feed", () => {
    expect(view.id).toBe("brasileirao-serie-b-Cuiabá-Náutico-1790037000.0");
    expect(view.ligaId).toBe("brazil-serie-b"); // toFrontendLeagueId (normalizeMatch)
    expect(view.casa).toBe("Cuiabá");
    expect(view.fora).toBe("Náutico");
    expect(view.kickoffIso).toBe("2026-09-22T00:30:00Z");
    expect(view.estado).toBe("ontem_sem_desfecho"); // finished, aba hoje ainda nao enriqueceu
  });

  it("casa com os 3 picks reais do mesmo jogo (ids batem neste par, mas mesmoJogo nunca olha pra eles)", () => {
    for (const p of picksDoJogo) {
      expect(mesmoJogo(view, p)).toBe(true);
    }
  });

  it("nao casa com um pick de outro jogo (liga certa, kickoff e times errados)", () => {
    expect(mesmoJogo(view, pick({
      match_id: "brasileirao-serie-b-Criciúma-Operário PR-1790029800.0",
      league_id: "brasileirao-serie-b", kickoff_utc: "2026-09-21T22:10:00+00:00",
    }))).toBe(false);
  });
});

describe("mesmoJogo — nunca compara id cru (prova sintética da divergência de formato da spec)", () => {
  // Fixture real: epoch INTEIRO, sem `.0` (ex. da spec:
  // "championship-Middlesbrough-Millwall-1798920000"). Ledger: epoch com
  // `.0` (ex. da spec: "...-1789415100.0"). Mesmo jogo, ids com formato
  // diferente — se `mesmoJogo` comparasse id cru, estes dois NUNCA bateriam.
  // Epoch calculado (nao copiado da spec) para o kickoff usado neste teste.
  const kickoff = "2026-12-01T20:00:00Z";
  const epoch = Math.round(Date.parse(kickoff) / 1000);
  const view = toJogoView(
    normalizeMatch(
      { id: `championship-Middlesbrough-Millwall-${epoch}`, leagueId: "championship",
        homeTeam: { name: "Middlesbrough" }, awayTeam: { name: "Millwall" },
        datetime: kickoff, status: "finished", mercados: [] },
      "championship", 0,
    ),
    new Date("2026-12-02T00:00:00Z"),
  );
  const pickDoMesmoJogo = pick({
    match_id: `championship-Middlesbrough-Millwall-${epoch}.0`, league_id: "championship",
    kickoff_utc: kickoff,
  });

  it("casa mesmo com epoch em formato diferente (inteiro vs decimal) — id nunca comparado", () => {
    expect(view.id).not.toBe(pickDoMesmoJogo.match_id); // ids DIFERENTES...
    expect(mesmoJogo(view, pickDoMesmoJogo)).toBe(true); // ...mas e o mesmo jogo
  });

  it("liga diferente nao casa mesmo com kickoff e times iguais", () => {
    expect(mesmoJogo(view, { ...pickDoMesmoJogo, league_id: "league-one" })).toBe(false);
  });

  it("kickoff diferente (mesmo 1s) nao casa — tolerancia 0", () => {
    expect(mesmoJogo(view, { ...pickDoMesmoJogo, kickoff_utc: "2026-12-01T20:00:01Z" })).toBe(false);
  });

  it("time visitante diferente nao casa", () => {
    expect(mesmoJogo(view, { ...pickDoMesmoJogo, match_id: "championship-Middlesbrough-Millwall FC-1798920000.0" }))
      .toBe(false);
  });

  it("kickoff_utc ausente cai no epoch do sufixo do match_id (linhas antigas, regra do #252-c)", () => {
    expect(mesmoJogo(view, { ...pickDoMesmoJogo, kickoff_utc: null })).toBe(true);
  });

  it("nomes com acento/hifen/maiuscula casam apos normalizacao", () => {
    const viewAcentuada = { ...view, casa: "São Paulo", fora: "Grêmio-RS" };
    const pickCorrespondente = { ...pickDoMesmoJogo, match_id: "championship-Sao Paulo-GremioRS-1798920000.0" };
    expect(mesmoJogo(viewAcentuada, pickCorrespondente)).toBe(true);
  });
});
