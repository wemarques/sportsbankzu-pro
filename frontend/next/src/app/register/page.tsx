"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Erro ao cadastrar"); setLoading(false); return; }
      router.push("/login?registered=true");
    } catch { setError("Erro de conexao"); setLoading(false); }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a0a" }}>
      <div style={{ width: "100%", maxWidth: 400, padding: 32, background: "#1a1a1a", borderRadius: 12, border: "1px solid #333" }}>
        <h1 style={{ textAlign: "center", color: "#fff", marginBottom: 8 }}>SportsBankZu Pro</h1>
        <p style={{ textAlign: "center", color: "#888", marginBottom: 24, fontSize: 14 }}>Criar conta gratuita</p>
        <form onSubmit={handleRegister}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: "#aaa", fontSize: 13, marginBottom: 4, display: "block" }}>Nome</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required
              style={{ width: "100%", padding: "10px 12px", background: "#0d0d0d", border: "1px solid #333", borderRadius: 8, color: "#fff", fontSize: 14, outline: "none" }}
              placeholder="Seu nome" />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: "#aaa", fontSize: 13, marginBottom: 4, display: "block" }}>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              style={{ width: "100%", padding: "10px 12px", background: "#0d0d0d", border: "1px solid #333", borderRadius: 8, color: "#fff", fontSize: 14, outline: "none" }}
              placeholder="seu@email.com" />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: "#aaa", fontSize: 13, marginBottom: 4, display: "block" }}>Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
              style={{ width: "100%", padding: "10px 12px", background: "#0d0d0d", border: "1px solid #333", borderRadius: 8, color: "#fff", fontSize: 14, outline: "none" }}
              placeholder="Minimo 6 caracteres" />
          </div>
          {error && <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button type="submit" disabled={loading}
            style={{ width: "100%", padding: "10px 0", background: loading ? "#333" : "#00ff88", color: "#000", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer" }}>
            {loading ? "Cadastrando..." : "Criar conta"}
          </button>
        </form>
        <p style={{ textAlign: "center", color: "#666", fontSize: 13, marginTop: 16 }}>
          Ja tem conta? <a href="/login" style={{ color: "#00ff88", textDecoration: "none" }}>Entrar</a>
        </p>
      </div>
    </div>
  );
}
