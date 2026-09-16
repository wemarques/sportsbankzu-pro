import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TextoComTermos } from "@/components/TextoComTermos";

describe("TextoComTermos (#257)", () => {
  it("texto sem termo passa direto", () => {
    render(<TextoComTermos texto="sem termo aqui" />);
    expect(screen.getByText("sem termo aqui")).toBeInTheDocument();
  });
  it("{term:id|texto} vira link para /glossario#id", () => {
    const { container } = render(<TextoComTermos texto="o {term:edge|edge} de hoje" />);
    const link = screen.getByRole("link", { name: "edge" });
    expect(link).toHaveAttribute("href", "/glossario#edge");
    // #257: ruling do controller — Testing Library trima texto por nó; a borda e provada pelo textContent
    expect(container.textContent).toBe("o edge de hoje");
  });
});
