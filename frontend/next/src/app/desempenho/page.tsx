import { Suspense } from "react";
import { Painel } from "./Painel";
export const metadata = { title: "Desempenho — SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-[calc(100vh-56px)] bg-[var(--sb-tinta)]"><Suspense><Painel /></Suspense></main>;
}
