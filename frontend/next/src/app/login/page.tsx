"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await signIn("credentials", { email, password, redirect: false });
    setLoading(false);
    if (result?.error) {
      setError("Email ou senha incorretos");
    } else {
      router.push("/dashboard");
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a0a" }}>
      <div style={{ width: "100%", maxWidth: 400, padding: 32, background: "#1a1a1a", borderRadius: 12, border: "1px solid #333" }}>
        <h1 style={{ textAlign: "center", color: "#fff", marginBottom: 8 }}>SportsBankZu Pro</h1>
        <p style={{ textAlign: "center", color: "#888", marginBottom: 24, fontSize: 14 }}>Acesse sua conta</p>
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: "#aaa", fontSize: 13, marginBottom: 4, display: "block" }}>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              style={{ width: "100%", padding: "10px 12px", background: "#0d0d0d", border: "1px solid #333", borderRadius: 8, color: "#fff", fontSize: 14, outline: "none" }}
              placeholder="seu@email.com" />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: "#aaa", fontSize: 13, marginBottom: 4, display: "block" }}>Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              style={{ width: "100%", padding: "10px 12px", background: "#0d0d0d", border: "1px solid #333", borderRadius: 8, color: "#fff", fontSize: 14, outline: "none" }}
              placeholder="******" />
          </div>
          {error && <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button type="submit" disabled={loading}
            style={{ width: "100%", padding: "10px 0", background: loading ? "#333" : "#00ff88", color: "#000", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer" }}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
        <p style={{ textAlign: "center", color: "#666", fontSize: 13, marginTop: 16 }}>
          Não tem conta? <a href="/register" style={{ color: "#00ff88", textDecoration: "none" }}>Cadastre-se</a>
        </p>
      </div>
    </div>
  );
}
