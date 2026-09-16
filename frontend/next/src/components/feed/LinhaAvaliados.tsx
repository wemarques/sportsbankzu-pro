import Link from "next/link";
import { avaliados } from "@/lib/copy";

export function LinhaAvaliados({ total, valem, href }: { total: number; valem: number; href: string }) {
  return (
    <p className="text-[13px] text-[var(--sb-texto-apagado)]">
      {avaliados(total, valem)} — <Link href={href} className="sb-foco text-[var(--sb-texto)] underline">ver todos</Link>
    </p>
  );
}
