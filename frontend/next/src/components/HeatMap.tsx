export default function HeatMap({ rows, cols, data }: { rows: number; cols: number; data: number[] }) {
  const max = Math.max(...data, 1);
  return (
    <div className="grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: 4 }}>
      {Array.from({ length: rows * cols }).map((_, i) => {
        const val = data[i] ?? 0;
        const pct = Math.round((val / max) * 100);
        return <div key={i} className="h-6 rounded" style={{ backgroundColor: `rgba(16,185,129,${pct / 100})` }} />;
      })}
    </div>
  );
}
