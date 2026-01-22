export default function Transfers({ items }: { items: Array<{ driver: string; teamFrom: string; teamTo: string; date: string }> }) {
  return (
    <div className="card p-4">
      <div className="text-lg mb-2">Transferências</div>
      <div className="space-y-2">
        {items.map((t, i) => (
          <div key={i} className="flex justify-between">
            <span>{t.driver}</span>
            <span className="muted">{t.teamFrom} → {t.teamTo}</span>
            <span className="muted">{t.date}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
