"use client";
import { useMemo, useState, useEffect } from "react";
import BankChart from "../components/BankChart";
import ProgressBar from "../components/ProgressBar";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@radix-ui/react-accordion";
import { Plus, AlertTriangle, Cpu } from "lucide-react";
import Link from "next/link";
import { MultiLeagueSelector } from "@/components/multi-league-selector";
import { MatchesList } from "@/components/matches-list";
import type { Match } from "@/components/MatchCard";

type BetRow = { jogo: string; mercado: string; odd: number; ev: number; stake: number; confianca: "Baixa" | "Média" | "Boa" | "Alta" };

export default function Page() {
  const [banca, setBanca] = useState(80);
  const [kellyFraction, setKellyFraction] = useState(25);
  const [estrategia, setEstrategia] = useState("Moderado");
  const [limiteDiarioUsado, setLimiteDiarioUsado] = useState(0);
  const limiteDiario = useMemo(() => banca * 0.1, [banca]);
  const limitePorAposta = useMemo(() => banca * 0.05, [banca]);

  const bets: BetRow[] = [
    { jogo: "Aston Villa vs Bournemouth", mercado: "Home ML", odd: 1.9, ev: 4, stake: 8, confianca: "Média" },
    { jogo: "Crystal Palace vs Brighton", mercado: "DNB", odd: 2.15, ev: 7, stake: 10, confianca: "Boa" },
    { jogo: "Nottingham Forest vs Leeds", mercado: "Home ML", odd: 1.95, ev: 9, stake: 12, confianca: "Alta" },
  ];

  const jogosAnalisados = 148;
  const valueBets = 24;
  const stakeTotal = useMemo(() => bets.reduce((s, b) => s + b.stake, 0), [bets]);
  const evMedio = useMemo(() => (bets.reduce((s, b) => s + b.ev, 0) / bets.length), [bets]);

  const [linhaLabels, setLinhaLabels] = useState<string[]>([]);
  const [linhaReal, setLinhaReal] = useState<number[]>([]);
  const [linhaProj, setLinhaProj] = useState<number[]>([]);
  useEffect(() => {
    const labels = Array.from({ length: 30 }, (_, i) => `Dia ${i + 1}`);
    let real = [banca];
    let proj = [banca];
    for (let i = 1; i < 30; i++) {
      const deltaProj = stakeTotal * (evMedio / 100) * 0.2;
      const deltaReal = i % 5 === 0 ? -limitePorAposta * 0.5 : limitePorAposta * 0.2;
      proj.push(proj[i - 1] + deltaProj);
      real.push(real[i - 1] + deltaReal);
    }
    setLinhaLabels(labels);
    setLinhaReal(real);
    setLinhaProj(proj);
  }, [banca, stakeTotal, evMedio, limitePorAposta]);

  useEffect(() => {
    setLimiteDiarioUsado(stakeTotal);
  }, [stakeTotal]);

  const varValor = (linhaReal[linhaReal.length - 1] ?? banca) - banca;
  const varPct = (varValor / banca) * 100;
  const timestamp = new Date().toLocaleString();

  const [toasts, setToasts] = useState<string[]>([]);
  useEffect(() => {
    const alerts: string[] = [];
    if (stakeTotal > limiteDiario) alerts.push("Stake total acima do limite diário");
    if (bets.some((b) => b.stake > limitePorAposta)) alerts.push("Stake por aposta acima de 5% da banca");
    setToasts(alerts);
  }, [stakeTotal, bets, limiteDiario, limitePorAposta]);

  const [selectedLeagues, setSelectedLeagues] = useState<string[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatches, setSelectedMatches] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  async function fetchMatches() {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/matches/fetch?leagues=${encodeURIComponent(selectedLeagues.join(","))}&date=today`, { cache: "no-store" });
      const data = await response.json();
      setMatches(Array.isArray(data?.matches) ? data.matches : []);
    } catch {
      setMatches([]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 backdrop-blur bg-black/30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-6">
          <div className="text-xl font-semibold">SportsBank Pro</div>
          <div className="flex items-center gap-3">
            <span className="muted">Banca Atual:</span>
            <input
              className="card px-3 py-2 w-32 text-right outline-none"
              type="number"
              value={banca}
              onChange={(e) => setBanca(parseFloat(e.target.value || "0"))}
            />
          </div>
          <div className="ml-auto flex items-center gap-4">
            <Link
              href="/ai-audit"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#9d50ff]/10 border border-[#9d50ff]/30 text-[#9d50ff] text-sm font-semibold hover:bg-[#9d50ff]/20 transition-colors"
            >
              <Cpu size={14} />
              AI Audit
            </Link>
            <span className={"badge " + (varValor >= 0 ? "bg-primary" : "bg-red-600")}>
              {varValor >= 0 ? "+" : ""}R$ {varValor.toFixed(2)} ({varPct.toFixed(1)}%)
            </span>
            <span className="muted">Última atualização: {timestamp}</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-[320px_1fr] gap-6 px-6 py-6">
        <aside className="card p-5 h-max">
          <div className="text-lg font-semibold mb-3">Configurações de Risco</div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between mb-1"><span className="muted">Kelly Fraction</span><span>{kellyFraction}%</span></div>
              <input type="range" min={0} max={100} value={kellyFraction} onChange={(e) => setKellyFraction(parseInt(e.target.value))} className="w-full" />
            </div>
            <div>
              <div className="muted mb-1">Estratégia</div>
              <select value={estrategia} onChange={(e) => setEstrategia(e.target.value)} className="card px-3 py-2 w-full">
                <option>Conservador</option>
                <option>Moderado</option>
                <option>Agressivo</option>
              </select>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between"><span className="muted">Limite diário</span><span>R$ {limiteDiarioUsado.toFixed(2)} / R$ {limiteDiario.toFixed(2)}</span></div>
              <ProgressBar value={limiteDiarioUsado} max={limiteDiario} />
              <div className="flex justify-between"><span className="muted">Limite por aposta</span><span>R$ {limitePorAposta.toFixed(2)} (5% da banca)</span></div>
            </div>
            <button className="w-full bg-primary text-black py-2 rounded-xl shadow-soft" onClick={() => alert("Stake fixo de 2% aplicado")}>Aplicar Stake Fixo (2%)</button>
          </div>
        </aside>

        <section className="space-y-6">
          <MultiLeagueSelector
            selectedLeagues={selectedLeagues}
            onSelectionChange={setSelectedLeagues}
            onFetchMatches={fetchMatches}
            isLoading={isLoading}
          />
          <MatchesList
            matches={matches}
            selectedMatches={selectedMatches}
            onSelectMatch={(id) => {
              setSelectedMatches((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]));
            }}
            isLoading={isLoading}
          />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card p-4"><div className="muted">📊 Jogos Analisados</div><div className="text-2xl font-semibold">{jogosAnalisados}</div></div>
            <div className="card p-4"><div className="muted">✅ Value Bets</div><div className="text-2xl font-semibold">{valueBets} <span className="badge bg-primary ml-2">+16% oportunidades</span></div></div>
            <div className="card p-4"><div className="muted">💰 Stake Total</div><div className="text-2xl font-semibold">R$ {stakeTotal.toFixed(2)} <span className="badge bg-warning ml-2">⚠️ acima do recomendado</span></div></div>
            <div className="card p-4"><div className="muted">📈 EV Médio</div><div className="text-2xl font-semibold">{evMedio.toFixed(1)}% <span className="badge bg-primary ml-2">Positivo</span></div></div>
          </div>

          <div>
            <div className="text-xl mb-2">Evolução da Banca (30 dias)</div>
            <BankChart labels={linhaLabels} real={linhaReal} projected={linhaProj} />
          </div>

          <div className="card p-4">
            <div className="text-xl mb-3">Tabela de Value Bets</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left muted">
                  <tr>
                    <th className="py-2">Jogo</th><th>Mercado</th><th>Odd</th><th>EV%</th><th>Stake Sugerido</th><th>Confiança</th><th>Retorno Projetado</th>
                  </tr>
                </thead>
                <tbody>
                  {bets.map((b, i) => (
                    <tr key={i} className="border-t border-slate-700">
                      <td className="py-2">{b.jogo}</td>
                      <td>{b.mercado}</td>
                      <td>{b.odd.toFixed(2)}</td>
                      <td className={b.ev >= 0 ? "text-primary" : "text-red-500"}>{(b.ev >= 0 ? "+" : "") + b.ev}%</td>
                      <td>R$ {b.stake.toFixed(2)}</td>
                      <td>{b.confianca === "Alta" ? "🔴 Alta" : b.confianca === "Boa" ? "🟢 Boa" : b.confianca === "Média" ? "🟡 Média" : "⚪ Baixa"}</td>
                      <td>R$ {(b.stake * b.odd).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card p-4">
            <div className="text-xl mb-3">Cenários Detalhados por Jogo</div>
            <Accordion type="single" collapsible>
              <AccordionItem value="city-liverpool">
                <AccordionTrigger className="w-full py-2">Manchester City vs Liverpool</AccordionTrigger>
                <AccordionContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="card p-3">
                      <div>🔵 TUDO ACERTA</div>
                      <div className="muted">Retorno Total | Lucro | ROI</div>
                      <div>R$ 152,50 | +R$ 72,50 | +90,6%</div>
                    </div>
                    <div className="card p-3"><div>🟡 2 ACERTOS</div><div className="muted">Retorno médio</div><div>R$ 95,40</div></div>
                    <div className="card p-3"><div>🔴 1 ACERTO</div><div className="muted">Retorno médio</div><div>R$ 49,50</div></div>
                  </div>
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left muted"><tr><th>Mercado</th><th>Stake</th><th>Odd</th><th>Retorno</th><th>ROI%</th><th>Confiança</th></tr></thead>
                      <tbody>
                        <tr className="border-t border-slate-700"><td>BTTS NÃO</td><td>R$ 28,00</td><td>1.90</td><td>R$ 53,20</td><td>+4%</td><td>Média</td></tr>
                        <tr className="border-t border-slate-700"><td>Galo DNB</td><td>R$ 22,00</td><td>2.25</td><td>R$ 49,50</td><td>+7%</td><td>Boa</td></tr>
                        <tr className="border-t border-slate-700"><td>Under 10.5 escanteios</td><td>R$ 15,00</td><td>1.66</td><td>R$ 24,90</td><td>+5%</td><td>Média</td></tr>
                        <tr className="border-t border-slate-700"><td>Under 2,5 gols</td><td>R$ 15,00</td><td>1.66</td><td>R$ 24,90</td><td>+3%</td><td>Média-Alta</td></tr>
                      </tbody>
                    </table>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>

          {toasts.length > 0 && (
            <div className="fixed bottom-4 right-4 space-y-2">
              {toasts.map((t, i) => (
                <div key={i} className="card px-4 py-3 flex items-center gap-2">
                  <AlertTriangle className="text-yellow-400" size={18} />
                  <span>{t}</span>
                </div>
              ))}
            </div>
          )}

          <footer className="card p-4 flex items-center justify-between">
            <span>Status: Em análise</span>
            <span className="muted">Próxima atualização em: 00:30</span>
          </footer>

          <button className="fixed bottom-6 right-6 bg-accent text-white p-4 rounded-full shadow-soft">
            <Plus />
          </button>
        </section>
      </main>
    </div>
  );
}
