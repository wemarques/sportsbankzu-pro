"use client";
import { useEffect, useMemo, useState } from "react";
// Removendo imports quebrados e mantendo apenas estrutura visual
// import { getSystemStatus, refreshSource } from "../lib/api";
import { BadgeCheck, AlertTriangle, XCircle, RefreshCcw } from "lucide-react";

// Mock temporário até o backend implementar endpoints de saúde detalhados
const MOCK_STATUS = {
  data_sources: {
    footystats: { available: true, url: "https://api.footystats.org", type: "scraper" },
    database: { available: true, path: "/data/sportsbank", type: "local_file" }
  }
};

type StatusItem = {
  source_name: string;
  source_type: string;
  source_url: string;
  last_attempt_timestamp: number;
  status: "success" | "failed" | "skipped";
  error_message?: string;
  is_cached: boolean;
  cache_age_seconds: number;
  ttl_seconds: number;
  data_path: string;
};

export default function SystemStatus({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [items, setItems] = useState<StatusItem[]>([]);
  const [pending, setPending] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const fmtTime = useMemo(() => (ts: number) => {
    try { return new Date(ts * 1000).toLocaleString("pt-BR"); } catch { return "-"; }
  }, []);
  const fmtAge = useMemo(() => (s: number) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  }, []);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    // Simulação de carregamento
    setTimeout(() => {
        const ds = MOCK_STATUS.data_sources;
        const listKeys = Object.keys(ds);
        const list: StatusItem[] = listKeys.map((k) => {
          // @ts-ignore
          const v = ds[k] || {};
          return {
            source_name: k,
            source_type: v.type || "unknown",
            source_url: v.url || "",
            last_attempt_timestamp: Math.floor(Date.now() / 1000),
            status: "success",
            is_cached: false,
            cache_age_seconds: 0,
            ttl_seconds: 3600,
            data_path: v.path || "",
          };
        });
        setItems(list);
        setLoading(false);
    }, 500);
  }, [open]);

  async function onRefresh(source: string) {
    // Placeholder para futura implementação
    console.log("Refresh solicitado para:", source);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="card w-full max-w-3xl p-4 bg-[var(--card)] border border-[var(--border)] rounded-lg shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xl font-bold">Status do Sistema</div>
          <button onClick={onClose} className="px-3 py-1.5 text-sm bg-[var(--secondary)] hover:bg-[var(--muted)] border border-[var(--border)] rounded transition-colors">Fechar</button>
        </div>
        
        <div className="mt-3">
          {loading ? (
            <div className="text-center py-8 muted">Verificando conexões...</div>
          ) : items.length ? (
            <div className="space-y-3">
              {items.map((it, idx) => (
                  <div key={idx} className="p-3 border border-[var(--border)] rounded-md bg-[var(--background)]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <BadgeCheck className="w-5 h-5 text-[var(--primary)]" />
                        <div>
                          <div className="font-semibold capitalize">{it.source_name}</div>
                          <div className="muted text-xs">{it.source_type} • {it.source_url || "Local"}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => onRefresh(it.source_name)} className="px-2 py-1 text-xs bg-[var(--secondary)] border border-[var(--border)] rounded flex items-center gap-1 hover:bg-[var(--muted)]">
                          <RefreshCcw className="w-3 h-3" /> Verificar
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs muted">
                      <div className="bg-[var(--secondary)]/50 rounded px-2 py-1">Última verificação: {fmtTime(it.last_attempt_timestamp)}</div>
                      <div className="bg-[var(--secondary)]/50 rounded px-2 py-1">Status: Operacional</div>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="muted text-center py-4">Sem status disponíveis.</div>
          )}
        </div>
      </div>
    </div>
  );
}
