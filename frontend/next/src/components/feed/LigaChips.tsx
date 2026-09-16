"use client";
export function LigaChips({ ligas, ativa, onChange }: { ligas: { id: string; nome: string }[]; ativa: string; onChange: (id: string) => void }) {
  const todas = [{ id: "todas", nome: "todas" }, ...ligas];
  return (
    <div className="relative">
      <div className="flex gap-2 overflow-x-auto whitespace-nowrap py-2 [scrollbar-width:none]" aria-label="ligas">
        {todas.map((l) => (
          <button key={l.id} type="button" aria-pressed={l.id === ativa} onClick={() => onChange(l.id)}
            className="sb-foco rounded-full border border-[var(--sb-linha)] px-3 py-1 text-[13px] aria-pressed:border-[var(--sb-texto)] aria-pressed:bg-[var(--sb-hover)]">
            {l.nome}
          </button>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[var(--sb-tinta)]" aria-hidden="true" />
    </div>
  );
}
