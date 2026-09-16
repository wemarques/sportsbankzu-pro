import { Suspense } from "react";
import { Feed } from "./Feed";
export const metadata = { title: "Jogos — SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-screen bg-[var(--sb-tinta)]"><Suspense><Feed /></Suspense></main>;
}
