"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

export type UserRole = "free" | "plus" | "admin";

const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "SPORTSBANKZU_ADM_2026";

export function useRole() {
  const { data: session } = useSession();
  const [deviceAdmin, setDeviceAdmin] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("sbz_admin_token");
    setDeviceAdmin(token === ADMIN_TOKEN);
  }, []);

  // Priority: session role > device token > default "plus"
  const sessionRole = (session?.user as any)?.role as UserRole | undefined;
  const role: UserRole = sessionRole || (deviceAdmin ? "admin" : "plus");
  const isAuthenticated = true; // TODO #136: usar session real quando RDS funcionar

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
