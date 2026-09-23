import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";

describe("MonogramaSBZ (#262, spec §4)", () => {
  it("decorativo por padrao, 24 px, letras SBZ em teal sobre tinta", () => {
    const { container } = render(<MonogramaSBZ />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg.querySelector("rect")).toHaveAttribute("fill", "var(--sb-tinta)");
    expect(svg.querySelector("text")).toHaveTextContent("SBZ");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-marca)");
  });
  it("apagado troca a cor e nao decorativo ganha titulo acessivel", () => {
    const { container } = render(<MonogramaSBZ tamanho={48} apagado decorativo={false} />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("role", "img");
    expect(svg.querySelector("title")).toHaveTextContent("sportsbankzu");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-texto-apagado)");
  });
});
