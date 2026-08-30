// #191: shareable URL for the Campeonatos section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Campeonatos | SportsBankZU Pro",
  description: "Selecione e gerencie as ligas analisadas pelo SportsBankZU Pro.",
};

export default function CampeonatosPage() {
  return <Dashboard initialView="campeonatos" />;
}
