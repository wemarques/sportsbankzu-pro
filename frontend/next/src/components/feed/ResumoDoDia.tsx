import type { LedgerResumo } from "@/lib/ledgerApi";
import { resumoDoDia, VAZIOS } from "@/lib/copy";

/** #256 — spec §5 e §4.5: acerto agregado do dia em ontem; sem reais (dinheiro fica
 * em /desempenho). Quando não há picks resolvidos (resultado ainda em processamento),
 * exibe mensagem de pendência. */
export function ResumoDoDia({ resumo }: { resumo: LedgerResumo | null }) {
  if (!resumo) return null;
  if (resumo.resolvidos === 0)
    return (
      <p className="tnum my-2 text-[14px] texto-apagado" role="status">
        {VAZIOS.resultadoPendente}
      </p>
    );
  return (
    <p className="tnum my-2 text-[14px]" role="status">
      {resumoDoDia(resumo.acertos, resumo.resolvidos, resumo.jogos)}
    </p>
  );
}
