"use client";

import React from "react";

/**
 * Extract the numeric target from a corner prediction text.
 * E.g. "Escanteios Over 8.5" → 9, "Escanteios Over 9.5" → 10
 * Returns null if no corner market is detected.
 */
export function extractTargetCorners(mercado: string): number | null {
  const match = /escanteios?\s+over\s+(\d+(?:\.\d+)?)/i.exec(mercado);
  if (!match) return null;
  return Math.ceil(parseFloat(match[1]));
}

interface CornerProgressBarProps {
  currentCorners: number;
  targetCorners: number;
}

export default function CornerProgressBar({
  currentCorners,
  targetCorners,
}: CornerProgressBarProps) {
  const pct = Math.min((currentCorners / targetCorners) * 100, 100);
  const hit = currentCorners >= targetCorners;

  return (
    <div className="cpb-root">
      <div className="cpb-header">
        <span className="cpb-label">Escanteios</span>
        <span className="cpb-target">
          Meta: {targetCorners}
        </span>
      </div>

      <div className="cpb-track">
        <div
          className={`cpb-fill ${hit ? "cpb-fill--hit" : ""}`}
          style={{ width: `${pct}%` }}
        >
          <span className={`cpb-badge ${hit ? "cpb-badge--hit" : ""}`}>
            {currentCorners}
          </span>
        </div>
      </div>
    </div>
  );
}
