import { FormBanca } from "./FormBanca";

export default function BancaPage() {
  return (
    <main className="min-h-screen bg-[var(--sb-tinta)] px-4 py-6">
      <h1 className="mb-4 text-[22px] font-semibold text-[var(--sb-texto)]">Banca</h1>
      <FormBanca />
    </main>
  );
}
