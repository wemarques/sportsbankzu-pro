import type { PickView } from "@/lib/jogoView";
import { fmtOdd, fmtPct } from "@/lib/formato";
import { BotaoCopiar } from "@/components/feed/BotaoCopiar";

function status(p: PickView) {
  if (p.vale) return { texto: "vale", classe: "" };
  if (p.classification === "NO_BET") return { texto: p.motivo || "não vale", classe: "" };
  if (p.bookOdd == null) return { texto: "sem preço", classe: "" };
  if (p.bookOdd < p.fairOdd) return { texto: "↓ abaixo do mínimo", classe: "text-[var(--sb-contra-texto)]" };
  return { texto: p.motivo || "não vale", classe: "" };
}

export function TabelaMercados({ mercados }: { mercados: PickView[] }) {
  return (
    <table id="mercados" className="w-full text-[14px]">
      <thead><tr className="text-left text-[13px] text-[var(--sb-texto-apagado)]">
        <th scope="col" className="py-1 font-normal">mercado</th><th scope="col" className="py-1 text-right font-normal">chance</th>
        <th scope="col" className="py-1 text-right font-normal">mínima</th><th scope="col" className="py-1 text-right font-normal">paga</th>
        <th scope="col" className="py-1 font-normal">status</th><th scope="col" className="py-1 font-normal"></th>
      </tr></thead>
      <tbody>
        {mercados.map((p) => { const s = status(p); return (
          <tr key={p.mercado} className={`border-t border-[var(--sb-linha)] ${p.vale ? "" : "text-[var(--sb-texto-apagado)]"}`}>
            <td className="py-2">{p.mercado}</td>
            <td className="tnum py-2 text-right">{fmtPct(p.prob01)}%</td>
            <td className="tnum py-2 text-right">{fmtOdd(p.fairOdd)}</td>
            <td className="tnum py-2 text-right">{p.bookOdd != null ? fmtOdd(p.bookOdd) : "—"}</td>
            <td className={`py-2 ${s.classe}`}>{s.texto}</td>
            <td className="py-2">{p.vale && p.bookOdd != null && <BotaoCopiar odd={p.bookOdd} sobre="painel" />}</td>
          </tr>); })}
      </tbody>
    </table>
  );
}
