/**
 * #256 — cliente tipado dos proxies `/api/ledger/dia` e `/api/ledger/agregado`
 * (fase 1, contrato em `frontend/next/src/app/api/ledger/{dia,agregado}/route.ts`:
 * `200 { ok: true, ...payload }` ou `400|503 { ok: false, error: { kind, message } }`).
 * Nunca lança: falha de rede vira `{ ok: false, erro: { kind: "NETWORK_ERROR", ... } }`.
 */

export interface LedgerPick {
  match_id: string;
  league_id: string;
  kickoff_utc: string | null;
  familia: string;
  market: string;
  selection: string;
  published_prob: number | null;
  fair_odd: number | null;
  book_odd: number | null;
  classification: string;
  outcome: 0 | 1 | null;
  detail: string | null;
}

/** `resolvidos` (picks individuais com outcome != null) é adicionado pela
 * Task 20-bis (backend) — é o único denominador válido para "X de cada 100
 * picks": `picks` inclui não-resolvidos, `jogos` conta partidas distintas
 * (pode ser MENOR que `acertos` quando dois picks do mesmo jogo acertam). */
export interface LedgerResumo { picks: number; acertos: number; jogos: number; resolvidos: number }

export interface LedgerDia {
  data: string;
  picks: LedgerPick[];
  resumo: LedgerResumo;
  semana: Record<string, LedgerResumo>;
  mes: Record<string, LedgerResumo>;
}

export interface LedgerSegmento { picks: number; acertos: number; n_jogos: number; resolvidos: number; brier: number | null }
export interface LedgerBucket { prob_media: number | null; freq_real: number | null; n: number }

export interface LedgerAgregado {
  periodo: string;
  familia: string | null;
  liga: string | null;
  acerto: { picks: number; acertos: number; jogos: number; resolvidos: number };
  retorno: { valor: number | null; pct_banca: number | null; motivo: string | null };
  brier: number | null;
  amostra_curta: boolean;
  por_familia: Record<string, LedgerSegmento>;
  por_liga: Record<string, LedgerSegmento>;
  buckets: LedgerBucket[] | null;
}

export type ResultadoLedger<T> =
  | { ok: true; dados: T }
  | { ok: false; erro: { kind: string; message: string } };

async function chamar<T>(url: string): Promise<ResultadoLedger<T>> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    const corpo = await res.json();
    if (!corpo.ok) {
      return { ok: false, erro: corpo.error ?? { kind: "UNKNOWN", message: "falha desconhecida" } };
    }
    const { ok: _ok, ...dados } = corpo;
    return { ok: true, dados: dados as T };
  } catch {
    return { ok: false, erro: { kind: "NETWORK_ERROR", message: "sem conexão com o servidor" } };
  }
}

export function getLedgerDia(data: string): Promise<ResultadoLedger<LedgerDia>> {
  return chamar<LedgerDia>(`/api/ledger/dia?data=${encodeURIComponent(data)}`);
}

export function getLedgerAgregado(
  periodo: "7d" | "30d" | "temporada",
  familia?: string,
  liga?: string,
): Promise<ResultadoLedger<LedgerAgregado>> {
  const params = new URLSearchParams({ periodo });
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);
  return chamar<LedgerAgregado>(`/api/ledger/agregado?${params.toString()}`);
}
