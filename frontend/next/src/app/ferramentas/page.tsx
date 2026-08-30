// #191: shareable URL for the Ferramentas section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Ferramentas | SportsBankZU Pro",
  description: "Ferramentas de analise: auditoria AI, comparativos, duplas e gestao de banca.",
};

export default function FerramentasPage() {
  return <Dashboard initialView="ferramentas" />;
}
