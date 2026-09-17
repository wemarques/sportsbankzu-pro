import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { fraseConfianca } from "@/lib/confiancaLiga";
import { LinhaStake } from "@/components/feed/LinhaStake";
import { LinhaConfianca } from "@/components/feed/LinhaConfianca";
import { LinhaSegundoPick } from "@/components/feed/LinhaSegundoPick";
import { LinhaAvaliados } from "@/components/feed/LinhaAvaliados";
import { setBanca } from "@/lib/bancaStore";

const pick = { mercado: "Mais de 2,5 cartões", prob01: 0.59, fairOdd: 1.67, bookOdd: 1.7,
               edge: 0.03, ev: 0.003, classification: "NEUTRO_QUALIFICADO", motivo: "", vale: true };
const conf = (over: object) => ({ leagueId: "mls", level: "ML_ACTIVE", brier: 0.2, accuracy: 0.58, nSamples: 40, trainedAt: null, ...over } as never);

describe("fraseConfianca (os 4 estados do #250 sem sigla)", () => {
  it("ML_ACTIVE com accuracy na media", () => {
    expect(fraseConfianca(conf({}), "MLS")).toEqual({ texto: "MLS: 40 jogos medidos, acerto na média das ligas", numero: 40, semBase: false });
  });
  it("acima e abaixo da media", () => {
    expect(fraseConfianca(conf({ accuracy: 0.66 }), "MLS").texto).toContain("acima da média");
    expect(fraseConfianca(conf({ accuracy: 0.5 }), "MLS").texto).toContain("abaixo da média");
  });
  it("POISSON e ML_SUPPRESSED: modelo geral, sem afirmar acerto", () => {
    expect(fraseConfianca(conf({ level: "POISSON", accuracy: null, nSamples: null }), "MLS")).toEqual({ texto: "MLS: modelo geral, sem histórico próprio", numero: null, semBase: true });
    expect(fraseConfianca(conf({ level: "ML_SUPPRESSED", nSamples: 6, accuracy: null }), "MLS")).toEqual({ texto: "MLS: 6 jogos medidos, ainda sem base", numero: 6, semBase: true });
  });
  it("UNVERIFIED ou nulo: nao afirma nada", () => {
    expect(fraseConfianca(null, "MLS")).toEqual({ texto: "MLS: confiança não verificada", numero: null, semBase: true });
  });
  it("media por parametro substitui o piso fixo (#256 fix round 1)", () => {
    // accuracy 0.50 contra o piso 0.58 (default, sem 3o argumento) fica "abaixo"; contra
    // media=0.50 explicito (mesma accuracy) fica "na media" — prova que o parametro,
    // nao uma constante interna, decide o resultado.
    expect(fraseConfianca(conf({ accuracy: 0.5 }), "MLS").texto).toContain("abaixo da média");
    expect(fraseConfianca(conf({ accuracy: 0.5 }), "MLS", 0.5).texto).toContain("na média");
  });
});

describe("linhas do card", () => {
  beforeEach(() => localStorage.clear());
  it("stake com banca definida", () => {
    setBanca(1000);
    // #257 fix round 1: o valor do stake agora e um link para o glossario, entao o
    // texto do <p> nao fica mais num unico no de texto — checa via toHaveTextContent.
    const { container } = render(<LinhaStake pick={pick} />);
    expect(container.querySelector("p.tnum")).toHaveTextContent(/Da sua banca de R\$ 1\.000,00: R\$/);
    expect(screen.getByRole("link", { name: "R$ 0,64 — o que é Stake" })).toHaveAttribute("href", "/glossario#stake");
    expect(screen.getByRole("link", { name: "ajustar" })).toHaveAttribute("href", "/banca");
  });
  it("stake sem banca: chama para definir", () => {
    render(<LinhaStake pick={pick} />);
    expect(screen.getByRole("link", { name: "stake: defina sua banca" })).toHaveAttribute("href", "/banca");
  });
  it("confianca: numero em teal, semBase em texto-apagado", () => {
    const { rerender } = render(<LinhaConfianca confianca={conf({})} ligaNome="MLS" />);
    expect(screen.getByText("40")).toHaveClass("text-[var(--sb-confianca)]");
    rerender(<LinhaConfianca confianca={null} ligaNome="MLS" />);
    expect(screen.getByText(/não verificada/)).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("media chega por prop, sem hook interno (#256 fix round 1)", () => {
    const { rerender } = render(<LinhaConfianca confianca={conf({ accuracy: 0.5 })} ligaNome="MLS" media={0.5} />);
    expect(screen.getByText(/na média/)).toBeInTheDocument();
    rerender(<LinhaConfianca confianca={conf({ accuracy: 0.5 })} ligaNome="MLS" />);
    expect(screen.getByText(/abaixo da média/)).toBeInTheDocument();
  });
  it("segundo pick: frase completa, sem botao", () => {
    render(<LinhaSegundoPick pick={pick} />);
    expect(screen.getByText("Mais de 2,5 cartões")).toBeInTheDocument();
    expect(screen.getByText("59 em 100, paga 1,70 (+0,03)")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("avaliados com link para #mercados", () => {
    render(<LinhaAvaliados total={12} valem={2} href="/jogos/j1#mercados" />);
    expect(screen.getByRole("link", { name: "ver todos" })).toHaveAttribute("href", "/jogos/j1#mercados");
    expect(screen.getByText(/12 mercados avaliados, 2 valem/)).toBeInTheDocument();
  });
});
