export default function DRSZones({ zones }: { zones: Array<{ start: number; end: number }> }) {
  return (
    <div className="card p-4">
      <div className="muted mb-2">DRS Zones</div>
      <div className="w-full h-6 bg-slate-700 rounded-xl relative">
        {zones.map((z, idx) => (
          <div key={idx} className="absolute h-6 bg-primary/80" style={{ left: `${z.start}%`, width: `${z.end - z.start}%`, borderRadius: '0.75rem' }} />
        ))}
      </div>
    </div>
  );
}
