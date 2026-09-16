import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TabelaSegmentos } from "@/components/desempenho/TabelaSegmentos";

describe("TabelaSegmentos (#256, F1 — piso n>=20 no acerto por segmento, proibicao 8)", () => {
  it("resolvidos < 20: amostra curta, mesmo com acertos definidos", () => {
    render(<TabelaSegmentos titulo="Por família" linhas={{
      "Over/Under": { picks: 20, acertos: 10, n_jogos: 19, resolvidos: 19, brier: 0.2 },
    }} />);
    expect(screen.getByText("amostra curta")).toBeInTheDocument();
  });
  it("resolvidos == 20 (piso, inclusive): mostra o percentual", () => {
    render(<TabelaSegmentos titulo="Por família" linhas={{
      "Cards": { picks: 21, acertos: 12, n_jogos: 19, resolvidos: 20, brier: null },
    }} />);
    expect(screen.getByText("60%")).toBeInTheDocument();
  });
});
