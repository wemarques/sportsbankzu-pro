#!/usr/bin/env node
/**
 * #254 — guarda de familias tipograficas (spec §2).
 * Barlow Condensed so em src/components/marca e src/app/page.tsx.
 * Inter em lugar nenhum. Falha com a lista de ocorrencias.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../src", import.meta.url));
const PERMITIDO_BARLOW = [join("components", "marca"), join("app", "page.tsx")];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== "node_modules") yield* walk(p); }
    else if (/\.(tsx|ts|css)$/.test(name)) yield p;
  }
}

const violacoes = [];
for (const file of walk(ROOT)) {
  const rel = relative(ROOT, file);
  const src = readFileSync(file, "utf8");
  if (/\bInter\b/.test(src) && /next\/font|font-family|fontFamily/.test(src)) {
    violacoes.push(`${rel}: Inter`);
  }
  if (/Barlow/.test(src) && !PERMITIDO_BARLOW.some((ok) => rel.startsWith(ok))) {
    violacoes.push(`${rel}: Barlow Condensed fora de components/marca`);
  }
}
if (violacoes.length) {
  console.error(`✗ lint:fonts — ${violacoes.length} violacao(oes):\n  ` + violacoes.join("\n  "));
  process.exit(1);
}
console.log("✓ lint:fonts — familias no lugar.");
