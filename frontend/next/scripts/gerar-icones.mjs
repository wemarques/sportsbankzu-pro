#!/usr/bin/env node
// #262 — gera os PNGs do monograma SBZ a partir de public/marca/sbz.svg com a fonte real carregada.
import { chromium } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
const svg = readFileSync("public/marca/sbz.svg", "utf8");
const html = `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&display=swap"><style>body{margin:0;background:transparent}#m{display:block}</style><div id="m">${svg}</div>`;
// #262 fix wave — apple-icon.png sai OPACO (fundo #15161A atras do rect): iOS
// nao aplica mascara em icone com transparencia, o retangulo arredondado do
// SVG deixaria os quatro cantos "vazando" o fundo do sistema. Os outros tres
// alvos continuam transparentes (favicon/PWA compoe a propria mascara).
const alvos = [
  ["src/app/icon.png", 32, false],
  ["src/app/apple-icon.png", 180, true],
  ["public/marca/icon-192.png", 192, false],
  ["public/marca/icon-512.png", 512, false],
];
mkdirSync("public/marca", { recursive: true });
const b = await chromium.launch(); const p = await b.newPage();
await p.setContent(html); await p.evaluate(() => document.fonts.ready);
const fonteCarregada = await p.evaluate(() => document.fonts.check('700 30px "Barlow Condensed"'));
if (!fonteCarregada) {
  console.error("Barlow Condensed 700 nao carregou — abortando para nao gerar icones com fallback Arial.");
  await b.close();
  process.exit(1);
}
for (const [saida, px, opaco] of alvos) {
  await p.setViewportSize({ width: px, height: px });
  await p.evaluate((px) => { const s = document.querySelector("svg"); s.setAttribute("width", String(px)); s.setAttribute("height", String(px)); }, px);
  await p.evaluate((cor) => { document.body.style.background = cor; }, opaco ? "#15161A" : "transparent");
  await p.locator("svg").screenshot({ path: saida, omitBackground: !opaco });
  console.log("gerado", saida, px, opaco ? "opaco" : "transparente");
}
await b.close();
