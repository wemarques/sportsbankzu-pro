import React from "react";

type Props = React.PropsWithChildren<{
  className?: string;
}>;

export function Card({ children, className }: Props) {
  return <div className={`card ${className ?? ""}`}>{children}</div>;
}

export function CardHeader({ children }: Props) {
  return <div className="p-4 border-b border-[var(--border)]">{children}</div>;
}

export function CardContent({ children }: Props) {
  return <div className="p-4">{children}</div>;
}

export function CardFooter({ children }: Props) {
  return <div className="p-4 border-t border-[var(--border)]">{children}</div>;
}

