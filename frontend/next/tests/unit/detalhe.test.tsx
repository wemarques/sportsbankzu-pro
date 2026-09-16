import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { fraseOrigem } from "@/lib/copy";
import type { PickView } from "@/lib/jogoView";

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
  it("de onde vem o numero: frase com unidade; campo ausente some", () => {
    expect(fraseOrigem({ golsCasa: 3, golsFora: 2.5, golsLiga: 4.9, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "Toronto", "Nashville", "MLS"))
      .toBe("Toronto faz 3,0 gols por jogo em casa; Nashville sofre 2,5 fora; a MLS tem 4,9 por jogo.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: 5.1, escanteiosFora: 4.6, escanteiosLiga: 9.8 }, "Toronto", "Nashville", "MLS"))
      .toBe("Toronto força 5,1 escanteios por jogo em casa; Nashville 4,6 fora; a MLS tem 9,8 por jogo.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "a", "b", "c")).toBeNull();
  });
});
