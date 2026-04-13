"use client";

interface LockedFeatureProps {
  children: React.ReactNode;
  locked: boolean;
  label?: string;
}

export default function LockedFeature({ children, locked, label = "PRO" }: LockedFeatureProps) {
  if (!locked) return <>{children}</>;
  return (
    <div style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      <div style={{ filter: "blur(4px)", pointerEvents: "none", userSelect: "none" }}>
        {children}
      </div>
      <a
        href="/upgrade"
        style={{
          position: "absolute", right: -4, top: -4,
          background: "#ffd700", color: "#000",
          fontSize: "0.6em", fontWeight: 700,
          padding: "1px 5px", borderRadius: 4,
          textDecoration: "none", cursor: "pointer",
        }}
      >
        {label}
      </a>
    </div>
  );
}
