"use client";
import { useSession } from "next-auth/react";

export type UserRole = "free" | "plus" | "admin";

export function useRole() {
  const { data: session, status } = useSession();
  // TODO #136: reativar quando RDS aceitar conexão do Vercel
  // Bypass temporário — sem login, tratar como admin para mostrar tudo
  const role = ((session?.user as any)?.role || "admin") as UserRole;
  const isAuthenticated = status === "authenticated" || true;

  return {
    role,
    isAdmin: role === "admin",
    isPlus: role === "plus" || role === "admin",
    isFree: role === "free",
    isAuthenticated,
    canSeeEV: role !== "free",
    canSeeValorDetectado: role !== "free",
    canSeeDestaques: role !== "free",
    canSeeDuplas: role !== "free",
    canSeeMistral: role !== "free",
    canSeeDirecao: role !== "free",
    canCopyWhatsApp: role !== "free",
    canSeeAudit: role === "admin",
    canSeeConfiabilidade: role === "admin",
    canSeeReasonCodes: role === "admin",
    canSeeFerramentas: role === "admin",
    canRegenMistral: role === "admin",
    canManageLeagues: role === "admin",
    maxLeagues: role === "free" ? 2 : 999,
  };
}
