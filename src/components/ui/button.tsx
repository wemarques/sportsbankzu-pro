import React from "react";
import { cn } from "../../lib/utils";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "success" | "warning" | "danger" | "ghost";
};

export function Button({ className, variant = "default", ...props }: Props) {
  const base =
    "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none h-9 px-4 py-2";
  const styles: Record<string, string> = {
    default:
      "bg-[var(--info)] text-white hover:brightness-110 focus-visible:ring-[var(--info)] ring-offset-[var(--card)]",
    success:
      "bg-[var(--primary)] text-black hover:brightness-110 focus-visible:ring-[var(--primary)] ring-offset-[var(--card)]",
    warning:
      "bg-[var(--warning)] text-black hover:brightness-110 focus-visible:ring-[var(--warning)] ring-offset-[var(--card)]",
    danger:
      "bg-[var(--danger)] text-white hover:brightness-110 focus-visible:ring-[var(--danger)] ring-offset-[var(--card)]",
    ghost:
      "bg-transparent border border-[var(--border)] text-[var(--text)] hover:bg-[var(--card)]",
  };
  return <button className={cn(base, styles[variant], className)} {...props} />;
}

