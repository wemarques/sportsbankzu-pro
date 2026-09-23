"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getMatchesByLeague } from "@/lib/api";
import { ACTIVE_LEAGUES, toBackendLeagueId, type Match } from "@/lib/leagues";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { useLeagueClassifications } from "@/hooks/useLeagueClassifications";
import { type Dia } from "@/lib/feedUrl";
import { VAZIOS, CARREGANDO } from "@/lib/copy";
import { Detalhe } from "@/components/detalhe/Detalhe";
import { EsqueletoDetalhe } from "@/components/detalhe/EsqueletoDetalhe";

const DIAS_API = ["today", "tomorrow"] as const;

/**
 * #254-b — celular abre o detalhe em pagina cheia (spec §3). Sem cache
 * proprio: mesma chamada do feed (`getMatchesByLeague`), procurando o `id`
 * primeiro no dia de hoje e depois em amanha.
 */
function DetalhePagina() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(String(params?.id ?? ""));
  const confianca = useLeagueClassifications();
  const [jogo, setJogo] = useState<JogoView | null>(null);
  const [carregando, setCarregando] = useState(true);
  // #262 fix wave (round 2) — dia (chave da API) que o loop DIAS_API esta
  // buscando no momento; o rotulo pt-BR e derivado abaixo, antes do return.
  const [diaAtualApi, setDiaAtualApi] = useState<(typeof DIAS_API)[number]>("today");

  useEffect(() => {
    let vivo = true;
    if (!id) { setCarregando(false); return; }
    const ligas = ACTIVE_LEAGUES().map((l) => toBackendLeagueId(l.id)).join(",");

    async function carregar() {
      setCarregando(true);
      for (const date of DIAS_API) {
        if (!vivo) return;
        setDiaAtualApi(date);
        try {
          const res = await getMatchesByLeague(ligas, date);
          if (!vivo) return;
          const agora = new Date();
          const views = deduplicateMatches((res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)))
            .map((m: Match) => toJogoView(m, agora));
          const achado = views.find((v) => v.id === id);
          if (achado) { setJogo(achado); setCarregando(false); return; }
        } catch {
          // segue tentando o proximo dia
        }
      }
      if (vivo) { setJogo(null); setCarregando(false); }
    }
    carregar();
    return () => { vivo = false; };
  }, [id]);

  // #262 fix wave (round 2) — "amanha" e valor do tipo Dia, nao texto exibido:
  // esta na allowlist do lint:accents (app/jogos/[id]/page.tsx:amanha), como
  // as demais ocorrencias do mesmo padrao em lib/feedUrl.ts e DiaTabs.tsx.
  const diaAtual: Dia = diaAtualApi === "today" ? "hoje" : "amanha";

  if (carregando) {
    return (
      <div className="mx-auto max-w-[700px] px-4 py-4" aria-busy="true">
        <p role="status" className="sr-only">{CARREGANDO.buscando(diaAtual)}</p>
        <EsqueletoDetalhe />
      </div>
    );
  }

  if (!jogo) {
    return (
      <div className="mx-auto max-w-[700px] px-4 py-8 text-[var(--sb-texto)]">
        <p className="text-[14px]">{VAZIOS.jogoNaoEncontrado}</p>
        <Link href="/jogos" className="sb-foco underline">{VAZIOS.verFeedDeHoje}</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[700px] px-4 py-4">
      <p className="pb-3 text-[14px]"><Link href="/jogos" className="sb-foco underline">{VAZIOS.verFeedDeHoje}</Link></p>
      <Detalhe jogo={jogo} confianca={confianca.get(jogo.ligaId)} />
    </div>
  );
}

export default function Page() {
  return <main className="min-h-[calc(100vh-56px)] bg-[var(--sb-tinta)]"><DetalhePagina /></main>;
}
