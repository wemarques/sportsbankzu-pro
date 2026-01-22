import React, { createContext, useContext, useMemo } from "react";
import { cn } from "../../lib/utils";

type TabsCtxType = {
  value: string;
  setValue: (v: string) => void;
};

const TabsCtx = createContext<TabsCtxType | null>(null);

export function Tabs({
  value,
  onValueChange,
  children,
}: {
  value: string;
  onValueChange: (v: string) => void;
  children: React.ReactNode;
}) {
  const ctx = useMemo(() => ({ value, setValue: onValueChange }), [value, onValueChange]);
  return <TabsCtx.Provider value={ctx}>{children}</TabsCtx.Provider>;
}

export function TabsList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--card)] p-1 gap-1",
        className
      )}
    >
      {children}
    </div>
  );
}

export function TabsTrigger({
  value,
  children,
}: {
  value: string;
  children: React.ReactNode;
}) {
  const ctx = useContext(TabsCtx);
  if (!ctx) return <button>{children}</button>;
  const active = ctx.value === value;
  return (
    <button
      onClick={() => ctx.setValue(value)}
      className={cn(
        "px-3 py-1 text-sm rounded-md",
        active
          ? "bg-[var(--accent)] text-white"
          : "bg-transparent text-[var(--text)] hover:bg-[var(--card)]"
      )}
    >
      {children}
    </button>
  );
}

