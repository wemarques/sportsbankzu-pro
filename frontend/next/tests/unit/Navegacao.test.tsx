import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Navegacao } from "@/components/nav/Navegacao";

let pathname = "/jogos";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

describe("Navegacao (#257, spec §3)", () => {
  it("quatro links, Jogos marcado como ativo em /jogos", () => {
    pathname = "/jogos";
    render(<Navegacao />);
    const jogos = screen.getByRole("link", { name: "Jogos" });
    const banca = screen.getByRole("link", { name: "Banca" });
    const desempenho = screen.getByRole("link", { name: "Desempenho" });
    const glossario = screen.getByRole("link", { name: "Glossário" });
    expect(jogos).toHaveAttribute("aria-current", "page");
    expect(banca).toHaveAttribute("href", "/banca");
    expect(desempenho).toHaveAttribute("href", "/desempenho");
    expect(glossario).toHaveAttribute("href", "/glossario");
  });

  it("some em rota escondida (/)", () => {
    pathname = "/";
    const { container } = render(<Navegacao />);
    expect(container.firstChild).toBeNull();
  });

  it("#262: o item ativo leva teal, os demais nao", () => {
    pathname = "/banca";
    render(<Navegacao />);
    const banca = screen.getByRole("link", { name: "Banca" });
    expect(banca.className).toContain("aria-[current=page]:text-[var(--sb-marca)]");
    expect(banca.className).not.toContain("aria-[current=page]:text-[var(--sb-texto)]");
  });
});
