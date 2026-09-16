import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Talao } from "@/components/feed/Talao";
import { BotaoCopiar } from "@/components/feed/BotaoCopiar";

// prob01 fora de fronteira de arredondamento (0,585 daria 59 — ruling do controller)
const pick = { mercado: "Mais de 6,5 escanteios", prob01: 0.58, fairOdd: 1.67, bookOdd: 1.75,
               edge: 0.08, ev: 0.02, classification: "SAFE", motivo: "", vale: true };

describe("Talao (spec §4.1)", () => {
  it("veredito, frequencia e linha de preco", () => {
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    expect(screen.getByRole("heading", { name: "Mais de 6,5 escanteios" })).toBeInTheDocument();
    expect(screen.getByText("acontece em 58 de cada 100 jogos assim")).toBeInTheDocument();
    expect(screen.getByText("mercado paga 1,75, acima do mínimo 1,67 (+0,08)")).toBeInTheDocument();
  });
  it("abaixo do minimo: glifo ↓ e data-estado; sem cor de contra dentro do talao", () => {
    render(<Talao pick={{ ...pick, bookOdd: 1.62, fairOdd: 1.75 }} futuro={false} preJogo={false} />);
    const linha = screen.getByText(/abaixo do mínimo 1,75/);
    expect(linha).toHaveAttribute("data-estado", "abaixo");
    expect(linha.textContent?.startsWith("↓")).toBe(true);
    expect(linha).not.toHaveStyle({ color: "var(--sb-contra-texto)" });
  });
  it("amanha sem preco nao mostra botao de copiar", () => {
    render(<Talao pick={{ ...pick, bookOdd: null }} futuro preJogo={false} />);
    expect(screen.getByText("vale a partir de 1,67, mercado ainda sem preço")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copiar/ })).toBeNull();
  });
  it("em jogo: sufixo recomendacao pre-jogo", () => {
    render(<Talao pick={pick} futuro={false} preJogo />);
    expect(screen.getByText("recomendação pré-jogo")).toBeInTheDocument();
  });
  it("copiar copia so o numero e confirma no mesmo slot", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    fireEvent.click(screen.getByRole("button", { name: "copiar odd 1,75" }));
    expect(writeText).toHaveBeenCalledWith("1.75");
    await waitFor(() => expect(screen.getByText("1,75 copiado")).toBeInTheDocument());
  });
  it("clipboard negado: contra-texto inline, sem toast", async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("negado")) } });
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    fireEvent.click(screen.getByRole("button", { name: "copiar odd 1,75" }));
    await waitFor(() => expect(screen.getByText("não deu pra copiar — selecione o número")).toBeInTheDocument());
  });
  it("nada dentro do talao usa a cor confianca", () => {
    const { container } = render(<Talao pick={pick} futuro={false} preJogo={false} />);
    expect(container.innerHTML).not.toContain("--sb-confianca");
  });
  it("falha de copia dentro do talao nao usa contra-texto", async () => {
    const original = navigator.clipboard;
    Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("negado")) }, configurable: true });
    render(<BotaoCopiar odd={1.75} sobre="talao" />);
    fireEvent.click(screen.getByRole("button", { name: "copiar odd 1,75" }));
    const aviso = await screen.findByText("não deu pra copiar — selecione o número");
    expect(aviso.className).toContain("tinta-do-talao");
    expect(aviso.className).not.toContain("contra-texto");
    Object.defineProperty(navigator, "clipboard", { value: original, configurable: true });
  });
});
