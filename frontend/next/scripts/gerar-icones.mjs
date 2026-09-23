#!/usr/bin/env node
// #262 — gera os PNGs do monograma SBZ a partir de public/marca/sbz.svg com a fonte real carregada.
import { chromium } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
const svg = readFileSync("public/marca/sbz.svg", "utf8");
const html = `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&display=swap"><style>body{margin:0;background:#15161A}#m{display:block}</style><div id="m">${svg}</div>`;
const alvos = [["src/app/icon.png", 32], ["src/app/apple-icon.png", 180], ["public/marca/icon-192.png", 192], ["public/marca/icon-512.png", 512]];
mkdirSync("public/marca", { recursive: true });
const b = await chromium.launch(); const p = await b.newPage();
await p.setContent(html); await p.evaluate(() => document.fonts.ready);
for (const [saida, px] of alvos) {
  await p.setViewportSize({ width: px, height: px });
  await p.evaluate((px) => { const s = document.querySelector("svg"); s.setAttribute("width", String(px)); s.setAttribute("height", String(px)); }, px);
  await p.locator("svg").screenshot({ path: saida, omitBackground: false });
  console.log("gerado", saida, px);
}
await b.close();
