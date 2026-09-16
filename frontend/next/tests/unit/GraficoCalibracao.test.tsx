import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraficoCalibracao } from "@/components/desempenho/GraficoCalibracao";

describe("GraficoCalibracao (spec §5 — unico visual da tela, leitura em uma frase)", () => {
  it("amostra curta: buckets nulo", () => {
    render(<GraficoCalibracao buckets={null} />);
    expect(screen.getByText("amostra curta")).toBeInTheDocument();
  });
  it("desenha os pontos com n>0 e a frase do maior desvio; tabela sr-only com todos", () => {
    render(<GraficoCalibracao buckets={[
      { prob_media: 0.55, freq_real: 0.60, n: 30 },
      { prob_media: null, freq_real: null, n: 0 },
      { prob_media: 0.82, freq_real: 0.60, n: 22 },
    ]} />);
    const fig = screen.getByRole("img");
    expect(fig.getAttribute("aria-label")).toContain("quando o painel disse 82");
    expect(fig.getAttribute("aria-label")).toContain("aconteceu 60 em cada 100");
    expect(screen.getAllByRole("row")).toHaveLength(3); // cabecalho + 2 pontos com n>0
  });
});
