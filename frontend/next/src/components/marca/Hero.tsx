"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getLedgerAgregado, getLedgerDia } from "@/lib/ledgerApi";
import { getMatchesByLeague } from "@/lib/api";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import { diaISOOntem } from "@/lib/feedUrl";
import { ACTIVE_LEAGUES, toBackendLeagueId, type Match } from "@/lib/leagues";
import { fraseAcertoHero, HERO } from "@/lib/copy";
import { CardJogo } from "@/components/feed/CardJogo";
import { fonteMarca } from "@/components/marca/fonteMarca";

const MIN_N_HERO = 20; // mesmo piso do backend, MIN_N_BRIER (#079)

export function Hero() {
  const [frase, setFrase] = useState<string | null>(null);
  const [jogoProva, setJogoProva] = useState<JogoView | null>(null);
  const [semProva, setSemProva] = useState(false);

  useEffect(() => {
    let vivo = true;
    const ligas = ACTIVE_LEAGUES().map((l) => ({ id: toBackendLeagueId(l.id), nome: l.name }));

    getLedgerAgregado("30d").then((r) => {
      if (!vivo || !r.ok) return;
      const { acertos, jogos, resolvidos } = r.dados.acerto;
      setFrase(fraseAcertoHero(acertos, resolvidos, jogos, MIN_N_HERO));
    }).catch(() => {});

    getMatchesByLeague(ligas.map((l) => l.id).join(","), "today").then(async (res) => {
      if (!vivo) return;
      const agora = new Date();
      const views = deduplicateMatches(
        (res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)),
      ).map((m: Match) => toJogoView(m, agora));
      // spec §5: o talão-prova é o de MAIOR edge de hoje; empate, maior chance
      const doHoje = views.filter((v) => v.talao)
        .sort((a, b) => (b.talao!.edge ?? -Infinity) - (a.talao!.edge ?? -Infinity) || b.talao!.prob01 - a.talao!.prob01)[0];
      if (doHoje) { setJogoProva(doHoje); return; }

      // #257: sem talao hoje — cai para o de ONTEM, so o que foi publicado no
      // ledger (nunca /fixtures para dia passado — fonte unica, spec §6.3).
      const rOntem = await getLedgerDia(diaISOOntem(new Date()));
      if (!vivo) return;
      if (!rOntem.ok) { setSemProva(true); return; }
      const porJogo = agruparPorJogo(rOntem.dados.picks);
      let achado: JogoView | null = null;
      for (const [matchId, picksDoJogo] of Array.from(porJogo)) {
        const leagueId = picksDoJogo[0].league_id;
        const liga = ligas.find((l) => l.id === leagueId);
        const view = toJogoViewOntem(matchId, liga?.id ?? leagueId, liga?.nome ?? leagueId, picksDoJogo);
        if (view.estado === "ontem" && view.talao) { achado = view; break; }
      }
      if (achado) setJogoProva(achado); else setSemProva(true);
    }).catch(() => { if (vivo) setSemProva(true); });

    return () => { vivo = false; };
  }, []);

  return (
    <section className="mx-auto flex min-h-screen max-w-[720px] flex-col items-center justify-center gap-6 px-4 text-center text-[var(--sb-texto)]">
      <h1 className={`${fonteMarca.className} text-[36px] font-bold leading-tight`}>
        {HERO.headlineLinha1}
        <br />{HERO.headlineLinha2}
      </h1>
      {frase && <p className="tnum text-[16px] text-[var(--sb-texto-apagado)]">{frase}</p>}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/jogos" className="sb-foco rounded-[var(--sb-raio-painel)] border border-[var(--sb-texto)] px-5 py-2.5 text-[16px] font-semibold">
          {HERO.ctaJogos}
        </Link>
        <Link href="/login" className="sb-foco text-[14px] underline">{HERO.ctaEntrar}</Link>
        <Link href="/register" className="sb-foco text-[14px] underline">{HERO.ctaCriarConta}</Link>
      </div>
      {jogoProva && (
        <div className="w-full max-w-[420px] text-left">
          <CardJogo jogo={jogoProva} confianca={null} selecionado={false}
            hrefDetalhe={`/jogos/${encodeURIComponent(jogoProva.id)}`} media={null} />
        </div>
      )}
      {!jogoProva && semProva && <p className="text-[13px] text-[var(--sb-texto-apagado)]">{HERO.semTalao}</p>}
    </section>
  );
}
