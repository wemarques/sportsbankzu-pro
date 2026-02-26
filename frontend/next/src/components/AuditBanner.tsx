"use client";

import { useEffect, useState } from "react";
import { Bell, X, TrendingUp, AlertTriangle, CheckCircle } from "lucide-react";
import { getAuditStatus, type AuditStatusResponse } from "@/lib/api";

export default function AuditBanner() {
  const [data, setData] = useState<AuditStatusResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    getAuditStatus(3).then(setData).catch(() => {});
  }, []);

  if (dismissed || !data) return null;

  const { summary, last_batch_audit, recent_corrections } = data;

  // Nothing to show
  if (!summary.has_recent_activity && summary.total_corrections_applied === 0) {
    return null;
  }

  // Determine tone based on corrections
  const cronCorrections = recent_corrections.filter(
    (c) => c.applied_by === "cron_auto",
  );
  const hasCorrectionActivity = cronCorrections.length > 0;

  // If there is audit activity but no corrections, show a subtle success banner
  if (!hasCorrectionActivity && summary.has_recent_activity) {
    return null; // Only show banner when there are corrections to report
  }

  // Extract accuracy from the last batch audit
  const accuracy = last_batch_audit?.data?.overall_accuracy;
  const assessment = last_batch_audit?.data?.model_evaluation_summary as string | undefined;

  // Determine tone: success (good accuracy), info (corrections applied), error (critical)
  let tone: "success" | "info" | "error" = "info";
  let Icon = Bell;
  if (assessment === "SATISFATORIO") {
    tone = "success";
    Icon = CheckCircle;
  } else if (assessment === "CRITICO") {
    tone = "error";
    Icon = AlertTriangle;
  } else {
    Icon = TrendingUp;
  }

  // Format timestamp
  const auditDate = last_batch_audit?.timestamp
    ? new Date(last_batch_audit.timestamp).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  // Build correction summary
  const correctionParams = cronCorrections
    .map((c) => c.parameter)
    .slice(0, 3)
    .join(", ");

  return (
    <div
      className={`st-share-feedback st-share-feedback--${tone}`}
      role="status"
      style={{ display: "flex", alignItems: "center", gap: "8px" }}
    >
      <Icon size={14} style={{ flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: "0.75rem" }}>
        <strong>Auditoria {auditDate}</strong>
        {accuracy != null && <> &mdash; Acuracia: {Number(accuracy).toFixed(1)}%</>}
        {cronCorrections.length > 0 && (
          <>
            {" "}
            &mdash; {cronCorrections.length} correcao(oes) aplicada(s)
            {correctionParams && (
              <span style={{ opacity: 0.7 }}> ({correctionParams})</span>
            )}
          </>
        )}
        {assessment && (
          <span style={{ opacity: 0.7 }}> &mdash; {assessment}</span>
        )}
      </span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        style={{
          background: "none",
          border: "none",
          color: "inherit",
          cursor: "pointer",
          padding: "2px",
          opacity: 0.6,
          flexShrink: 0,
        }}
        aria-label="Fechar"
      >
        <X size={14} />
      </button>
    </div>
  );
}
