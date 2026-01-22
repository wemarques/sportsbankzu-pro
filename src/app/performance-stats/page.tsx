"use client";
import { useEffect, useState } from "react";
import HeatMap from "../../components/HeatMap";
import DRSZones from "../../components/DRSZones";
import Transfers from "../../components/Transfers";
import { getPerformanceStats, getDRSZones } from "../../lib/api";

export default function PerformanceStats() {
  const [heat, setHeat] = useState<number[]>([]);
  const [drs, setDrs] = useState<Array<{ start: number; end: number }>>([]);
  const transfers = [
    { driver: 'Driver A', teamFrom: 'Team X', teamTo: 'Team Y', date: '2025-06-01' },
    { driver: 'Driver B', teamFrom: 'Team Y', teamTo: 'Team Z', date: '2025-07-15' },
  ];
  useEffect(() => { (async () => { try { const p = await getPerformanceStats('driver_1'); setHeat(p?.heatmap ?? Array(64).fill(0)); const z = await getDRSZones('race_1'); setDrs(z ?? []); } catch { setHeat(Array(64).fill(0).map((_, i) => (i % 10))); setDrs([{ start: 10, end: 25 }, { start: 55, end: 75 }]); } })(); }, []);
  return (
    <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="card p-4">
        <div className="text-xl mb-3">Heat Map</div>
        <HeatMap rows={8} cols={8} data={heat} />
      </div>
      <DRSZones zones={drs} />
      <Transfers items={transfers} />
    </div>
  );
}
