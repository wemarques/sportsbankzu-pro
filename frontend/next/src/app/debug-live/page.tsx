
"use client";

import { useEffect, useState } from "react";

export default function DebugLivePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/debug-live")
      .then((res) => res.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="p-8 text-white">Carregando dados brutos da API...</div>;
  if (error) return <div className="p-8 text-red-500">Erro: {error}</div>;

  return (
    <div className="p-8 bg-gray-900 min-h-screen text-white font-mono text-xs">
      <h1 className="text-xl mb-4 text-yellow-400">Debug Live Scores (Raw FootyStats Data)</h1>
      <div className="mb-4">
        <p>Total Jogos: {data?.data?.length ?? 0}</p>
        <p>Success: {String(data?.success)}</p>
      </div>
      
      {data?.data?.map((m: any, i: number) => (
        <div key={i} className="mb-4 p-4 border border-gray-700 rounded bg-gray-800">
            <div className="font-bold text-green-400 mb-2">
                {m.home_name} vs {m.away_name} (Status: {m.status})
            </div>
            <div className="grid grid-cols-2 gap-2">
                <div>Home Goals: {m.homeGoalCount} (raw: {JSON.stringify(m.homeGoalCount)})</div>
                <div>Away Goals: {m.awayGoalCount} (raw: {JSON.stringify(m.awayGoalCount)})</div>
                <div>Total Goals: {m.totalGoalCount}</div>
                <div>HT Goals: {m.home_team_goal_count_half_time} - {m.away_team_goal_count_half_time}</div>
            </div>
            <details className="mt-2">
                <summary className="cursor-pointer text-blue-400">Ver JSON completo</summary>
                <pre className="mt-2 whitespace-pre-wrap text-gray-400">
                    {JSON.stringify(m, null, 2)}
                </pre>
            </details>
        </div>
      ))}
    </div>
  );
}
