"use client";

import React from "react";

/**
 * Extract the numeric target and direction from a corner prediction text.
 * E.g. "Escanteios Over 8.5" → { target: 9, direction: "over" }
 *      "Escanteios Under 9.5" → { target: 9, direction: "under" }
 * Returns null if no corner market is detected.
 */
export function extractTargetCorners(
  mercado: string,
): { target: number; direction: "over" | "under" } | null {
  const overMatch = /escanteios?\s+over\s+(\d+(?:\.\d+)?)/i.exec(mercado);
  if (overMatch) return { target: Math.ceil(parseFloat(overMatch[1])), direction: "over" };

  const underMatch = /escanteios?\s+under\s+(\d+(?:\.\d+)?)/i.exec(mercado);
  if (underMatch) return { target: Math.floor(parseFloat(underMatch[1])), direction: "under" };

  return null;
}

interface CornerProgressBarProps {
  currentCorners: number;
  targetCorners: number;
  direction: "over" | "under";
}

export default function CornerProgressBar({
  currentCorners,
  targetCorners,
  direction,
}: CornerProgressBarProps) {
  const pct = Math.min((currentCorners / targetCorners) * 100, 100);
  const hit = currentCorners >= targetCorners;
  const isGood = direction === "over" ? hit : !hit;

  return (
    <div className="cpb-root">
      <div className="cpb-header">
        <span className="cpb-label">Escanteios</span>
        <span className="cpb-target">
          {direction === "over" ? "Meta" : "Limite"}: {targetCorners}
        </span>
      </div>

      <div className="cpb-track">
        <div
          className={`cpb-fill ${isGood ? "cpb-fill--hit" : hit ? "cpb-fill--danger" : ""}`}
          style={{ width: `${pct}%` }}
        >
          <span className={`cpb-badge ${isGood ? "cpb-badge--hit" : hit ? "cpb-badge--danger" : ""}`}>
            {currentCorners}
          </span>
        </div>
      </div>
    </div>
  );
}
