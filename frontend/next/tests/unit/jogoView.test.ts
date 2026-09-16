import { describe, expect, it } from "vitest";
import { escolherTalao, toJogoView, type PickView } from "@/lib/jogoView";
import { normalizeMatch } from "@/lib/normalizeMatch";
import fixture from "../fixtures/fixtures.2026-09-15.v1.json";

const AGORA = new Date("2026-09-15T12:00:00Z");

function pick(over: Partial<PickView>): PickView {
  return { mercado: "x", prob01: 0.5, fairOdd: 2, bookOdd: 2.1, edge: 0.05, ev: 0.05,
           classification: "SAFE", motivo: "", vale: true, ...over };
}

describe("escolherTalao (spec §4.1)", () => {
  it("maior edge vence", () => {
    const a = pick({ mercado: "a", edge: 0.08 }), b = pick({ mercado: "b", edge: 0.03 });
    expect(escolherTalao([b, a])).toEqual({ talao: a, segundo: b });
  });
  it("empate de edge: maior chance", () => {
    const a = pick({ mercado: "a", edge: 0.05, prob01: 0.58 }), b = pick({ mercado: "b", edge: 0.05, prob01: 0.61 });
    expect(escolherTalao([a, b]).talao).toBe(b);
  });
  it("so quem vale disputa; sem ninguem, nulo", () => {
    const n = pick({ mercado: "n", vale: false, classification: "NEUTRO", edge: 0.9 });
    expect(escolherTalao([n])).toEqual({ talao: null, segundo: null });
  });
});

describe("toJogoView — estados (spec §4.2)", () => {
  const base = {
    id: "j1", leagueId: "mls", homeTeam: { name: "Toronto" }, awayTeam: { name: "Nashville SC" },
    datetime: "2026-09-15T23:30:00Z", status: "scheduled", odds: {}, stats: {},
  };
  const merc = (classification: string, extra = {}) => ({
    mercado: "Escanteios Over 6.5", status: classification, prob_min: 57, prob_max: 59, odd_minima: 1.75,
    classification, ev: 0.01, edge: 0.08, fair_odd: 1.67, book_odd: 1.75, calibrated_probability: 0.585,
    reason_codes: [], ...extra,
  });
  const view = (raw: object) => toJogoView(normalizeMatch(raw, "mls", 0), AGORA);

  it("vale", () => {
    const v = view({ ...base, mercados: [merc("SAFE"), merc("NEUTRO_QUALIFICADO", { mercado: "Cartoes Over 2.5", edge: 0.03 })] });
    expect(v.estado).toBe("vale");
    expect(v.talao?.mercado).toBe("Escanteios Over 6.5");
    expect(v.segundo?.mercado).toBe("Cartões Over 2.5");
    expect(v.totalAvaliados).toBe(2); expect(v.totalValem).toBe(2);
  });
  it("direcao: so NEUTRO", () => {
    const v = view({ ...base, mercados: [merc("NEUTRO", { mercado: "Over 2.5 gols", book_odd: 1.62, fair_odd: 1.75, edge: -0.13 })] });
    expect(v.estado).toBe("direcao"); expect(v.talao).toBeNull(); expect(v.direcao?.mercado).toBe("Over 2.5 gols");
  });
  it("nada: so NO_BET", () => {
    expect(view({ ...base, mercados: [merc("NO_BET", { reason_codes: ["NEGATIVE_EV"] })] }).estado).toBe("nada");
  });
  it("nada: mercados vazio (o pipeline nao envia NO_BET; eles vivem em rejected_insights)", () => {
    const v = view({ ...base, mercados: [], stats: { rejected_insights: [{ market: "Over 2.5", reason: "NEGATIVE_EV" }] } });
    expect(v.estado).toBe("nada"); expect(v.totalAvaliados).toBe(1); expect(v.totalValem).toBe(0);
  });
  it("amanha sem preco: data futura e book_odd nulo no talao", () => {
    const v = view({ ...base, datetime: "2026-09-16T23:30:00Z", mercados: [merc("SAFE", { book_odd: null })] });
    expect(v.estado).toBe("amanha_sem_preco"); expect(v.talao?.bookOdd).toBeNull();
  });
  it("em jogo", () => {
    const v = view({ ...base, status: "live", period: "2T", minute: 61, score: { home: 1, away: 0 }, mercados: [merc("SAFE")] });
    expect(v.estado).toBe("em_jogo"); expect(v.aoVivo).toEqual({ periodo: "2T", minuto: 61, placar: "1–0" });
  });
  it("ontem sem desfecho: jogo encerrado sem resultado do ledger", () => {
    expect(view({ ...base, datetime: "2026-09-14T23:30:00Z", status: "finished", mercados: [merc("SAFE")] }).estado).toBe("ontem_sem_desfecho");
  });
  it("motivo de recusa em duas palavras", () => {
    const v = view({ ...base, mercados: [merc("NO_BET", { reason_codes: ["LOW_DATA_QUALITY"] })] });
    expect(v.mercados[0].motivo).toBe("amostra curta");
  });
  it("fixture real: todo jogo cai num estado e o talao, quando existe, vale", () => {
    for (const raw of fixture.matches as { leagueId: string }[]) {
      const v = toJogoView(normalizeMatch(raw, raw.leagueId, 0), AGORA);
      expect(["vale", "direcao", "nada", "amanha_sem_preco", "em_jogo", "ontem", "ontem_sem_desfecho"]).toContain(v.estado);
      if (v.talao) expect(v.talao.vale).toBe(true);
    }
  });

  it("snapshot do fixture real", () => {
    const views = (fixture.matches as { leagueId: string }[]).map((r) => toJogoView(normalizeMatch(r, r.leagueId, 0), AGORA));
    expect(views.map((v) => ({ id: v.id, estado: v.estado, talao: v.talao?.mercado ?? null, valem: v.totalValem }))).toMatchSnapshot();
  });
});
