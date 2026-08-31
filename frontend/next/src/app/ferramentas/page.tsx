// #191: shareable URL for the Ferramentas section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Ferramentas | SportsBankZU Pro",
  description: "Ferramentas de análise: auditoria AI, comparativos, duplas e gestão de banca.",
};

export default function FerramentasPage() {
  return <Dashboard initialView="ferramentas" />;
}
