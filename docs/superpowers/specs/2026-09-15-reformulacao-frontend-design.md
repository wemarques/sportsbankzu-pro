# Reformulação do frontend — design

**Data:** 2026-09-15
**Autor:** sessão de brainstorming com Welligton
**Status:** design aprovado seção a seção; plano de implementação ainda não escrito
**Alcance:** opção B — identidade visual nova **e** reorganização do dashboard. Não é redesenho da arquitetura de informação inteira (opção C, recusada por ser outro projeto).
**Relacionado:** #246-a (corredor decide por probabilidade), #250 (estados do modelo por liga), #252/#252-a (só geração pré-apito; janela contaminada), #244 (`audit_results` não é fonte), #082/#181 (contrato Mistral), #190 (banca unificada), #187 (rótulos de mercado)

---

## 0. Contexto medido

- Stack: Next.js 15, Tailwind 3 com tokens shadcn, Radix, lucide, Inter. Tema escuro azul-ardósia (`#0f172a`) com verde `#22c55e`; duas famílias de tokens convivendo em `globals.css` (shadcn e "Scoretabs").
- 17 rotas. `dashboard/page.tsx` tem 2.792 linhas e 43 `useState`; as funções de mapeamento de payload (`normalizeMatch`, `toDetailData`) moram na página.
- Quem usa: o operador (Welligton) e, futuramente, assinantes. Dois momentos: desktop para analisar a rodada; celular, perto do apito, para conferir o pick. Hoje não há login em uso.
- O que o operador apontou como sem utilidade: navegação por mercado (1X2, DC, BTTS, gols, cartões, escanteios, "duplas"); a lista "mercados analisados — não recomendados"; "lambda" no texto da Mistral; "Aposte aqui — valor detectado"; "Cálculo de Stake: Quarter Kelly Automático"; "Casa 3.0 Fora 2.5 Liga 4.9" sem unidade; as siglas AI/ST/BS/? do selo de liga. E o que falta: os jogos de ontem.
- Contratos conferidos no backend: a faixa "57–59%" é sintética (`prob_max = prob`, `prob_min = prob − 2`); `odd_minima` é `book_odd or fair_odd` (quando há preço de casa, o painel mostra o preço da casa rotulado de mínimo); `homeCornersPerMatch`, `leagueAvgCorners`, `avgGoals` existem com unidade no nome; **nenhuma rota expõe `prediction_ledger × ledger_outcomes`**; `/audit/status` e `/metrics/brier` leem `audit_results`, o prognóstico recomputado pós-jogo.

## 1. Direção

Personalidade: **o veredito em primeiro plano, o rigor um nível abaixo.** Direção visual escolhida no teste com mockups: **B (Ficha, o bilhete de aposta)** como objeto de decisão, hibridizada:

- de A (Noturno): a frase de frequência ("acontece em 58 de cada 100 jogos assim") dentro do talão; e a linguagem visual inteira de A **reservada à marca** (hero, card social) — emoção na porta de entrada, sobriedade na decisão;
- de C (Instrumento): uma cor única para os números de confiança, e a escala completa com ticks **só na página de detalhe**, nunca no card;
- ajustes em B: linha de preço como badge de edge explícito, banca editável, botão copiar odd, amarelo com menor área e saturação.

Tema escuro único. Nada da identidade atual é sagrado além do nome.

## 2. Tokens

Cada cor tem um significado, e só um. Contrastes (WCAG 2.1) na coluna da direita foram calculados sobre `painel = #1E2026`; com `painel = #22242B` caem alguns décimos e são **recalculados pelo teste de contraste da fase 0**, que é a fonte de verdade. A matriz do teste **deriva dos usos reais**, hover incluído: todo par (texto, superfície) que algum componente produz entra nela.

| Token | Hex | Significa | Contraste |
|---|---|---|---|
| `tinta` | `#15161A` | fundo da página | — |
| `painel` | `#22242B` | superfícies (lista, detalhe); a borda `linha` continua, mas a profundidade não depende dela | — |
| `linha` | `#2C2E36` | divisórias | — |
| `hover` | `#262830` | superfície um passo acima; único estado de hover | — |
| `texto` | `#E6E4DD` | leitura | 12,8–14,2:1 sobre tinta/painel |
| `texto-apagado` | `#93959C` | apoio, amostra, "sem preço", "amostra curta". Subiu de `#8B8D94` porque sobre `hover` dava 4,43:1 | 4,91:1 sobre hover · 5,18:1 sobre painel · 6,04:1 sobre tinta |
| `talao` | `#E3D9AE` | **o pick recomendado, e nada mais.** Só envolve veredito, frequência e linha de preço | — |
| `tinta-do-talao` | `#1B1710` | texto e números dentro do talão (bold para chance e preço) | 12,6:1 sobre talão |
| `tinta-apoiada` | `#4A4436` | apoio dentro do talão | 6,8:1 sobre talão |
| `confianca` | `#4FB3BF` | **números de confiança** (chance, edge, jogos medidos) e a escala do detalhe. **Nunca dentro do talão** (1,7:1 sobre talão): dentro dele, número de confiança é `tinta-do-talao` bold | 6,6–7,3:1 sobre tinta/painel |
| `contra-texto` | `#E8665A` | texto do que joga contra: preço abaixo do mínimo, pick errado, período negativo | 5,0:1 sobre painel |
| `contra` | `#E0533F` | fills, bordas e ícones do mesmo significado | — |

Regras de cor:
- Sem verde. Acerto é `texto` com `✓`; erro é `contra-texto` com `×`; preço abaixo do mínimo é `contra-texto` com `↓`; período negativo é `contra-texto` com `↓`. **Cor nunca é a única portadora do estado** (WCAG 1.4.1).
- **Um significado por glifo:** `✓` = acerto (desfecho), `×` = erro, `↓` = abaixo. Recomendação **não tem glifo**: no feed, é estar no talão; na tabela do detalhe, é a coluna de status em texto ("vale" / "abaixo do mínimo" / "sem preço").
- Estados interativos sem cor nova: link = `texto` sublinhado; hover = `hover`; focus = outline 2px `texto`, offset 2px. O teal fica com um emprego só.
- Sem sombras.

Tipografia:
- **Zilla Slab** 600/700: veredito, times, stake, títulos. Parte-se do pressuposto de que **não tem `tnum`**.
- **Source Sans 3** 400/600: corpo, listas, apoio e **toda coluna de números** (`font-variant-numeric: tabular-nums`, alinhada pela vírgula).
- **Barlow Condensed** 500/700: **só marca** (`app/page.tsx`, `components/marca/`). Lint proíbe a família fora daí; a fonte só é carregada nessas rotas.
- Escala: 13 · 14 · 16 · 18 · 22 · 28 · 36 px. Linha de texto ≤ 70 caracteres. `Inter` sai.

Espaço e forma: base 4px. Raio 4px no talão, 8px nos painéis. O talão é o único objeto "recortado" (meias-luas laterais); isso marca que ele é a decisão.

Princípios:
1. Uma coisa em negrito por tela: o veredito.
2. Número antes de nome: "R$ 25", não "Quarter Kelly"; "58 em cada 100", não "λ".
3. Todo dispositivo visual codifica algo: a linha tracejada é o destaque entre decisão e preço; a escala com ticks só existe onde há medição.
4. Emoção na marca, sobriedade na decisão.
5. Sem chrome de template: nada de eyebrow em caixa alta, mono para rótulos, seta em botão, ponto médio em metadados ("MLS, 20:30", não "MLS · 20:30").

## 3. Arquitetura de informação e navegação

Princípio: o operador navega por **dia** e por **jogo**; o mercado é detalhe dentro do jogo.

| Rota | O que é | Substitui |
|---|---|---|
| `/` | Hero da marca (linguagem A) **só para primeira visita ou deslogado**; quem retorna (cookie lido no server, sem flash) é redirecionado para `/jogos?dia=hoje` | `page.tsx` |
| `/jogos` | **O feed.** Segmented control Dia \| Rodada acima de três tabs (Ontem · Hoje · Amanhã); chips de liga ("todas" primeiro, scroll horizontal com fade, nunca em três linhas). Cada jogo é um card | `dashboard`, `destaques`, `campeonatos`, `duplas` |
| `/jogos/[id]` | Detalhe em página cheia (celular) | `match/[id]`, `MatchDetailCard` |
| `/jogos?dia=ontem` | **Alias, não tela:** o mesmo feed com o resultado no próprio talão (`✓`/`×`) e o resumo do dia no topo | novo |
| `/banca` | Banca editável; alimenta o stake de todo talão | `bankroll` |
| `/desempenho` | Acerto, dinheiro agregado, Brier e calibração por família e liga | `performance-stats`, `ai-audit`, `admin/reliability` |
| `/glossario` | Dez termos, âncora por id, entrada por link contextual (não por tab) | `glossario` |

Somem da navegação (arquivo pode ficar, sem link): `login`, `register` (CTA "entrar / criar conta" **fica visível no hero**, senão rota oculta vira invisível), `admin-activate`, `admin-deactivate`, `debug-live`, `ferramentas` (avaliar conteúdo antes de apagar). Admin acessível por URL, fora do menu.

Navegação: celular, barra inferior com três itens (Jogos · Banca · Desempenho); desktop, sidebar com quatro (Jogos · Banca · Desempenho · Glossário). O eixo de dias vive **só** nos tabs de `/jogos`. Desktop é lista + painel de detalhe com a lista sempre visível; celular abre `/jogos/[id]`.

Estado: **tudo na URL** — `?dia=`, `?liga=`, `?jogo=` (o talão selecionado é link compartilhável; `?jogo=` faz push no history, voltar fecha o painel), e em `/desempenho` `?periodo=`, `?familia=`, `?liga=`. Único estado fora da URL: a banca (localStorage). Ordenação do feed: horário de kickoff, em jogo pinado no topo. Polling pausa com a aba oculta.

## 4. O talão, seus estados e o detalhe

### 4.1 Card do feed (estado "vale")

```
┌ painel ─────────────────────────────────────────────┐
│ Toronto × Nashville SC                    MLS, 20:30 │  Slab 18 · apoio 13
│ (┌ talão ──────────────────────────────────────────┐)│
│  │ Mais de 6,5 escanteios                          │ │  Slab 28, tinta-do-talao
│  │ acontece em 58 de cada 100 jogos assim          │ │  Source 14, tinta-apoiada
│  │ - - - - - - - - - - - - - - - - - - - - - - - - │ │  o destaque
│  │ mercado paga 1,75, acima do mínimo 1,67 (+0,08) │ │  Source 600 tnum, tinta-do-talao
│  │                                    [copiar 1,75]│ │
│ (└─────────────────────────────────────────────────┘)│
│ Da sua banca de R$ 1.000                R$ 25 ajustar│  stake fora do talão
│ MLS: 40 jogos medidos, acerto na média das ligas     │  "40" em confianca
│ Mais de 2,5 cartões   59 em 100, paga 1,70 (+0,03)   │  2º pick, sem botão
│ 12 mercados avaliados, 2 valem — ver todos           │  link → /jogos/[id]#mercados
└──────────────────────────────────────────────────────┘
```

- Linha de preço = badge de edge, frase inteira. Abaixo do mínimo: "mercado paga 1,62, abaixo do mínimo 1,75 (−0,13)" em `contra-texto` com `↓`. "vale a partir de" = `fair_odd`; "mercado paga" = `book_odd`.
- Copiar copia só o número; `aria-label` "copiar odd 1,75"; confirmação "1,75 copiado" no mesmo slot, sem layout shift; clipboard negado → "não deu pra copiar — selecione o número" em `contra-texto`, sem toast.
- Stake sai da banca; Kelly some do texto, a conta não muda. Banca indefinida → "stake: defina sua banca" linkando `/banca`.
- Confiança na liga: os quatro estados do #250 viram frase — "40 jogos medidos, acerto na média" / "acima da média" / "abaixo da média" / "6 jogos medidos, ainda sem base" (este em `texto-apagado`). O backend continua respondendo os quatro estados.
- **Dois valem, um talão:** talão = maior `edge`; empate, maior chance. O segundo vale fica na linha 2 com a frase completa e sem botão; ganha copiar só no detalhe.
- Em jogo: linha do topo ganha período, minuto e placar; o talão congela como recomendação pré-jogo e a linha de preço ganha o sufixo "recomendação pré-jogo" em `tinta-apoiada`.

### 4.2 Enum de estados (derivado do payload em `lib/jogoView.ts`, nunca no componente)

| Estado | Condição (campos do payload) | Card |
|---|---|---|
| `vale` | algum mercado com `classification` ∈ {SAFE, NEUTRO_QUALIFICADO} | talão completo |
| `direcao` | nenhum vale; existe mercado NEUTRO mantido pelo corredor (#246-a) | sem talão, sem stake: "Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje" |
| `nada` | só NO_BET | uma linha "12 mercados avaliados, nenhum vale hoje"; colapsado, expansível |
| `amanha_sem_preco` | data futura e `book_odd` nulo no pick | talão com chance e mínimo; "mercado ainda sem preço"; sem stake |
| `em_jogo` | status ao vivo | topo com período/minuto/placar; talão congelado |
| `ontem` | data passada, com desfecho | faixa `✓ fechou com 8 escanteios` (texto) ou `× fechou com 5` (contra-texto) |
| `ontem_sem_desfecho` | data passada, sem desfecho | talão sem faixa, "resultado ainda não conferido" em `texto-apagado` |

`CardJogo` é um switch sobre esse enum. Contrato: um `type JogoView` e um teste de snapshot com fixture real de payload.

### 4.3 Detalhe (`/jogos/[id]`)

```
Toronto × Nashville SC                          MLS, 09/09, 20:30
[o mesmo talão do feed]

Confiança nesta liga
0 ──┼────┼────┼────┼── 100        ticks; 50 rotulado em texto-apagado 13; zona teal = margem; marca = 58
58 em cada 100, com margem de 52 a 64, em 40 jogos medidos da MLS   ← também é o aria-label

Todos os mercados avaliados (12)                                 ← âncora #mercados
mercado                 chance   mínima   paga    status
Mais de 6,5 escanteios    58%     1,67     1,75   vale  [copiar]
Mais de 2,5 cartões       59%     1,67     1,70   vale  [copiar]
Mais de 2,5 gols          57%     1,75     1,62   ↓ abaixo do mínimo
Ambos marcam              51%      —        —     sem preço
… recusados em texto-apagado, motivo em duas palavras (mapa reason_code → frase em copy.ts)

Como o modelo vê o jogo         ← texto Mistral em vocabulário de operador; some inteiro se indisponível
De onde vem o número            ← "Toronto faz 3,0 gols por jogo em casa; Nashville sofre 2,5 fora; a MLS tem 4,9 por jogo."
                                   só com unidade e comparação; campo ausente → frase ausente
40 jogos medidos nos últimos 60 dias — ver calibração em /desempenho
```

A margem (incerteza da estimativa) vive **só** aqui, com a escala.

### 4.4 Copy, antes → depois

| Hoje | Novo |
|---|---|
| Aposte aqui — valor detectado | *(some; o talão é o sinal)* |
| Cálculo de Stake: Quarter Kelly Automático | Da sua banca de R$ 1.000: R$ 25 |
| Escanteios Over 6.5 · 57–59% · Odd mín 1.67 | Mais de 6,5 escanteios · acontece em 58 de cada 100 · vale a partir de 1,67 |
| Odd mín (quando era o preço da casa) | mercado paga 1,75, acima do mínimo 1,67 (+0,08) |
| AI / ST / BS / ? | MLS: 40 jogos medidos, acerto na média |
| Mercados analisados — não recomendados | 12 mercados avaliados, 2 valem — ver todos |
| Casa 3.0 Fora 2.5 Liga 4.9 | Toronto faz 3,0 gols por jogo em casa; Nashville sofre 2,5 fora; a MLS tem 4,9 por jogo |
| "lambda", "deflação", "banda" (texto Mistral) | vocabulário de operador (item de backend) |

Todas as frases vivem em `lib/copy.ts` (templates com tokens `{term:edge}` que viram links para `/glossario#edge`) e o formatador pt-BR (vírgula decimal, "R$ 1.000,00") num ponto só.

### 4.5 Decisões registradas nesta seção

- **Sem reais por pick em "ontem".** Faixa de payout por pick transforma o painel em extrato de aposta. A visão em dinheiro existe **agregada** em `/desempenho` ("seguindo o stake sugerido, na sua banca atual: semana +R$ X (+y%)"), opcionalmente uma linha no topo de `/ontem` com a mesma frase.
- **Número único no talão (58), não faixa (57–59).** A faixa atual é sintética; a incerteza medida é a margem, que vive no detalhe.

## 5. Telas restantes

**Hero (`/`).** Uma tela: headline em duas linhas (Slab), frase de acerto **vinda do ledger** ("nos últimos 30 dias: 58 de cada 100 picks acertaram em 221 jogos de 20 ligas"; some se n < 20 jogos), CTA "Ver os jogos de hoje" mais "Entrar · Criar conta", e um **talão real** como prova — o de maior edge de hoje; sem pick válido hoje, o talão de ontem com a faixa de resultado; sem nenhum, o slot some. Paleta A só aqui e no card social; o talão dentro do hero usa os tokens do produto.

**Banca (`/banca`).** Input "Sua banca" (foco ao entrar, vírgula decimal), consequência em texto ("cada pick sugere uma fração dela, hoje até R$ 25 por jogo"), link "como a fração é calculada → glossário#stake". Validação inline em `contra-texto` ("banca precisa ser um valor em reais"); confirmação "banca salva" no mesmo slot. Indefinida: input vazio + "Defina a banca para ver quanto apostar em cada jogo." localStorage corrompido → indefinida, sem throw.

**Desempenho (`/desempenho`).** Ordem: desfecho, depois calibração. Filtros na URL: período (7 dias, 30 dias, temporada), família, liga. O período ativo aparece por extenso ao lado do segmento ("03/09–hoje"), para o operador não confiar em palavra mágica.

```
Acerto              58 de cada 100 picks · 221 jogos
Na sua banca atual  +R$ 312 (+3,1%) seguindo o stake sugerido      ← qualificado; negativo em contra-texto com ↓
Por família         picks · acerto · Brier (menor é melhor → glossário#brier); n < mínimo → "amostra curta"
Calibração          gráfico de 10 buckets com a diagonal, único visual da tela; leitura em uma frase
                    ("quando o painel disse 60, aconteceu 57 em cada 100"); aria-label + tabela sr-only
Por liga (n ≥ 20)   mesma tabela, "amostra curta" onde faltar
```

**Glossário (`/glossario`).** Dez termos com exemplo numérico real: chance, mínimo, paga, edge, stake (Kelly explicado só aqui), jogos medidos, calibração, Brier, direção, corredor. Sem busca.

**Estados vazios e de erro, transversais:**

| Situação | Tela |
|---|---|
| Dia sem jogos | "Nenhum jogo nas ligas escolhidas em 16/09." + "próximo dia com picks: quinta" |
| Backend fora / timeout | "Os jogos de hoje não carregaram. Tentar de novo." O último feed carregado fica visível com carimbo "de 14:32"; sem spinner infinito |
| Liga sem dados | card colapsado "MLS: sem dados da rodada" |
| Desempenho sem picks fechados no período | "sem picks fechados neste período" + link para o período maior |
| `/jogos/[id]` inexistente | "jogo não encontrado" + link para o feed de hoje |
| Mistral indisponível | a seção "Como o modelo vê o jogo" some inteira; sem placeholder |

## 6. Componentes e fluxo de dados

### 6.1 Árvore

```
app/  page.tsx · jogos/page.tsx · jogos/[id]/page.tsx · banca/page.tsx · desempenho/page.tsx · glossario/page.tsx
components/feed/     DiaSegment · DiaTabs · LigaChips · CardJogo (switch) · Talao · LinhaStake · LinhaConfianca · LinhaSegundoPick · LinhaAvaliados · ResumoDoDia
components/detalhe/  EscalaConfianca · TabelaMercados (copiar por linha "vale") · ComoOModeloVe · DeOndeVemONumero
components/marca/    Hero · CardSocial                       ← único lugar de Barlow Condensed
lib/                 jogoView.ts (payload → JogoView, puro) · copy.ts · formato.ts · bancaStore.ts (com "indefinida")
```

Um propósito por componente; `CardJogo` não calcula nada.

### 6.2 Fluxo por tela

| Tela | Fonte | Existe | O que falta |
|---|---|---|---|
| Feed hoje/amanhã | `/api/matches/fetch` → `/fixtures?leagues=&date=` | sim | `fair_odd` e `book_odd` separados no mapeamento |
| Em jogo | `useLivePolling` / `/live-scores` | sim | pausa com aba oculta |
| Confiança da liga | `/api/ml/status` (#250) | sim | tradução dos 4 estados em frase (`copy.ts`) |
| Detalhe: tabela | mesmo payload (todos os mercados, `reason_codes`) | sim | mapa `reason_code → duas palavras` |
| Detalhe: texto | `/api/ai/match/{id}/analysis` | sim | prompt em vocabulário de operador (backend) |
| Detalhe: "de onde vem" | `stats.*PerMatch`, `leagueAvg*`, `avgGoals` | sim | frase só com campo presente |
| Ontem | `GET /ledger/dia` | **não** | rota nova |
| Desempenho | `GET /ledger/agregado` | **não** | rota nova |
| Banca | `bancaStore` | sim | estado indefinido |

### 6.3 Contratos novos de backend

**Fonte única:** tudo que o usuário vê sai do ledger (`prediction_ledger × ledger_outcomes`, só geração pré-apito conforme #252, fora da janela contaminada conforme #252-a). Isso inclui **Brier e calibração**: a calibração honesta para o usuário é sobre a probabilidade **publicada**, não sobre o prognóstico recomputado. `audit_results` passa a ser diagnóstico interno (scripts e admin), nunca tela.

`GET /ledger/dia?data=YYYY-MM-DD` — por jogo e por pick publicado:
`match_id, league_id, kickoff_utc, familia, market, selection, published_prob, fair_odd, book_odd (gravado na publicação), classification, outcome (0/1/null), detail (o que fechou: "8 escanteios")` mais o resumo do dia: `picks, acertos, jogos` e os acumulados `semana` e `mes` por família (`picks, acertos, n_jogos`).

`GET /ledger/agregado?periodo=7d|30d|temporada&familia=&liga=` (`temporada` = desde o primeiro pick do ledger, 2026-09-03) — `acerto (picks, acertos, jogos)`, `retorno` (soma de `stake × (book_odd − 1)` nos acertos menos `stake` nos erros, com `stake` = a coluna gravada em `prediction_ledger` convertida a **fração da banca** vigente na publicação; a unidade da coluna é verificação de contrato da fase 1; o cliente multiplica pela banca atual e rotula "na sua banca atual", e mostra também em % da banca), por família e por liga: `picks, acertos, brier, n_jogos`, e `buckets` de calibração (10 faixas: `prob_media, freq_real, n`). Piso `n` mínimo (MIN_N_BRIER = 20, #079): abaixo dele o campo vem `null` e a tela escreve "amostra curta".

`fair_odd` e `book_odd` sempre presentes e distintos no payload de `/fixtures` (verificação de contrato).

Prompt Mistral (#082): vocabulário de operador; `validate_output` rejeita "lambda", "deflação", "banda".

Cada item de backend segue o SDD completo (Etapas 1–5; 2-bis para os consumidores do ledger).

## 7. Validação

| O que protege | Como |
|---|---|
| payload → `JogoView` | snapshot com **fixtures pinadas por data e versão de schema** (um jogo por estado); **teste de contrato** que valida cada fixture contra o type do payload atual — drift falha no CI, não em produção |
| copy e formatação | testes de `copy.ts`/`formato.ts` |
| tokens | teste que calcula o contraste WCAG de cada par permitido e falha abaixo de 4,5:1; teste de largura de "1,67" vs "1,75" na fonte de números |
| famílias | lint: Barlow só em `components/marca` e `app/page.tsx`; Inter em lugar nenhum |
| acessibilidade | axe no Playwright por tela e estado; foco; aria da escala, do copiar e da tabela sr-only |
| estados e URL | Playwright com `/api/*` mockado por fixture, celular e desktop: os sete estados do card, dia sem jogos, backend fora com carimbo, `?jogo=` + voltar, `/jogos/[id]` inexistente, banca indefinida e corrompida, clipboard negado, **ontem sem desfecho, Mistral indisponível, hero com n < 20** |
| **fonte única** | teste: os números do `ResumoDoDia` de `/ontem` == os do agregado de `/desempenho` para o mesmo período |
| regressão visual | viewport fixo (390×844 e 1440×900), animações desligadas, tolerância declarada (0,1% de pixels), **dono do approve de diff: Welligton** |
| backend `/ledger/*` | pytest: só pré-apito, fora da janela contaminada, `n` mínimo → `null`, buckets somam ao total |
| backend contrato | `fair_odd ≠ book_odd` na rota de fixtures; `validate_output` rejeita o vocabulário interno |

**Teste de 5 segundos.** Duas rodadas: mostra uma tela por 5 s e pergunta "qual mercado e qual odd mínima?"; mede acerto, tempo e confiança declarada (1–5); perfis casual e analítico, 4 a 6 pessoas cada. **Rodada 1**, sobre mockups com os **tokens finais** (não o B do teste inicial), antes de construir o feed; **critério pré-registrado: acerto ≥ 80% por perfil e tempo mediano ≤ 5 s no objeto de decisão**; a divisão de perfil deve confirmar B para decisão e C para análise, senão a seção 4 muda enquanto é barato. **Rodada 2** sobre o produto construído, na fase 6. Resultados no REGISTRO com os números.

## 8. Ordem de build

Sete fases, cada uma entregável, com entrada própria em `REGISTRO_CORRECOES`, suíte verde (pytest e Playwright), `lint:accents` (consertado na fase 0) e espelho dos docs.

| Fase | Entrega | Depende de |
|---|---|---|
| 0 | Guardas: tokens em `globals.css`, fontes, lint de família, teste de contraste, `copy.ts` + `formato.ts`, `bancaStore` com indefinido, `lint:accents` no Windows | — |
| 1 | Backend, em paralelo: contrato `fair_odd`/`book_odd`; `/ledger/dia` e `/ledger/agregado`; prompt Mistral | — |
| 2 | `jogoView.ts` extraído do dashboard com snapshots e fixtures pinadas; **zero mudança visual** | 0 |
| 3 | `/jogos`: feed, talão, estados hoje/amanhã/em jogo, `/banca`. **3b, se esticar:** detalhe (escala + tabela) vem depois — o objeto de decisão não espera pelo de rigor | 0, 2 |
| 4 | Ontem no feed, `/desempenho` | 1, 3 |
| 5 | Hero, redirect por cookie, `/glossario`, navegação final, links contextuais | 3, 4 |
| 6 | Rodada 2 do teste de 5 s; `/jogos` vira padrão; **tag e branch de backup antes de apagar** `dashboard/page.tsx`, `duplas`, `destaques`, `campeonatos` e as rotas mortas | 5 |

As rotas novas nascem ao lado das antigas; o corte só acontece na fase 6, depois da validação.

## 9. Fora do escopo

Login e assinatura (as rotas existem, o fluxo não); opção C (arquitetura de informação inteira); mudança em qualquer cálculo do pipeline (o corredor #246-a, os estados #250 e a classificação continuam como estão — muda a exibição); tema claro.
