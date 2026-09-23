import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { Cabecalho } from "@/components/marca/Cabecalho";

describe("Cabecalho (#262, spec §1)", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date("2026-09-23T02:59:00Z")); });
  afterEach(() => vi.useRealTimers());
  it("banner com a marca inteira, link para /jogos e a data BRT", () => {
    render(<Cabecalho />);
    const banner = screen.getByRole("banner");
    const link = screen.getByRole("link", { name: "sportsbankzu, ir para os jogos" });
    expect(link).toHaveAttribute("href", "/jogos");
    expect(link.textContent).toBe("sportsbankzu");
    expect(banner).toHaveTextContent("terça, 22 de setembro");
  });
  it("vira a data no cliente a meia-noite BRT, sem refresh", () => {
    render(<Cabecalho />);
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(screen.getByRole("banner")).toHaveTextContent("quarta, 23 de setembro");
  });
});
