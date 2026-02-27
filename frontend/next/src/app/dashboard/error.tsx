"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        gap: 16,
        padding: 32,
        color: "#ccc",
        fontFamily: "sans-serif",
      }}
    >
      <h2 style={{ color: "#ff4444", fontSize: "1.2rem" }}>Ocorreu um erro inesperado</h2>
      <p style={{ fontSize: "0.85rem", color: "#888", maxWidth: 400, textAlign: "center" }}>
        Algo deu errado ao renderizar o dashboard. Tente recarregar a pagina.
      </p>
      <button
        onClick={() => reset()}
        style={{
          padding: "8px 24px",
          background: "#00ff88",
          color: "#000",
          border: "none",
          borderRadius: 6,
          fontWeight: 600,
          cursor: "pointer",
          fontSize: "0.85rem",
        }}
      >
        Tentar novamente
      </button>
      {process.env.NODE_ENV !== "production" && (
        <pre style={{ fontSize: "0.7rem", color: "#666", maxWidth: "100%", overflow: "auto", whiteSpace: "pre-wrap" }}>
          {error?.message}
        </pre>
      )}
    </div>
  );
}
