import React from "react";
import { cn } from "../../lib/utils";

type Props = {
  value: number;
  className?: string;
  color?: "success" | "warning" | "danger" | "info" | "accent";
};

export function Progress({ value, className, color = "info" }: Props) {
  const colorMap: Record<string, string> = {
    success: "bg-[var(--primary)]",
    warning: "bg-[var(--warning)]",
    danger: "bg-[var(--danger)]",
    info: "bg-[var(--info)]",
    accent: "bg-[var(--accent)]",
  };
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("w-full h-2 rounded-full bg-[#1f2937]", className)}>
      <div
        className={cn("h-2 rounded-full", colorMap[color])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

