import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EstadoVazio } from "@/components/marca/EstadoVazio";
describe("EstadoVazio (#262, spec §4)", () => {
  it("monograma apagado e decorativo acima do texto; o texto e o mesmo", () => {
    const { container } = render(<EstadoVazio><p>Nenhum jogo nas ligas escolhidas em 22/09.</p></EstadoVazio>);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-texto-apagado)");
    expect(screen.getByText("Nenhum jogo nas ligas escolhidas em 22/09.")).toBeInTheDocument();
  });
  it("tamanho={32} rende svg width=32; padrao rende width=48", () => {
    const { container: c32 } = render(<EstadoVazio tamanho={32}><p>x</p></EstadoVazio>);
    expect(c32.querySelector("svg")).toHaveAttribute("width", "32");
    const { container: cPadrao } = render(<EstadoVazio><p>y</p></EstadoVazio>);
    expect(cPadrao.querySelector("svg")).toHaveAttribute("width", "48");
  });
});
