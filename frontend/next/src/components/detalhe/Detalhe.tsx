import type { JogoView } from "@/lib/jogoView";

/** Placeholder — a Task 16 substitui por implementacao completa (spec §4.3). */
export function Detalhe({ jogo }: { jogo: JogoView; confianca: unknown }) {
  return <p>{jogo.casa} × {jogo.fora}</p>;
}
