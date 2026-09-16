import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CardJogo } from "@/components/feed/CardJogo";
import type { JogoView, PickView } from "@/lib/jogoView";

const p = (o: Partial<PickView>): PickView => ({ mercado: "Mais de 6,5 escanteios", prob01: 0.585, fairOdd: 1.67, bookOdd: 1.75, edge: 0.08, ev: 0.02, classification: "SAFE", motivo: "", vale: true, ...o });
const base: JogoView = { id: "j1", ligaId: "mls", ligaNome: "MLS", casa: "Toronto", fora: "Nashville SC", kickoffIso: "2026-09-09T23:30:00Z",
  estado: "vale", talao: p({}), segundo: null, direcao: null, mercados: [p({})], totalAvaliados: 12, totalValem: 1, aoVivo: null, resultado: null };
const render_ = (j: JogoView) => render(<CardJogo jogo={j} confianca={null} selecionado={false} onAbrir={() => {}} hrefDetalhe="/jogos/j1" />);

describe("CardJogo e um switch sobre o estado (spec §4.2)", () => {
  it("vale: talao + stake + confianca + avaliados; cabecalho 'MLS, 20:30'", () => {
    render_(base);
    expect(screen.getByText("MLS, 20:30")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "pick recomendado" })).toBeInTheDocument();
    expect(screen.getByText(/12 mercados avaliados, 1 vale/)).toBeInTheDocument();
  });
  it("direcao: sem talao, sem stake, frase de direcao", () => {
    render_({ ...base, estado: "direcao", talao: null, direcao: p({ mercado: "Mais de 2,5 gols", prob01: 0.57, classification: "NEUTRO", vale: false }) });
    expect(screen.queryByRole("region", { name: "pick recomendado" })).toBeNull();
    expect(screen.getByText("Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje")).toBeInTheDocument();
    expect(screen.queryByText(/banca/)).toBeNull();
  });
  it("nada: uma linha colapsada", () => {
    render_({ ...base, estado: "nada", talao: null, totalValem: 0 });
    expect(screen.getByText("12 mercados avaliados, nenhum vale hoje")).toBeInTheDocument();
  });
  it("em jogo: periodo, minuto, placar", () => {
    render_({ ...base, estado: "em_jogo", aoVivo: { periodo: "2T", minuto: 61, placar: "1–0" } });
    expect(screen.getByText("2T, 61' 1–0")).toBeInTheDocument();
    expect(screen.getByText("recomendação pré-jogo")).toBeInTheDocument();
  });
  it("ontem: faixa de resultado com glifo", () => {
    render_({ ...base, estado: "ontem", resultado: { acertou: false, detalhe: "5 escanteios" } });
    expect(screen.getByText("× fechou com 5 escanteios")).toHaveClass("text-[var(--sb-contra-texto)]");
  });
  it("ontem sem desfecho", () => {
    render_({ ...base, estado: "ontem_sem_desfecho" });
    expect(screen.getByText("resultado ainda não conferido")).toBeInTheDocument();
  });
  it("amanha sem preco: talao com 'ainda sem preço', sem stake", () => {
    render_({ ...base, estado: "amanha_sem_preco", talao: p({ bookOdd: null }), mercados: [p({ bookOdd: null })] });
    expect(screen.getByText("vale a partir de 1,67, mercado ainda sem preço")).toBeInTheDocument();
    expect(screen.queryByText(/na sua banca atual/)).toBeNull();
  });
  it("com onAbrir o titulo e botao; sem onAbrir e link", () => {
    render_({ ...base });
    expect(screen.getByRole("button", { name: "Toronto × Nashville SC" })).toBeInTheDocument();
    render(<CardJogo jogo={base} confianca={null} selecionado hrefDetalhe="/jogos/j1" />);
    expect(screen.getByRole("link", { name: "Toronto × Nashville SC" })).toHaveAttribute("href", "/jogos/j1");
  });
});
