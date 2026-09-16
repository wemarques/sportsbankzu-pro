"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useBanca, calcStake } from "@/lib/bancaStore";
import { fmtReais } from "@/lib/formato";

export function FormBanca() {
  const [banca, setBanca] = useBanca();
  const [valor, setValor] = useState("");
  const [msg, setMsg] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  useEffect(() => { if (banca != null && valor === "") setValor(String(banca).replace(".", ",")); }, [banca, valor]);

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    const n = parseFloat(valor.replace(/\./g, "").replace(",", "."));
    if (setBanca(n) === "invalida") { setMsg({ tipo: "erro", texto: "banca precisa ser um valor em reais" }); return; }
    setMsg({ tipo: "ok", texto: "banca salva" });
  }
  // consequencia: o maior stake que um pick SAFE sugeriria hoje (prob 0,60, odd 1,90 → cap de 5%)
  const teto = banca != null ? calcStake(0.6, 1.9, banca, "SAFE") : null;
  return (
    <form onSubmit={salvar} className="max-w-[70ch] space-y-3 text-[var(--sb-texto)]">
      <label className="block text-[16px]" htmlFor="banca">Sua banca</label>
      <input id="banca" ref={ref} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)}
        className="sb-foco tnum w-full rounded-[var(--sb-raio-painel)] border border-[var(--sb-linha)] bg-[var(--sb-painel)] px-3 py-2 text-[22px]" placeholder="R$ 0,00" />
      <div className="flex items-center gap-3">
        <button type="submit" className="sb-foco rounded-[var(--sb-raio-painel)] border border-[var(--sb-texto)] px-4 py-2 text-[14px]">Salvar banca</button>
        <span className={`min-h-[20px] text-[14px] ${msg?.tipo === "erro" ? "text-[var(--sb-contra-texto)]" : ""}`} aria-live="polite">{msg?.texto ?? ""}</span>
      </div>
      {banca == null
        ? <p className="text-[14px] text-[var(--sb-texto-apagado)]">Defina a banca para ver quanto apostar em cada jogo.</p>
        : <p className="text-[14px]">Cada pick sugere uma fração dela, hoje até {fmtReais(teto ?? 0)} por jogo.</p>}
      <p className="text-[13px]"><Link href="/glossario#stake" className="sb-foco underline">Como a fração é calculada</Link></p>
    </form>
  );
}
