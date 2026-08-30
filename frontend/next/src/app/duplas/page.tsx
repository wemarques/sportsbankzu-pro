// #191: shareable URL for the Duplas section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Duplas | SportsBankZU Pro",
  description: "Combinadas intra-jogo e inter-jogo com maior probabilidade.",
};

export default function DuplasPage() {
  return <Dashboard initialView="duplas" />;
}
