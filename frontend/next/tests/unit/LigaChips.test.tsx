import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LigaChips } from "@/components/feed/LigaChips";

describe("LigaChips (#262, spec §2)", () => {
  const ligas = [{ id: "premier-league", nome: "Premier League" }, { id: "championship", nome: "Championship" }];
  it("selecionado leva teal na borda e no texto; nao selecionado nao leva teal em lugar nenhum", () => {
    render(<LigaChips ligas={ligas} ativa="premier-league" onChange={vi.fn()} />);
    const sel = screen.getByRole("button", { name: "Premier League" });
    const nao = screen.getByRole("button", { name: "Championship" });
    expect(sel).toHaveAttribute("aria-pressed", "true");
    expect(sel.className).toContain("aria-pressed:border-[var(--sb-marca)]");
    expect(sel.className).toContain("aria-pressed:text-[var(--sb-marca)]");
    expect(sel.className).not.toContain("aria-pressed:bg-");
    expect(nao.className).toContain("hover:bg-[var(--sb-hover)]");
    expect(nao.className).not.toMatch(/hover:border|hover:text/);
  });
});
