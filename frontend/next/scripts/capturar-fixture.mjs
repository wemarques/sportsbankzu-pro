#!/usr/bin/env node
/** #254-a — captura o payload real da Lambda e pina data + versao de schema. */
import { writeFileSync } from "node:fs";
const BASE = "https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws";
const [leagues = "mls,brasileirao-serie-b,premier-league", date = "today"] = process.argv.slice(2);
const res = await fetch(`${BASE}/fixtures?leagues=${leagues}&date=${date}`);
const body = await res.json();
const hoje = new Date().toISOString().slice(0, 10);
const out = { schema: "fixtures.v1", capturado_em: new Date().toISOString(), fonte: `/fixtures?leagues=${leagues}&date=${date}`, matches: body.matches ?? [] };
const path = `tests/fixtures/fixtures.${hoje}.v1.json`;
writeFileSync(path, JSON.stringify(out, null, 2));
console.log(`${out.matches.length} jogos → ${path}`);
