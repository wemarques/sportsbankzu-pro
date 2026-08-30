// #191: shareable URL for the Glossario section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Glossario | SportsBankZU Pro",
  description: "Termos, metricas e classificacoes do SportsBankZU Pro explicados.",
};

export default function GlossarioPage() {
  return <Dashboard initialView="glossario" />;
}
