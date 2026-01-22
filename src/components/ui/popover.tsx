import React, { createContext, useContext, useMemo } from "react";

type PopoverContextType = {
  open: boolean;
  setOpen: (v: boolean) => void;
};

const PopoverCtx = createContext<PopoverContextType | null>(null);

export function Popover({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  children: React.ReactNode;
}) {
  const value = useMemo(() => ({ open, setOpen: onOpenChange }), [open, onOpenChange]);
  return (
    <PopoverCtx.Provider value={value}>
      <div className="relative inline-block">{children}</div>
    </PopoverCtx.Provider>
  );
}

export function PopoverTrigger({
  asChild,
  children,
}: {
  asChild?: boolean;
  children: React.ReactElement;
}) {
  const ctx = useContext(PopoverCtx);
  if (!ctx) return children;
  const props = {
    onClick: () => ctx.setOpen(!ctx.open),
  };
  return asChild ? React.cloneElement(children, props) : <button {...props}>{children}</button>;
}

export function PopoverContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ctx = useContext(PopoverCtx);
  if (!ctx || !ctx.open) return null;
  return (
    <div
      className={`absolute z-50 mt-2 rounded-md border border-[var(--border)] shadow-soft ${className ?? ""}`}
      style={{ minWidth: "12rem" }}
    >
      {children}
    </div>
  );
}

