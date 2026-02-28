import "../../styles/ai-audit.css";
import AIReviewDashboard from "../../components/AIReviewDashboard";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "AI Audit - SportsBankZU Pro",
  description: "Auditoria inteligente de prognósticos com Mistral AI",
};

export default function AIAuditPage() {
  return <AIReviewDashboard />;
}
