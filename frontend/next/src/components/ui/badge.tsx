import React from "react";
import { cn } from "../../lib/utils";

type Props = React.PropsWithChildren<{
  variant?: "success" | "warning" | "danger" | "default" | "outline";
  className?: string;
}>;

export function Badge({ children, variant = "default", className }: Props) {
  const map: Record<string, string> = {
    success: "bg-[var(--primary)] text-black",
    warning: "bg-[var(--warning)] text-black",
    danger: "bg-[var(--danger)] text-white",
    default: "bg-[var(--card)] text-[var(--text)] border border-[var(--border)]",
    outline: "bg-transparent text-[var(--text)] border border-[var(--border)]",
  };
  return <span className={cn("badge", map[variant], className)}>{children}</span>;
}

