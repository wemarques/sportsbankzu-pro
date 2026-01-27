import React from "react";

type Props = React.PropsWithChildren<React.HTMLAttributes<HTMLDivElement>>;

export function Card({ children, className, ...rest }: Props) {
  return <div className={`card ${className ?? ""}`} role="region" {...rest}>{children}</div>;
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

