import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { Detalhe } from "@/components/detalhe/Detalhe";
import { fraseOrigem } from "@/lib/copy";
import type { JogoView, PickView } from "@/lib/jogoView";

const p = (o: Partial<PickView>): PickView => ({ mercado: "x", prob01: 0.5, fairOdd: 2, bookOdd: 2.1, edge: 0.05, ev: 0.05, classification: "SAFE", motivo: "", vale: true, ...o });

describe("detalhe (spec §4.3)", () => {
  it("escala: aria-label com a frase inteira; marca e zona", () => {
    render(<EscalaConfianca prob01={0.58} margem={[0.52, 0.64]} nJogos={40} liga="MLS" />);
    const fig = screen.getByRole("img");
    expect(fig).toHaveAttribute("aria-label", "58 em cada 100, com margem de 52 a 64, em 40 jogos medidos da MLS");
    expect(screen.getByText("50")).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("tabela: cabecalhos, status em texto, copiar so em quem vale, recusados apagados", () => {
    render(<TabelaMercados mercados={[
      p({ mercado: "Mais de 6,5 escanteios", prob01: 0.58, fairOdd: 1.67, bookOdd: 1.75 }),
      p({ mercado: "Mais de 2,5 gols", prob01: 0.57, fairOdd: 1.75, bookOdd: 1.62, classification: "NEUTRO", vale: false, motivo: "sem valor" }),
      p({ mercado: "Ambos marcam", prob01: 0.51, fairOdd: 1.96, bookOdd: null, classification: "NO_BET", vale: false, motivo: "sem preço" }),
    ]} />);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["mercado", "chance", "mínima", "paga", "status", ""]);
    expect(screen.getByText("vale")).toBeInTheDocument();
    expect(screen.getByText("↓ abaixo do mínimo")).toHaveClass("text-[var(--sb-contra-texto)]");
    expect(screen.getByText("sem preço")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /copiar odd/ })).toHaveLength(1);
    expect(screen.getByText("Ambos marcam").closest("tr")).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("recusado mostra o motivo, nao 'sem preço'", () => {
    render(<TabelaMercados mercados={[p({ mercado: "Mais de 3,5 gols", prob01: 0.35, fairOdd: 2.86, bookOdd: null, classification: "NO_BET", vale: false, motivo: "amostra curta" })]} />);
    expect(screen.getByText("amostra curta")).toBeInTheDocument();
    expect(screen.queryByText("sem preço")).toBeNull();
    expect(screen.queryByRole("button", { name: /copiar odd/ })).toBeNull();
  });
  it("de onde vem o numero: frase com unidade; campo ausente some", () => {
    expect(fraseOrigem({ golsCasa: 3, golsFora: 2.5, golsLiga: 4.9, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "Toronto", "Nashville", "MLS"))
      .toBe("Nos jogos do Toronto saem 3,0 gols por partida na temporada; nos do Nashville, 2,5; média da MLS: 4,9.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: 5.1, escanteiosFora: 4.6, escanteiosLiga: 9.8 }, "Toronto", "Nashville", "MLS"))
      .toBe("Toronto cobra 5,1 escanteios por jogo na temporada; Nashville, 4,6; média da MLS: 9,8.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "a", "b", "c")).toBeNull();
  });
});

afterEach(() => vi.unstubAllGlobals());

const jogoConfianca: JogoView = {
  id: "j1", ligaId: "mls", ligaNome: "MLS", casa: "Toronto", fora: "Nashville SC", kickoffIso: "2026-09-09T23:30:00Z",
  estado: "vale", talao: p({}), segundo: null, direcao: null, mercados: [p({})], totalAvaliados: 1, totalValem: 1,
  aoVivo: null, resultado: null,
  origem: { golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null },
};

describe("Detalhe usa nJogos do ledger nos dois lugares, nao mais o treino ML (#256)", () => {
  it("nenhuma das duas chamadas mostra confianca.nSamples (999); DeOndeVemONumero mostra o numero do ledger (40)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({
        ok: true, periodo: "temporada",
        por_liga: { mls: { picks: 12, acertos: 7, n_jogos: 40, resolvidos: 12, brier: 0.24 } },
      }),
    }));
    render(<Detalhe jogo={jogoConfianca} confianca={{ leagueId: "mls", level: "ML_ACTIVE", brier: 0.2, accuracy: 0.58, nSamples: 999, trainedAt: null }} />);
    await waitFor(() => expect(screen.getByText(/40 jogos medidos/)).toBeInTheDocument());
    expect(screen.queryByText(/999/)).toBeNull();
  });
});
