"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "SPORTSBANKZU_ADM_2026";

export default function AdminActivatePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"checking" | "success" | "invalid">("checking");

  useEffect(() => {
    const token = searchParams.get("token");
    if (token === ADMIN_TOKEN) {
      localStorage.setItem("sbz_admin_token", token);
      setStatus("success");
      setTimeout(() => router.push("/dashboard"), 1500);
    } else {
      setStatus("invalid");
    }
  }, [searchParams, router]);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a0a" }}>
      <div style={{ textAlign: "center", padding: 32 }}>
        {status === "checking" && <p style={{ color: "#888" }}>Verificando token...</p>}
        {status === "success" && (
          <>
            <p style={{ color: "#00ff88", fontSize: 18, fontWeight: 600 }}>Admin ativado!</p>
            <p style={{ color: "#888", marginTop: 8 }}>Redirecionando...</p>
          </>
        )}
        {status === "invalid" && (
          <>
            <p style={{ color: "#ef4444", fontSize: 18, fontWeight: 600 }}>Token invalido</p>
            <a href="/dashboard" style={{ color: "#888", marginTop: 8, display: "block" }}>Voltar ao dashboard</a>
          </>
        )}
      </div>
    </div>
  );
}
