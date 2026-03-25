"use client";

import React, { useState, useRef, useEffect } from "react";
import { getClassificationDisplay } from "@/lib/classifications";

interface ClassificationBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export default function ClassificationBadge({ status, size = "sm" }: ClassificationBadgeProps) {
  const display = getClassificationDisplay(status);
  const [showTooltip, setShowTooltip] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const badgeRef = useRef<HTMLSpanElement>(null);

  function handleEnter() {
    timerRef.current = setTimeout(() => setShowTooltip(true), 300);
  }

  function handleLeave() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setShowTooltip(false);
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const fontSize = size === "sm" ? "0.6rem" : "0.7rem";
  const padding = size === "sm" ? "2px 6px" : "3px 8px";

  return (
    <span
      ref={badgeRef}
      className="classification-badge"
      style={{
        fontSize,
        fontWeight: 900,
        textTransform: "uppercase",
        letterSpacing: "0.5px",
        padding,
        borderRadius: 3,
        background: display.bgColor,
        color: display.color,
        cursor: "help",
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        whiteSpace: "nowrap",
      }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {display.label}
      {showTooltip && (
        <span className="classification-tooltip">
          <strong style={{ display: "block", marginBottom: 4, fontSize: "0.75rem" }}>
            {display.label}
          </strong>
          <span style={{ opacity: 0.85, lineHeight: 1.4 }}>
            {display.tooltip}
          </span>
        </span>
      )}
    </span>
  );
}
