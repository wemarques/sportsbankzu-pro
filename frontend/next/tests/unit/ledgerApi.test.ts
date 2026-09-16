import { afterEach, describe, expect, it, vi } from "vitest";
import { getLedgerDia, getLedgerAgregado } from "@/lib/ledgerApi";

function stubFetch(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    status,
    json: () => Promise.resolve(body),
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("ledgerApi (#256)", () => {
  it("getLedgerDia: sucesso devolve dados sem o envelope 'ok'", async () => {
    stubFetch({ ok: true, data: "2026-09-14", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
    const r = await getLedgerDia("2026-09-14");
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.dados).toEqual({ data: "2026-09-14", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
  });
  it("getLedgerDia: erro estruturado do proxy vira 'erro'", async () => {
    stubFetch({ ok: false, error: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório" } }, 400);
    const r = await getLedgerDia("lixo");
    expect(r).toEqual({ ok: false, erro: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório" } });
  });
  it("getLedgerDia: falha de rede (fetch rejeita) vira NETWORK_ERROR, nunca lança", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const r = await getLedgerDia("2026-09-14");
    expect(r.ok).toBe(false);
    if (r.ok === false) expect(r.erro.kind).toBe("NETWORK_ERROR");
  });
  it("getLedgerAgregado: monta querystring com periodo/familia/liga", async () => {
    stubFetch({ ok: true, periodo: "7d", familia: "Corners", liga: "mls", acerto: { picks: 1, acertos: 1, jogos: 1, resolvidos: 1 } });
    await getLedgerAgregado("7d", "Corners", "mls");
    const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(chamada).toContain("periodo=7d");
    expect(chamada).toContain("familia=Corners");
    expect(chamada).toContain("liga=mls");
  });
  it("getLedgerAgregado: sem familia/liga nao manda os parametros", async () => {
    stubFetch({ ok: true, periodo: "30d", acerto: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
    await getLedgerAgregado("30d");
    const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(chamada).not.toContain("familia=");
    expect(chamada).not.toContain("liga=");
  });
});
