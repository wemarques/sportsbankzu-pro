import { Suspense } from "react";
import { Feed } from "./Feed";
export const metadata = { title: "Jogos — SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-[calc(100vh-56px)] bg-[var(--sb-tinta)]"><Suspense><Feed /></Suspense></main>;
}
