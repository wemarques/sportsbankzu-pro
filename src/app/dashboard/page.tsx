"use client";
import { useEffect, useMemo, useState } from "react";
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import * as Accordion from "@radix-ui/react-accordion";
import { BarChart3, Settings, BadgeCheck, ActivitySquare } from "lucide-react";
import MatchesList from "../../components/MatchList";
import { AVAILABLE_LEAGUES, Match } from "../../lib/leagues";
import { getMatchesByLeague, getValueBetsByLeague } from "../../lib/api";
import SystemStatus from "../../components/SystemStatus";

function DashboardJogos({ dataJogos }: { dataJogos: { liga: string; time_casa: string; time_fora: string; data_hora: string; estadio: string; status: string; }[] }) {
  const initialDate = dataJogos?.[0]?.data_hora?.substring(0, 10) ?? new Date().toISOString().substring(0, 10);
  const [dataSelecionada, setDataSelecionada] = useState(initialDate);
  const datasDisponiveis = useMemo(() => {
    const datas = dataJogos.map((j) => j.data_hora.substring(0, 10));
    return Array.from(new Set(datas)).sort();
  }, [dataJogos]);
  const jogosFiltrados = useMemo(() => {
    if (!dataSelecionada) return dataJogos;
    return dataJogos.filter((j) => j.data_hora.startsWith(dataSelecionada));
  }, [dataJogos, dataSelecionada]);

  return (
    <div>
      <div className="text-xl mb-3">Jogos da Rodada</div>
      <div className="flex items-center gap-3">
        <label htmlFor="select-data" className="muted">Selecionar Data da Rodada:</label>
        <select id="select-data" value={dataSelecionada} onChange={(e) => setDataSelecionada(e.target.value)} className="bg-transparent border border-[var(--border)] rounded-md px-3 py-2">
          {datasDisponiveis.map((data) => (
            <option key={data} value={data}>{new Date(data).toLocaleDateString("pt-BR", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</option>
          ))}
        </select>
      </div>
      <div className="my-3 border-t border-[var(--border)]" />
      <div>
        <div className="mb-2">Partidas de {new Date(dataSelecionada).toLocaleDateString("pt-BR")}</div>
        {jogosFiltrados.length ? (
          <ul className="space-y-2">
            {jogosFiltrados.map((j, idx) => (
              <li key={idx} className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-md">
                <span className="font-semibold">{j.time_casa}</span> vs <span className="font-semibold">{j.time_fora}</span> <span className="muted text-xs">({j.liga} - {new Date(j.data_hora).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })})</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="muted">Nenhum jogo agendado para a data selecionada.</div>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [banca, setBanca] = useState(1250);
  const [kelly, setKelly] = useState(0.25);
  const [estrategia, setEstrategia] = useState("Conservadora");
  const [stakeMax, setStakeMax] = useState(5);
  const [perdaMax, setPerdaMax] = useState(10);
  const [selectedLeague, setSelectedLeague] = useState<string>(AVAILABLE_LEAGUES[0].id);
  const [selectedMatches, setSelectedMatches] = useState<string[]>([]);
  const [dateFilter, setDateFilter] = useState<"today" | "tomorrow" | "week">("today");
  const [statusFilter, setStatusFilter] = useState<"all" | "scheduled" | "live" | "finished">("all");
  const [statusOpen, setStatusOpen] = useState(false);
  const [matchesData, setMatchesData] = useState<Match[]>([]);
  const [valueBetsData, setValueBetsData] = useState<any[]>([]);
  const [rodadaData, setRodadaData] = useState<{ liga: string; time_casa: string; time_fora: string; data_hora: string; estadio: string; status: string; }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatBRL = useMemo(() => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }), []);

  const cards = [
    { title: "Jogos Analisados", value: 12, icon: BarChart3 },
    { title: "Value Bets", value: 4, icon: BadgeCheck, badge: "+3 novas" },
    { title: "Stake Total", value: formatBRL.format(80), sub: `(6.4% da banca)` },
    { title: "EV Médio", value: "+4.8%" },
  ];

  const evolucao = [
    { data: "27/05", real: 1000, projecao: 1000 },
    { data: "28/05", real: 1050, projecao: 1040 },
    { data: "29/05", real: 1020, projecao: 1080 },
    { data: "30/05", real: 1150, projecao: 1120 },
    { data: "31/05", real: 1180, projecao: 1160 },
    { data: "01/06", real: 1250, projecao: 1200 },
    { data: "02/06", real: null as any, projecao: 1280 },
  ];

  const betsFlat = valueBetsData.flatMap((vb) => (vb?.bets ?? []).map((b: any) => ({ mercado: b.market, stake: b.stake_value ?? 0, odd: b.odds ?? 0, retorno: b.expected_return_value ?? 0, roi: b.roi ?? "", confianca: b.confidence ?? "" })));

  const totals = {
    retorno: 152.5,
    lucro: 72.5,
    roi: 90.6,
  };
  useEffect(() => {
    async function fetchLeagueData() {
      setLoading(true); setError(null);
      try {
        const today = new Date().toISOString().substring(0, 10);
        const matchesRes = await getMatchesByLeague(selectedLeague);
        const vbRes = await getValueBetsByLeague(selectedLeague);
        const rodadaRes = await getMatchesByLeague(selectedLeague, today);
        const normalizedMatches: Match[] = (matchesRes?.matches ?? []).map(toMatch(selectedLeague));
        setMatchesData(normalizedMatches);
        setValueBetsData(vbRes?.value_bets ?? []);
        setRodadaData((rodadaRes?.matches ?? []).map((m: any) => ({ liga: matchesRes?.league ?? AVAILABLE_LEAGUES.find(l => l.id === selectedLeague)?.name ?? selectedLeague, time_casa: m.home_team ?? m.homeTeam?.name ?? m.home ?? "Home", time_fora: m.away_team ?? m.awayTeam?.name ?? m.away ?? "Away", data_hora: m.match_date ?? m.datetime ?? today + "T00:00:00", estadio: m.venue ?? "", status: m.status ?? "scheduled" })));
      } catch (err: any) {
        setError('Não foi possível carregar os dados. Tente novamente.');
        setMatchesData([]); setValueBetsData([]); setRodadaData([]);
      } finally {
        setLoading(false);
      }
    }
    fetchLeagueData();
  }, [selectedLeague]);

  function onSelectMatch(m: Match) {
    setSelectedMatches((prev) => prev.includes(m.id) ? prev.filter((x) => x !== m.id) : [...prev, m.id]);
  }

  return (
    <div className="min-h-screen">
      <div className="fixed top-0 left-0 right-0 z-40 border-b border-[var(--border)] bg-[var(--card)]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">
          <div className="flex-1 font-semibold text-xl">SportsBank Pro</div>
          <div className="flex items-center gap-2 flex-[2]">
            <span className="muted">Banca Atual</span>
            <input
              type="number"
              value={banca}
              onChange={(e) => setBanca(Number(e.target.value))}
              className="flex-1 bg-transparent border border-[var(--border)] rounded-md px-3 py-1"
            />
            <span className="px-2 py-1 rounded-md bg-[var(--primary)] text-black">{formatBRL.format(banca)}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="relative inline-flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--primary)] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--primary)]"></span>
              </span>
              <span className="muted">Online</span>
            </div>
            <span className="badge bg-[var(--accent)] text-black">{AVAILABLE_LEAGUES.find(l=>l.id===selectedLeague)?.name ?? selectedLeague}</span>
            <button onClick={() => setStatusOpen(true)} className="px-3 py-2 bg-[var(--card)] border border-[var(--border)] rounded-md flex items-center gap-2">
              <ActivitySquare className="w-4 h-4" />
              <span className="text-sm">Status do Sistema</span>
            </button>
            <button className="px-3 py-2 bg-[var(--card)] border border-[var(--border)] rounded-md"><Settings className="w-4 h-4" /></button>
          </div>
        </div>
      </div>

      <div className="pt-20 max-w-7xl mx-auto px-6 flex gap-6">
        <div className={`${sidebarOpen ? "w-80" : "w-14"} transition-all`}>
          <div className="card p-4 h-fit">
            <div className="flex items-center justify-between">
              <div className="text-sm uppercase tracking-wide muted">Configurações de Risco</div>
              <button onClick={() => setSidebarOpen((v) => !v)} className="text-xs bg-[var(--card)] border border-[var(--border)] rounded px-2 py-1">{sidebarOpen ? "Ocultar" : "Mostrar"}</button>
            </div>
            {sidebarOpen && (
              <div className="space-y-4 mt-4">
                <div>
                  <div className="muted mb-1">Kelly Fraction</div>
                  <input type="range" min={0.1} max={1} step={0.01} value={kelly} onChange={(e) => setKelly(Number(e.target.value))} className="w-full" />
                  <div className="text-sm">{kelly.toFixed(2)}</div>
                </div>
                <div>
                  <div className="muted mb-1">Estratégia</div>
                  <select value={estrategia} onChange={(e) => setEstrategia(e.target.value)} className="w-full bg-transparent border border-[var(--border)] rounded-md px-3 py-2">
                    <option value="Conservadora">Conservadora</option>
                    <option value="Moderada">Moderada</option>
                    <option value="Agressiva">Agressiva</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="muted mb-1">Stake Máximo</div>
                    <div className="flex items-center gap-2">
                      <input type="number" value={stakeMax} onChange={(e) => setStakeMax(Number(e.target.value))} className="flex-1 bg-transparent border border-[var(--border)] rounded-md px-3 py-2" />
                      <span className="muted">%</span>
                    </div>
                  </div>
                  <div>
                    <div className="muted mb-1">Perda Máxima</div>
                    <div className="flex items-center gap-2">
                      <input type="number" value={perdaMax} onChange={(e) => setPerdaMax(Number(e.target.value))} className="flex-1 bg-transparent border border-[var(--border)] rounded-md px-3 py-2" />
                      <span className="muted">%</span>
                    </div>
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Apostas hoje: 4</div>
                  <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Lucro: {formatBRL.format(72.5)}</div>
                  <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">ROI: +90.6%</div>
                  <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-2">Stake usada: 6.4%</div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {cards.map((c, i) => (
              <div key={i} className="card p-4">
                <div className="flex items-center justify-between">
                  <div className="muted">{c.title}</div>
                  {c.icon && <c.icon className="w-5 h-5 text-[var(--info)]" />}
                </div>
                <div className="text-2xl font-semibold mt-1">{c.value}</div>
                {c.sub && <div className="muted text-sm mt-1">{c.sub}</div>}
                {c.badge && <span className="badge bg-[var(--primary)] text-black mt-2 inline-block">{c.badge}</span>}
              </div>
            ))}
          </div>

          <div className="card p-4">
            <div className="text-xl mb-3">Seleção de Ligas e Jogos</div>
            <div className="flex items-center gap-3">
              <select value={selectedLeague} onChange={(e) => setSelectedLeague(e.target.value)} className="bg-transparent border border-[var(--border)] rounded-md px-3 py-2">
                {AVAILABLE_LEAGUES.map((l) => (<option key={l.id} value={l.id}>{l.name}</option>))}
              </select>
            </div>
            <div className="mt-4 flex gap-3">
              <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value as any)} className="bg-transparent border border-[var(--border)] rounded-md px-3 py-2">
                <option value="today">Hoje</option>
                <option value="tomorrow">Amanhã</option>
                <option value="week">Semana</option>
              </select>
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)} className="bg-transparent border border-[var(--border)] rounded-md px-3 py-2">
                <option value="all">Todos</option>
                <option value="scheduled">Agendados</option>
                <option value="live">Ao vivo</option>
                <option value="finished">Encerrados</option>
              </select>
            </div>
            <div className="mt-4" />
            {error && (<div className="bg-red-500/10 border border-red-500 text-red-500 p-3 rounded mb-3">{error}</div>)}
            <MatchesList matches={matchesData} league={selectedLeague} dateFilter={dateFilter} statusFilter={statusFilter} onSelectMatch={onSelectMatch} selectedMatches={selectedMatches} loading={loading} />
            <div className="mt-3 flex justify-between items-center">
              <div className="muted">Selecionados: {selectedMatches.length}</div>
              <button className="px-4 py-2 rounded-md bg-[var(--primary)] text-black border border-[var(--border)]">Adicionar à análise</button>
            </div>
          </div>

          <div className="card p-4">
            <div className="text-xl mb-2">Evolução da Banca</div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={evolucao}>
                <CartesianGrid stroke="#1e1e2e" />
                <XAxis dataKey="data" stroke="#71717a" />
                <YAxis stroke="#71717a" tickFormatter={(v) => formatBRL.format(v)} />
                <Tooltip formatter={(value: number) => formatBRL.format(value)} labelFormatter={(label) => label} contentStyle={{ background: "#12121a", border: `1px solid #1e1e2e` }} />
                <Line type="monotone" dataKey="real" stroke="#22c55e" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="projecao" stroke="#8b5cf6" strokeDasharray="6 6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card p-4">
            <div className="text-xl mb-3">Value Bets</div>
            {loading ? (
              <div className="flex items-center justify-center p-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--primary)]"></div><span className="ml-3">Carregando dados...</span></div>
            ) : betsFlat.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left muted">
                    <tr>
                      <th className="py-2">Mercado</th>
                      <th>Stake</th>
                      <th>Odd</th>
                      <th>Retorno Esperado</th>
                      <th>ROI%</th>
                      <th>Confiança</th>
                    </tr>
                  </thead>
                  <tbody>
                    {betsFlat.map((b, i) => (
                      <tr key={i} className="border-t border-[var(--border)]">
                        <td className="py-2">{b.mercado}</td>
                        <td>{formatBRL.format(b.stake)}</td>
                        <td>{Number(b.odd).toFixed(2)}</td>
                        <td>{formatBRL.format(b.retorno)}</td>
                        <td className="text-[var(--primary)]">{b.roi}</td>
                        <td><span className="badge bg-[var(--accent)] text-black">{b.confianca}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="muted">Nenhuma value bet disponível para a liga selecionada.</div>
            )}
          </div>

          <div className="card p-4">
            <div className="text-xl mb-3">Cenários Detalhados</div>
            <Accordion.Root type="single" collapsible className="w-full">
              {valueBetsData.map((vb, idx) => (
                <Accordion.Item key={idx} value={`item-${idx}`} className="border-t border-[var(--border)]">
                  <Accordion.Header>
                    <Accordion.Trigger className="w-full flex items-center justify-between py-3">
                      <div>
                        <div className="font-semibold">{vb?.match?.home_team} x {vb?.match?.away_team}</div>
                        <div className="muted text-sm">{new Date(vb?.match?.match_date ?? Date.now()).toLocaleString("pt-BR")}</div>
                      </div>
                      <span className="badge bg-[var(--accent)] text-black">EV {vb?.ev ?? "-"}</span>
                    </Accordion.Trigger>
                  </Accordion.Header>
                  <Accordion.Content className="pb-4">
                    <div className="grid md:grid-cols-3 gap-4">
                      <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-md">
                        <div className="font-semibold">Otimista</div>
                        <div className="muted text-sm">Probabilidade {vb?.scenarios?.optimistic?.probability ?? "-"}</div>
                        <div className="mt-1">Retorno {vb?.scenarios?.optimistic?.expected_return ?? "-"}</div>
                        <div className="mt-1 text-[var(--primary)]">{vb?.scenarios?.optimistic?.profit ?? "-"}</div>
                        <div className="mt-2 w-full h-2 bg-slate-800 rounded">
                          <div className="h-2 rounded bg-[var(--primary)]" style={{ width: "80%" }} />
                        </div>
                      </div>
                      <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-md">
                        <div className="font-semibold">Realista</div>
                        <div className="muted text-sm">Probabilidade {vb?.scenarios?.realistic?.probability ?? "-"}</div>
                        <div className="mt-1">Retorno {vb?.scenarios?.realistic?.expected_return ?? "-"}</div>
                        <div className="mt-1 text-[var(--info)]">{vb?.scenarios?.realistic?.profit ?? "-"}</div>
                        <div className="mt-2 w-full h-2 bg-slate-800 rounded">
                          <div className="h-2 rounded bg-[var(--info)]" style={{ width: "50%" }} />
                        </div>
                      </div>
                      <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-md">
                        <div className="font-semibold">Pessimista</div>
                        <div className="muted text-sm">Probabilidade {vb?.scenarios?.pessimistic?.probability ?? "-"}</div>
                        <div className="mt-1">Retorno {vb?.scenarios?.pessimistic?.expected_return ?? "-"}</div>
                        <div className="mt-1 text-[var(--danger)]">{vb?.scenarios?.pessimistic?.profit ?? "-"}</div>
                        <div className="mt-2 w-full h-2 bg-slate-800 rounded">
                          <div className="h-2 rounded bg-[var(--danger)]" style={{ width: "20%" }} />
                        </div>
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="muted mb-2">Apostas relacionadas</div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="text-left muted">
                            <tr>
                              <th className="py-2">Mercado</th>
                              <th>Stake</th>
                              <th>Odd</th>
                              <th>EV%</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(vb?.bets ?? []).map((b: any, i: number) => (
                              <tr key={i} className="border-t border-[var(--border)]">
                                <td>{b.market}</td>
                                <td>{b.stake}</td>
                                <td>{b.odds}</td>
                                <td className="text-[var(--primary)]">{b.roi}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="mt-4 flex justify-end">
                      <button className="px-4 py-2 rounded-md bg-[var(--accent)] text-black border border-[var(--border)]">Aplicar Estratégia</button>
                    </div>
                  </Accordion.Content>
                </Accordion.Item>
              ))}
          </Accordion.Root>
        </div>
        <div className="card p-4">
          <DashboardJogos dataJogos={rodadaData} />
        </div>
        </div>
      </div>
      <SystemStatus open={statusOpen} onClose={() => setStatusOpen(false)} />
  </div>
  );
}

function toMatch(leagueId: string) {
  return (item: any, idx: number): Match => {
    const home = item.home_team ?? item.homeTeam?.name ?? item.home ?? "Home";
    const away = item.away_team ?? item.awayTeam?.name ?? item.away ?? "Away";
    const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
    const leagueName = AVAILABLE_LEAGUES.find((l) => l.id === leagueId)?.name ?? leagueId;
    const statusRaw = item.status ?? "scheduled";
    return {
      id: item.id ?? `${leagueId}-${idx}-${home}-${away}-${dt}`,
      leagueId,
      leagueName,
      homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? [], rating: item.homeTeam?.rating ?? 0 },
      awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? [], rating: item.awayTeam?.rating ?? 0 },
      datetime: dt,
      venue: item.venue ?? "",
      status: statusRaw,
      score: item.score,
      odds: { home: item.odds?.home ?? 0, draw: item.odds?.draw ?? 0, away: item.odds?.away ?? 0, over25: item.odds?.over25 ?? 0, under25: item.odds?.under25 ?? 0, bttsYes: item.odds?.bttsYes ?? 0, bttsNo: item.odds?.bttsNo ?? 0 },
      stats: { homeWinProb: item.stats?.homeWinProb ?? 0, drawProb: item.stats?.drawProb ?? 0, awayWinProb: item.stats?.awayWinProb ?? 0, avgGoals: item.stats?.avgGoals ?? 0, bttsProb: item.stats?.bttsProb ?? 0, over25Prob: item.stats?.over25Prob ?? 0 },
      h2h: { totalMatches: item.h2h?.totalMatches ?? 0, homeWins: item.h2h?.homeWins ?? 0, draws: item.h2h?.draws ?? 0, awayWins: item.h2h?.awayWins ?? 0, avgGoals: item.h2h?.avgGoals ?? 0 },
      source: item.source ?? "backend",
      lastUpdated: item.lastUpdated ?? new Date().toISOString(),
    };
  };
}
