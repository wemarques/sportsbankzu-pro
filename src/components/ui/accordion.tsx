import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";
import React from "react";

export function Accordion({
  children,
  type = "single",
  collapsible = true,
  className,
}: {
  children: React.ReactNode;
  type?: "single" | "multiple";
  collapsible?: boolean;
  className?: string;
}) {
  return (
    <AccordionPrimitive.Root type={type} collapsible={collapsible} className={className}>
      {children}
    </AccordionPrimitive.Root>
  );
}

export function AccordionItem({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <AccordionPrimitive.Item value={value} className={className}>
      {children}
    </AccordionPrimitive.Item>
  );
}

export function AccordionTrigger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <AccordionPrimitive.Header className="w-full">
      <AccordionPrimitive.Trigger
        className={`w-full flex items-center justify-between px-4 py-3 border border-[var(--border)] rounded-md bg-[var(--card)] ${className ?? ""}`}
      >
        {children}
        <ChevronDown className="h-4 w-4 shrink-0 transition-transform data-[state=open]:rotate-180" />
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  );
}

export function AccordionContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <AccordionPrimitive.Content
      className={`overflow-hidden data-[state=open]:animate-slideDown data-[state=closed]:animate-slideUp ${className ?? ""}`}
    >
      <div className="p-4 border border-[var(--border)] rounded-md bg-[var(--card)] mt-2">{children}</div>
    </AccordionPrimitive.Content>
  );
}

