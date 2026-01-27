"use client";
import { useEffect, useState } from "react";
import { AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import Chips from "../../components/Chips";
import { getTrendData } from "../../lib/api";

export default function MarketTrends() {
  const metrics = ["odds", "ev", "stake", "points"];
  const [metric, setMetric] = useState("odds");
  const [data, setData] = useState<{ label: string; value: number }[]>([]);
  useEffect(() => { (async () => { try { const d = await getTrendData(metric); setData(d ?? []); } catch { setData(Array.from({ length: 30 }, (_, i) => ({ label: `Dia ${i+1}`, value: 50 + i })))} })(); }, [metric]);
  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div className="text-xl">Market Trends</div>
          <Chips items={metrics} value={metric} onChange={setMetric} />
        </div>
        <div className="mt-4">
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data}>
              <CartesianGrid stroke="#334155" />
              <XAxis dataKey="label" stroke="#94a3b8" /><YAxis stroke="#94a3b8" />
              <Tooltip />
              <Area dataKey="value" stroke="#10b981" fill="#10b981" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
