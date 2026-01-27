"use client";
import { useEffect, useMemo, useState } from "react";
import { getSystemStatus, refreshSource } from "../lib/api";
import { BadgeCheck, AlertTriangle, XCircle, RefreshCcw } from "lucide-react";

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
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const res = await getSystemStatus();
        const ds = res?.data_sources || {};
        const cache = res?.cache || {};
        const ttlMatches = Number(cache?.ttl_matches) || 0;
        const ttlVB = Number(cache?.ttl_value_bets) || 0;
        const order: Record<string, number> = { csv: 4, odds_api: 3, whoscored: 2, footystats: 1 };
        const list: StatusItem[] = Object.keys(ds).map((k) => {
          const v = ds[k] || {};
          const type = k === "csv" ? "local_file" : k === "odds_api" ? "http_api" : "scraper";
          const ok = !!v.available;
          const blocked = !!v.blocked;
          const status: "success" | "failed" | "skipped" = ok ? "success" : "failed";
          return {
            source_name: k,
            source_type: type,
            source_url: v.url || "",
            last_attempt_timestamp: Math.floor(Date.now() / 1000),
            status,
            error_message: blocked ? "Bloqueado" : undefined,
            is_cached: false,
            cache_age_seconds: 0,
            ttl_seconds: k === "odds_api" ? ttlVB : ttlMatches,
            data_path: v.path || "",
          };
        }).sort((a,b) => (order[b.source_name] ?? 0) - (order[a.source_name] ?? 0));
        const pend = res?.pending ?? [];
        if (active) { setItems(list ?? []); setPending(pend ?? []); }
      } catch {
        if (active) { setItems([]); setPending([]); }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [open]);

  async function onRefresh(source: string) {
    try {
      await refreshSource(source);
      const res = await getSystemStatus();
      const ds = res?.data_sources || {};
      const cache = res?.cache || {};
      const ttlMatches = Number(cache?.ttl_matches) || 0;
      const ttlVB = Number(cache?.ttl_value_bets) || 0;
      const order: Record<string, number> = { csv: 4, odds_api: 3, whoscored: 2, footystats: 1 };
      const list: StatusItem[] = Object.keys(ds).map((k) => {
        const v = ds[k] || {};
        const type = k === "csv" ? "local_file" : k === "odds_api" ? "http_api" : "scraper";
        const ok = !!v.available;
        const blocked = !!v.blocked;
        const status: "success" | "failed" | "skipped" = ok ? "success" : "failed";
        return {
          source_name: k,
          source_type: type,
          source_url: v.url || "",
          last_attempt_timestamp: Math.floor(Date.now() / 1000),
          status,
          error_message: blocked ? "Bloqueado" : undefined,
          is_cached: false,
          cache_age_seconds: 0,
          ttl_seconds: k === "odds_api" ? ttlVB : ttlMatches,
          data_path: v.path || "",
        };
      }).sort((a,b) => (order[b.source_name] ?? 0) - (order[a.source_name] ?? 0));
      const pend = res?.pending ?? [];
      setItems(list ?? []);
      setPending(pend ?? []);
    } catch {}
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="card w-full max-w-3xl p-4">
        <div className="flex items-center justify-between">
          <div className="text-xl">Status do Sistema e Fontes de Dados</div>
          <button onClick={onClose} className="px-3 py-2 bg-[var(--card)] border border-[var(--border)] rounded-md">Fechar</button>
        </div>
        <div className="mt-3">
          {loading ? (
            <div className="muted">Carregando...</div>
          ) : items.length ? (
            <div className="space-y-3">
              {items.map((it, idx) => {
                const okOnline = it.status === "success" && !it.is_cached;
                const okCached = it.status === "success" && it.is_cached;
                const failed = it.status === "failed";
                return (
                  <div key={idx} className="p-3 border border-[var(--border)] rounded-md bg-[var(--bg)]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {okOnline && <BadgeCheck className="w-5 h-5 text-[var(--primary)]" />}
                        {okCached && <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />}
                        {failed && <XCircle className="w-5 h-5 text-[var(--danger)]" />}
                        <div>
                          <div className="font-semibold">{it.source_name}</div>
                          <div className="muted text-xs">{it.source_type} • {it.source_url}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => onRefresh(it.source_name)} className="px-2 py-1 text-xs bg-[var(--card)] border border-[var(--border)] rounded flex items-center gap-1">
                          <RefreshCcw className="w-3 h-3" /> Atualizar agora
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Última tentativa: {fmtTime(it.last_attempt_timestamp)}</div>
                      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Cache: {it.is_cached ? `Sim (${fmtAge(it.cache_age_seconds)})` : "Não"}</div>
                      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">TTL: {it.ttl_seconds}s</div>
                      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Arquivo: {it.data_path}</div>
                    </div>
                    {it.error_message && <div className="mt-2 text-[var(--danger)] text-sm">{it.error_message}</div>}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="muted">Sem status disponíveis.</div>
          )}
        </div>
        <div className="mt-4">
          <div className="text-sm font-semibold">Itens Pendentes/Planejados</div>
          {pending?.length ? (
            <ul className="list-disc pl-5 text-sm mt-1">
              {pending.map((p, i) => (<li key={i} className="muted">{p}</li>))}
            </ul>
          ) : (
            <div className="muted text-sm">Nenhum item pendente informado.</div>
          )}
        </div>
      </div>
    </div>
  );
}
