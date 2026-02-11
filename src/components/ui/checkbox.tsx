import React from "react";
import { cn } from "../../lib/utils";

type Props = React.InputHTMLAttributes<HTMLInputElement>;

export function Checkbox({ className, checked, ...props }: Props) {
  return (
    <input
      type="checkbox"
      data-state={checked ? "checked" : "unchecked"}
      className={cn(
        "h-4 w-4 rounded border border-[var(--border)] bg-[var(--card)] text-[var(--text)]",
        className
      )}
      checked={checked}
      {...props}
    />
  );
}

