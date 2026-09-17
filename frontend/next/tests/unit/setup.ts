import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// #257 — next/font/google so existe no build do Next; fora dele o modulo e um stub vazio.
const fonteFalsa = (nome: string) => () => ({ className: `fonte-${nome}`, variable: `--font-${nome}`, style: { fontFamily: nome } });
vi.mock("next/font/google", () => ({
  Barlow_Condensed: fonteFalsa("barlow"),
  Zilla_Slab: fonteFalsa("zilla"),
  Source_Sans_3: fonteFalsa("source"),
}));
