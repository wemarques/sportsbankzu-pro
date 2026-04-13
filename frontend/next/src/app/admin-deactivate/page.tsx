"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminDeactivatePage() {
  const router = useRouter();

  useEffect(() => {
    localStorage.removeItem("sbz_admin_token");
    setTimeout(() => router.push("/dashboard"), 1000);
  }, [router]);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a0a" }}>
      <div style={{ textAlign: "center", padding: 32 }}>
        <p style={{ color: "#ffd700", fontSize: 18, fontWeight: 600 }}>Admin desativado</p>
        <p style={{ color: "#888", marginTop: 8 }}>Redirecionando...</p>
      </div>
    </div>
  );
}
