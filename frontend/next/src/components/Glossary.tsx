"use client";

import React, { useState, useMemo } from "react";
import { GLOSSARY, GLOSSARY_CATEGORIES, type GlossaryEntry } from "@/lib/glossary";
import { Search } from "lucide-react";

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  classificacao: { bg: "rgba(0,255,136,0.12)", color: "#00ff88" },
  metrica: { bg: "rgba(74,158,255,0.12)", color: "#4a9eff" },
  mercado: { bg: "rgba(255,187,51,0.12)", color: "#ffbb33" },
  modelo: { bg: "rgba(157,80,255,0.12)", color: "#c4a0ff" },
};

export default function Glossary() {
  const [filter, setFilter] = useState<string>("todos");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    let items = GLOSSARY;
    if (filter !== "todos") {
      items = items.filter((e) => e.category === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(
        (e) =>
          e.term.toLowerCase().includes(q) ||
          e.definition.toLowerCase().includes(q)
      );
    }
    return items;
  }, [filter, search]);

  return (
    <div style={{ padding: "0 2px" }}>
      {/* Search */}
      <div style={{ position: "relative", marginBottom: 12 }}>
        <Search
          size={14}
          style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#666" }}
        />
        <input
          type="text"
          placeholder="Buscar termo..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: "100%",
            padding: "8px 12px 8px 32px",
            background: "#1a1a1a",
            border: "1px solid #333",
            borderRadius: 8,
            color: "#f0f0f0",
            fontSize: "0.8rem",
            outline: "none",
          }}
        />
      </div>

      {/* Category tabs */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {Object.entries(GLOSSARY_CATEGORIES).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              border: filter === key ? "1px solid #555" : "1px solid #2a2a2a",
              background: filter === key ? "#2a2a2a" : "transparent",
              color: filter === key ? "#f0f0f0" : "#888",
              fontSize: "0.7rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Entries */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {filtered.map((entry) => (
          <GlossaryCard key={entry.term} entry={entry} />
        ))}
        {filtered.length === 0 && (
          <p style={{ color: "#666", fontSize: "0.8rem", textAlign: "center", padding: 16 }}>
            Nenhum termo encontrado.
          </p>
        )}
      </div>
    </div>
  );
}

function GlossaryCard({ entry }: { entry: GlossaryEntry }) {
  const cat = CATEGORY_COLORS[entry.category] ?? { bg: "#1a1a1a", color: "#888" };
  const catLabel = GLOSSARY_CATEGORIES[entry.category] ?? entry.category;

  return (
    <div
      style={{
        background: "#141414",
        border: "1px solid #2a2a2a",
        borderRadius: 8,
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontWeight: 700, fontSize: "0.8rem", color: "#f0f0f0" }}>
          {entry.term}
        </span>
        <span
          style={{
            fontSize: "0.6rem",
            fontWeight: 600,
            padding: "1px 6px",
            borderRadius: 3,
            background: cat.bg,
            color: cat.color,
            textTransform: "uppercase",
            letterSpacing: "0.3px",
          }}
        >
          {catLabel}
        </span>
      </div>
      <p style={{ margin: 0, color: "#aaa", fontSize: "0.75rem", lineHeight: 1.5 }}>
        {entry.definition}
      </p>
      {entry.example && (
        <p style={{ margin: "4px 0 0", color: "#666", fontSize: "0.7rem", fontStyle: "italic" }}>
          Ex: {entry.example}
        </p>
      )}
    </div>
  );
}
