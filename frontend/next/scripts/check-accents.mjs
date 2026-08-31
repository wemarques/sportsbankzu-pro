#!/usr/bin/env node
/**
 * #189-j — guarda de acentuação da interface.
 *
 * Varre strings literais dos .tsx/.ts de UI procurando palavras pt-BR
 * escritas sem acento e falha com a lista de ocorrências. Roda no CI ou
 * localmente: `npm run lint:accents`.
 *
 * O que NÃO é violação: chaves internas (comparações ===, key:, category:,
 * localStorage, useState<...>), classes CSS, imports, rotas e o allowlist
 * abaixo (identificadores de dados que por contrato ficam sem acento —
 * ex.: o sub-tab "ultimos" e as chaves de bandeira "serie a"/"serie b").
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;

// Palavras proibidas em texto exibido (minúsculas; o match ignora caixa).
const FORBIDDEN = [
  "nao", "sao", "voce", "apos", "ate", "ja",
  "analise", "gestao", "glossario", "cartoes", "acoes", "opcoes", "razoes",
  "calibracao", "alocacao", "avaliacao", "ativacao", "atualizacao",
  "informacao", "informacoes", "recomendacao", "recomendacoes", "combinacao",
  "classificacao", "classificacoes", "configuracao", "correlacao", "selecao",
  "notificacoes", "contradicoes", "violacoes", "variacao", "duracao",
  "confianca", "seguranca", "consistencia", "frequencia", "tendencia",
  "referencia", "sequencia", "eficiencia", "ausencia", "divergencia",
  "significancia", "experiencia",
  "metrica", "metricas", "estatistica", "estatisticas", "estatistico", "estatisticos",
  "matematico", "matematica", "quadratico", "parametro", "parametros",
  "medio", "media", "medias", "otimo", "pessimo", "razoavel", "aceitavel",
  "disponivel", "disponiveis", "indisponivel", "indisponiveis", "possivel",
  "possiveis", "confiavel", "confiaveis", "elegivel", "responsavel", "instavel",
  "nivel", "util", "codigo", "numero", "metodo", "periodo", "historico",
  "historicos", "relatorio", "usuario", "proximo", "proximos", "proxima",
  "ultimo", "ultima", "ultimos", "unico", "unica", "grafico", "graficos",
  "pratica", "rapido", "rapida", "automatico", "automatica", "basico",
  "primaria", "secundaria", "extensao", "conexao", "precisao", "precisao",
  "criterios", "quao", "estao", "porem", "tambem", "amanha", "pagina",
  "estadio", "arbitro", "conteudo", "editavel",
];

// Ocorrências legítimas (chave interna, id de dado) — arquivo:palavra.
const ALLOWLIST = new Set([
  "components/MatchDetailCard.tsx:ultimos", // chave do sub-tab (useState/setActiveSubTab)
  "components/MatchDetailCard.tsx:cartoes", // chave de tab de estatísticas
  "components/AuditReportCard.tsx:serie",   // chaves do mapa de bandeiras "serie a"/"serie b"
  "components/AuditReportCard.tsx:media",   // valor de severidade do contrato backend (ALTA|MEDIA|BAIXA)
  "components/BatchAuditPanel.tsx:media",   // sufixo de classe CSS --media
  "components/MatchAnalysis/AICard.tsx:glossario", // chave de tab
  "app/dashboard/page.tsx:glossario",       // chave NavView + rota /glossario
  "app/glossario/page.tsx:glossario",       // initialView (chave NavView)
  "app/performance-stats/page.tsx:cartoes", // chave MarketFamily
  "app/match/[id]/page.tsx:estadio",        // nome próprio em espanhol (Estadio ...)
  "lib/chartTokens.ts:cartoes",             // chave MarketFamily
  "lib/api.ts:media",                       // valor de severidade do contrato backend
  "lib/localAudit.ts:nao",                  // valor de dado do ledger local
  "lib/localAudit.ts:media",                // valor de severidade
  "lib/mockMatches.ts:sao",                 // nomes de times/estádios espelhando a API
  "lib/mockMatches.ts:estadio",
]);

// Linhas que carregam chave/identificador, não texto exibido.
const SKIP_LINE =
  /className=|import |from ["']|href=|localStorage|sessionStorage|\/api\/|key=|key:|category:|=== ?["']|!== ?["']|useState<|\.has\(|\.add\(|data-|id=|\.css|console\.|@\/|\.tsx|\.ts["']/;

const wordRe = new RegExp(`\\b(${FORBIDDEN.join("|")})\\b`, "gi");

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) {
      if (name === "node_modules" || name === "api") continue;
      yield* walk(p);
    } else if (/\.(tsx|ts)$/.test(name) && !name.endsWith(".d.ts")) {
      yield p;
    }
  }
}

// extrai só o conteúdo de strings literais ('...', "...", `...`) da linha
function literalChunks(line) {
  const out = [];
  const re = /'([^'\\]*(?:\\.[^'\\]*)*)'|"([^"\\]*(?:\\.[^"\\]*)*)"|`([^`\\]*(?:\\.[^`\\]*)*)`/g;
  let m;
  while ((m = re.exec(line)) !== null) out.push(m[1] ?? m[2] ?? m[3] ?? "");
  return out;
}

let violations = [];
for (const file of walk(ROOT)) {
  const rel = relative(ROOT, file);
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    const t = line.trim();
    if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) return;
    if (SKIP_LINE.test(line)) return;
    for (const chunk of literalChunks(line)) {
      let m;
      wordRe.lastIndex = 0;
      while ((m = wordRe.exec(chunk)) !== null) {
        const word = m[1].toLowerCase();
        if (ALLOWLIST.has(`${rel}:${word}`)) continue;
        violations.push(`${rel}:${i + 1}: "${m[1]}" em «${chunk.slice(0, 70)}»`);
      }
    }
  });
}

if (violations.length) {
  console.error(`✗ ${violations.length} palavra(s) sem acento em texto de interface:\n`);
  for (const v of violations) console.error("  " + v);
  console.error(
    "\nCorrija a acentuação, ou — se for chave interna/id de dado — adicione ao ALLOWLIST em scripts/check-accents.mjs.",
  );
  process.exit(1);
}
console.log("✓ lint:accents — nenhuma palavra sem acento em texto de interface.");
