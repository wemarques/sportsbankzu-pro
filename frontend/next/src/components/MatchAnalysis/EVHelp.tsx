"use client";
import { useState } from "react";
import { C } from "./constants";

export const EVHelp = () => {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 4 }}>
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        style={{
          background: "transparent",
          border: "none",
          color: C.t3,
          fontSize: 11,
          cursor: "pointer",
          /* #189-h: alvo de toque maior (WCAG 2.5.5) */
          padding: "8px 8px 8px 0",
        }}
      >
        {open ? "▾" : "▸"} O que significa EV?
      </button>
      {open && (
        <div
          style={{
            marginTop: 6,
            padding: 10,
            background: "rgba(255,255,255,0.02)",
            borderRadius: 5,
            border: `1px solid ${C.border}`,
            fontSize: 11,
            lineHeight: 1.6,
            color: C.t2,
          }}
        >
          <strong style={{ color: C.t1 }}>EV</strong> = lucro esperado por aposta no longo prazo.
          <br />
          <span style={{ color: C.green }}>EV+</span> = odd paga mais que a prob real → lucro
          <br />
          <span style={{ color: C.red }}>EV−</span> = odd paga menos → perda
          <br />
          <br />
          <span style={{ color: C.blue }}>VIÁVEL</span> = chance real de acerto neste jogo, sem valor
          de longo prazo
          <br />
          <br />
          <code
            style={{
              background: "rgba(255,255,255,0.05)",
              padding: "1px 4px",
              borderRadius: 2,
            }}
          >
            EV = (prob × odd) − 1
          </code>
        </div>
      )}
    </div>
  );
};
