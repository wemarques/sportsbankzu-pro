"use client";
export default function Chips({ items, value, onChange }: { items: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((i) => (
        <button key={i} onClick={() => onChange(i)} className={`px-3 py-1 rounded-full ${value === i ? 'bg-primary text-black' : 'bg-slate-700 text-white'}`}>{i}</button>
      ))}
    </div>
  );
}
