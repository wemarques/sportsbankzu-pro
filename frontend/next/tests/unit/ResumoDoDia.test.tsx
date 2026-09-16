import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResumoDoDia } from "@/components/feed/ResumoDoDia";

describe("ResumoDoDia (#256, spec §4.5 — sem reais por pick em ontem)", () => {
  it("mostra acerto agregado do dia", () => {
    render(<ResumoDoDia resumo={{ picks: 5, acertos: 3, jogos: 4, resolvidos: 4 }} />);
    expect(screen.getByText("Ontem: 3 de 4 picks fechados acertaram em 4 jogos")).toBeInTheDocument();
  });
  it("quando todos os picks estão pendentes, mostra mensagem de resultado pendente", () => {
    render(<ResumoDoDia resumo={{ picks: 5, acertos: 0, jogos: 4, resolvidos: 0 }} />);
    expect(screen.getByText("resultado ainda não conferido")).toBeInTheDocument();
    expect(screen.getByText("resultado ainda não conferido")).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("resumo nulo (ainda carregando), nao renderiza nada", () => {
    const { container } = render(<ResumoDoDia resumo={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
