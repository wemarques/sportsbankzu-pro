import React from "react";
import { cn } from "../../lib/utils";

type Props = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: Props) {
  return (
    <input
      className={cn(
        "w-full rounded-md border border-[var(--border)] bg-[var(--card)] text-[var(--text)] placeholder-[var(--text2)] px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--info)]",
        className
      )}
      {...props}
    />
  );
}

