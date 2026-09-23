import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { Cabecalho } from "@/components/marca/Cabecalho";

const DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

describe("Cabecalho (#262, spec §1)", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date("2026-09-23T02:59:00Z")); });
  afterEach(() => vi.useRealTimers());
  it("antes do effect (SSR), o banner nao contem a data (so-cliente, fix wave #262)", () => {
    const html = renderToString(<Cabecalho />);
    expect(html).not.toContain("de setembro");
    for (const dia of DIAS_SEMANA) expect(html).not.toContain(dia);
  });
  it("banner com a marca inteira, link para /jogos e a data BRT", () => {
    render(<Cabecalho />);
    const banner = screen.getByRole("banner");
    const link = screen.getByRole("link", { name: "sportsbankzu, ir para os jogos" });
    expect(link).toHaveAttribute("href", "/jogos");
    expect(link).toHaveAccessibleName("sportsbankzu, ir para os jogos");
    expect(link.querySelector("span")).toHaveTextContent("sportsbankzu");
    // render() ja flush o effect que faz setAgora(new Date()) (act() sincrono).
    expect(banner).toHaveTextContent("terça, 22 de setembro");
  });
  it("vira a data no cliente a meia-noite BRT, sem refresh", () => {
    render(<Cabecalho />);
    expect(screen.getByRole("banner")).toHaveTextContent("terça, 22 de setembro");
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(screen.getByRole("banner")).toHaveTextContent("quarta, 23 de setembro");
  });
});
