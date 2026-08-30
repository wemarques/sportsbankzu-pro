// #191: shareable URL for the Destaques do Dia section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Destaques do Dia | SportsBankZU Pro",
  description: "Jogos com maior confianca da analise AI e stakes sugeridos do dia.",
};

export default function DestaquesPage() {
  return <Dashboard initialView="recomendadas" />;
}
