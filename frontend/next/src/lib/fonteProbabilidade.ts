/**
 * #234 — rótulos da fonte da probabilidade e da referência do EV (item 4 do
 * passo 4 da regra #230).
 *
 * Com `PROB_SOURCE=mercado` o backend publica, por seleção, de onde veio a
 * probabilidade (`prob_source`), o valor do modelo (`model_probability`), de
 * onde veio o EV (`ev_referencia`) e a qualidade da âncora
 * (`ancora_referencia`). Sem a flag nenhum desses campos existe e a interface
 * fica como sempre — cada helper devolve `null` para "nada a mostrar".
 */

export type ProbSource = "mercado" | "taxa_base" | "modelo_sem_referencia";

export interface EvReferencia {
  fonte: "consenso" | null;
  motivo?: "sem_odd" | "sem_consenso" | "poucas_casas";
  n_casas?: number;
  p_justa?: number;
  odd_mediana?: number | null;
  odd_max?: number | null;
}

export interface AncoraReferencia {
  metodo?: string | null;
  margem_pp?: number | null;
  frescor?: string | null;
  odd_par?: number | null;
}

export interface CamposAncora {
  prob_source?: ProbSource | string | null;
  model_probability?: number | null;
  calibrated_probability?: number | null;
  ev?: number | null;
  ev_referencia?: EvReferencia | null;
  ancora_referencia?: AncoraReferencia | null;
}

const pct = (v?: number | null): string => (v == null ? "-" : `${(v * 100).toFixed(1)}%`);

/** Pílula da fonte: rótulo curto, cor e explicação (title). `null` sem a flag. */
export function fonteProbabilidade(p: CamposAncora): { label: string; title: string; color: string } | null {
  const fonte = p.prob_source;
  if (!fonte) return null;
  const modelo = p.model_probability != null ? ` Modelo: ${pct(p.model_probability)}.` : "";
  const anc = p.ancora_referencia;
  if (fonte === "mercado") {
    const fresca = anc?.frescor === "ok";
    const margem = anc?.margem_pp != null ? ` Margem ${anc.margem_pp.toFixed(1)} pp.` : "";
    const nomeDevig = anc?.metodo ?? "de-vig";
    return {
      label: fresca ? "Mercado" : "Mercado (odd velha)",
      color: fresca ? "#4a9eff" : "#ff6b35",
      title: `Probabilidade publicada: mercado sem margem (par de odds, ${nomeDevig}).${margem}${modelo}`,
    };
  }
  if (fonte === "taxa_base") {
    return {
      label: "Taxa-base",
      color: "#a78bfa",
      title: `Sem preço em nenhuma fonte: probabilidade publicada é a taxa-base da liga neste mercado.${modelo}`,
    };
  }
  return {
    label: "Modelo",
    color: "#888",
    title: "Sem referência de mercado: probabilidade publicada é a do modelo, sem âncora.",
  };
}

/** Texto do EV (title) e o que mostrar quando não há EV. `null` sem a flag. */
export function referenciaDoEv(p: CamposAncora): { texto: string; semEv: string | null } | null {
  const r = p.ev_referencia;
  if (!r) return null;
  if (r.fonte === "consenso") {
    return {
      texto: `EV ${pct(p.ev)} contra o consenso de ${r.n_casas ?? "?"} casas (justo ${pct(r.p_justa)})`,
      semEv: null,
    };
  }
  const motivos: Record<string, string> = {
    sem_odd: "Sem odd oferecida: não há EV a calcular",
    sem_consenso: "Sem consenso entre casas: não há referência independente para o EV",
    poucas_casas: `Poucas casas no consenso (${r.n_casas ?? 0}): EV não calculado`,
  };
  return { texto: motivos[r.motivo ?? ""] ?? "EV sem referência", semEv: "EV: —" };
}

/** Reason codes do #233, no formato do REASON_META do card. */
export const REASON_META_ANCORA: Record<
  string,
  { icon: string; label: string; color: string; type: "positive" | "info" | "warning" | "danger" | "neutral" }
> = {
  ANCHOR_MARKET:      { icon: "⚓", label: "Âncora: mercado",         color: "#4a9eff", type: "info" },
  ANCHOR_STALE:       { icon: "⏳", label: "Odd velha",               color: "#ff6b35", type: "warning" },
  NO_VALUE_REFERENCE: { icon: "∅", label: "Sem referência de valor", color: "#666",    type: "neutral" },
  BASE_RATE_ONLY:     { icon: "≈", label: "Taxa-base",               color: "#a78bfa", type: "neutral" },
  MODEL_ONLY:         { icon: "○", label: "Só modelo",               color: "#888",    type: "neutral" },
};

/** Glossário dos termos novos (mesmo formato do GLOSSARY do card). */
export const GLOSSARIO_ANCORA: { term: string; description: string }[] = [
  { term: "Mercado (fonte)", description: "Probabilidade publicada a partir do par de odds sem a margem da casa (de-vig). O valor do modelo fica no detalhe." },
  { term: "Taxa-base", description: "Mercado sem preço em nenhuma fonte: a probabilidade publicada é a frequência histórica da liga neste mercado." },
  { term: "Consenso de casas", description: "Preço justo mediano entre várias casas. Sob a fonte de mercado, o EV é calculado contra ele, nunca contra a mesma odd." },
  { term: "Odd velha", description: "A margem do par de odds está fora do normal: provável linha de abertura. A âncora vale, mas não sustenta Alta Confiança." },
];
