export default function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="w-full h-3 bg-slate-700 rounded-full">
      <div className="h-3 rounded-full" style={{ width: `${pct}%`, backgroundColor: pct > 100 ? "#ef4444" : "#10b981" }} />
    </div>
  );
}