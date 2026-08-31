// #191: shareable URL for the Glossário section (same dashboard, deep-linked view).
import Dashboard from "../dashboard/page";

export const metadata = {
  title: "Glossário | SportsBankZU Pro",
  description: "Termos, métricas e classificacoes do SportsBankZU Pro explicados.",
};

export default function GlossarioPage() {
  return <Dashboard initialView="glossario" />;
}
