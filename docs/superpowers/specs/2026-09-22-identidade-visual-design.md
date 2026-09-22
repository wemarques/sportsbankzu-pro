# Identidade visual do produto novo: cabeçalho, cor de marca, profundidade, carregamento e arte

**Data:** 2026-09-22 | **Dono:** Welligton | **Emenda à spec** `2026-09-15-reformulacao-frontend-design.md` (§1, §2, §3, §4.2 e §5). Entrada de REGISTRO reservada: **#262**.
**Origem:** crítica do dono sobre o produto em produção após a fase 6 ("sem cabeçalho, sem cor, pouco atrativa, sem arte; carregando é tela preta"). Decisões tomadas em diálogo, uma por vez, em 2026-09-22: direção "marca forte, produto sóbrio"; fundo escuro mantido; cor de identidade = teal; cabeçalho com marca e data. Referências de inspiração do dono: scores24.live e betmines.com (usadas para a hierarquia do cabeçalho, não para o tema claro nem para a densidade em linhas).

## 0. O que muda e o que não muda

Muda: a moldura de todas as rotas (cabeçalho fixo), os tokens (um novo, uma revogação), a hierarquia de cor da navegação e dos chips, a profundidade dos cards, o estado de carregamento, os estados vazios e os ícones da aplicação.

Não muda: o talão (objeto de decisão validado na rodada 2 do teste de 5 s, #257-a), a faixa de acerto, o vermelho de "contra", a tabela de mercados, a copy dos estados já definidos, a navegação (sidebar no desktop, barra inferior no celular), o fundo tinta.

## 1. Cabeçalho fixo (revisa §3)

- Barra fixa no topo, 56 px de altura, em **todas** as rotas, inclusive `/` (hero fica abaixo dela), `/login` e `/register`. Fundo `--sb-painel`, linha inferior `--sb-linha` de 1 px. `<header>` com `role="banner"`; o conteúdo da página começa abaixo dela (padding-top no layout, sem sobreposição).
- **Esquerda:** marca "sportsbankzu" em Barlow (`fonteMarca`, a única exceção de fonte que a §2 já permite), com "zu" em `--sb-marca`, precedida do monograma (§4). É um `<Link href="/jogos">` com `aria-label="sportsbankzu, ir para os jogos"`.
- **Direita:** a data do dia do operador por extenso em BRT (UTC-3 fixo, mesma regra de `diaISOHoje`): "terça, 22 de setembro". Sem ano. Formatador em `lib/formato.ts`, com teste. A data vira no cliente à meia-noite BRT sem refresh: um timer agendado para o próximo 00:00 BRT (teste com relógio falso). Sem persistência.
- **Não vai no cabeçalho:** carimbo de leitura ("lido às 19:04"). Motivo: em `/banca`, `/glossario` e `/` não há leitura para carimbar. O carimbo vai ao topo do conteúdo de `/jogos` e de `/desempenho`, específico da rota, sempre que existir última leitura boa (hoje só aparece em erro). Copy: `CARIMBO.lidoAs(hora)` → "lido às 19:04".
- **Celular (< 640 px):** a data sai; fica monograma + marca. A barra inferior de navegação continua igual à §3.
- **Desktop:** a sidebar de 200 px começa abaixo do cabeçalho (não ao lado dele).

## 2. Cor de marca e profundidade (revisa §2)

- **Token novo** `--sb-marca: #4FB3BF`. Mesmo hex de `--sb-confianca`, token distinto de propósito: teal como "a casa" (marca, navegação, seleção) e teal como "confiança medida" podem divergir no futuro sem quebrar a escala.
- **Onde `--sb-marca` entra:** "zu" da marca e monograma; item ativo da navegação (texto teal, além do negrito atual); chip de liga selecionado (borda e texto teal, fundo painel); sublinhado dos links (`text-decoration-color`), com o texto dos links na cor do texto; borda do card selecionado no desktop (`?jogo=`), que hoje é branca.
- **Chip não selecionado, declarado:** texto `--sb-texto`, fundo `--sb-painel`, borda `--sb-linha`. Hover: fundo `--sb-hover`, borda inalterada. Um chip não selecionado com hover nunca se parece com o selecionado (o selecionado é definido pela cor da borda e do texto, não pelo fundo).
- **Onde `--sb-marca` não entra:** talão, faixa "✓ fechou com", "× fechou com", tabela de mercados, escala de confiança (que continua `--sb-confianca`).
- **Profundidade.** A §2 dizia "Sem sombras; profundidade vem de painel sobre tinta". **Revogado conscientemente:** profundidade agora vem de painel sobre tinta **mais** borda `--sb-linha` de 1 px **mais** sombra baixa `box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3)` nos cards do feed, no painel de detalhe e nos blocos de `/banca` e `/desempenho`. O talão continua sem sombra (é objeto recortado, §4.1). `--sb-painel` fica em `#22242B` (já é mais claro que a tinta; não se abre nova discussão de contraste).
- **Contraste a re-medir e registrar no #262:** teal sobre `#22242B` (esperado ≈ 6,6:1), teal sobre `#15161A`, texto sobre painel com borda.

## 3. Carregando (novo estado transversal; revisa §4.2 e §5 "estados vazios")

Regra de honestidade: a tela nunca afirma "sem jogos" antes de receber uma resposta. O esqueleto não mente enquanto o pedido está em voo; o estado vazio mentiria.

- **Existe última leitura boa** (polling, troca de aba, volta ao app, `?liga=` trocado): a lista anterior fica na tela com o seu carimbo; nunca esqueleto. É o comportamento atual de `ultimoBom`, agora escrito.
- **Não existe leitura boa** (primeira carga da sessão, ou primeira carga de um dia/aba sem cache): três cards-esqueleto no lugar da lista, com blocos `--sb-texto-apagado` a 30 % de opacidade no lugar do título, do talão e das duas linhas, pulsando devagar (1,6 s); `prefers-reduced-motion: reduce` desliga a animação e mantém os blocos estáticos. A lista recebe `aria-busy="true"` e um `role="status"` visualmente oculto diz "buscando os jogos de hoje".
- **Aos 1,5 s em voo**, entra abaixo do esqueleto a frase visível `CARREGANDO.demora(n)` → "buscando os jogos de hoje em 13 ligas, costuma levar até 12 segundos", com `n` = `ACTIVE_LEAGUES().length` (nunca número fixo na copy). "hoje"/"ontem"/"amanhã" segue a aba.
- **Timeout:** o que já existe (55 s na rota). Ao estourar, o estado de erro atual (`VAZIOS.feedNaoCarregou` + "Tentar de novo" + carimbo) substitui o esqueleto.
- **Vazio:** `VAZIOS` de "nenhum jogo nas ligas escolhidas" só aparece com resposta recebida e lista vazia. Nunca por tempo.
- **Mesmo esqueleto** para o painel de detalhe (`?jogo=`) e para `/desempenho` (blocos no lugar da linha de acerto e da tabela), com a mesma regra de 1,5 s e a frase adequada ("buscando o desempenho").
- **Aba Ontem:** a regra "ontem chega primeiro" é do hero (§5, M2 da fase 6) e não se aplica ao feed. Na aba Ontem vale a mesma regra deste capítulo, com "buscando os jogos de ontem".

## 4. Arte (revisa §1 e §5 "estados vazios")

- **Monograma "zu"**: um SVG único, `public/marca/zu.svg`, letras "zu" em Barlow convertidas em caminho (sem dependência de fonte no SVG), teal `#4FB3BF` sobre tinta `#15161A` com canto de 4 px. Só versão escura; se o tema claro voltar (fora do escopo, §5 da spec original), cria-se a versão clara.
- **Usos:** cabeçalho (20 px, ao lado do nome); favicon e ícones da aplicação (`favicon.ico` 16 e 32, `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` 180) gerados a partir do SVG e referenciados no `metadata` do `layout.tsx`; estados vazios ("nenhum jogo nas ligas escolhidas", "sem talão publicado hoje ou ontem", "sem picks fechados no período", "banca indefinida") ganham o monograma a 48 px em `--sb-texto-apagado` acima do texto, nunca em teal (vazio não é destaque).
- **Sem ilustração no feed nem no detalhe.** O objeto de decisão continua limpo.

## 5. Fora deste desenho, declarado

- Escudos dos times e das ligas: o campo `logo` vem vazio da API e não há pasta de logos. Exige fonte de dados (API-Football) e vira task própria, com contrato auditado (Etapa 2).
- Agrupamento por liga em linhas densas (scores24): o card foi o objeto validado na rodada 2; não muda.
- Tema claro: descartado pela decisão "fundo escuro" de 2026-09-22.
- **M5 (cabeçalho do feed fixo, dívida do #258) é substituído por esta emenda:** abas e chips rolam com o conteúdo, porque o cabeçalho fixo da aplicação já dá ancoragem visual. Fecha por emenda, não por commit.

## 6. Componentes e arquivos (revisa §6.1)

- `components/marca/Cabecalho.tsx` (novo; client, por causa do relógio da data) e `components/marca/Monograma.tsx` (novo; SVG inline com `aria-hidden` quando decorativo).
- `lib/formato.ts`: `dataPorExtensoBrt(agora: Date)` → "terça, 22 de setembro"; `proximaMeiaNoiteBrt(agora)`.
- `lib/copy.ts`: `MARCA.nome`, `MARCA.ariaLink`, `CARIMBO.lidoAs`, `CARREGANDO.buscando(dia)`, `CARREGANDO.demora(dia, n)`, `CARREGANDO.desempenho`. Tudo passa por `lint:accents`.
- `components/feed/EsqueletoCard.tsx`, `components/detalhe/EsqueletoDetalhe.tsx`, `app/desempenho/Esqueleto.tsx` (novos). `Feed.tsx`: estado `carregando && jogos.length === 0` → esqueleto; timer de 1,5 s para a frase; carimbo no topo do conteúdo.
- `components/nav/Navegacao.tsx`: item ativo em teal. `components/feed/LigaChips.tsx`: estados declarados na §2.
- `app/layout.tsx`: cabeçalho acima de sidebar + conteúdo; `metadata.icons`.
- `globals.css`: `--sb-marca`, classe `.sb-card` (borda + sombra), keyframes do esqueleto com `@media (prefers-reduced-motion: reduce)`.

## 7. Validação e portão

- Unit: formatador de data (BRT, virada de dia com relógio falso), copy (frases com `n` dinâmico), esqueleto (aparece só sem leitura boa; frase aos 1,5 s com timers falsos; some com a resposta; erro após timeout), chips (selecionado ≠ hover).
- E2E chromium (build de produção): cabeçalho presente em todas as rotas com `role="banner"`; data em BRT; carimbo em `/jogos` e `/desempenho` e ausente em `/banca`, `/glossario`, `/`; esqueleto com feed atrasado por `page.route` (`setTimeout` de 3 s) mostrando a frase aos 1,5 s e nunca "nenhum jogo" antes da resposta; `prefers-reduced-motion` via `page.emulateMedia` sem animação; vazio só após resposta vazia.
- Axe nas rotas com o cabeçalho; contraste do teal medido e registrado.
- Visual: as nove referências mudam. Fluxo de sempre: diff no relatório, approve do dono por imagem, commit separado das referências.
- Rodada de teste de 5 s: não se repete (card e talão não mudam).
- `lint:accents`, `lint:fonts` (Barlow só na marca: o cabeçalho usa `fonteMarca` só no nome), `tsc` sem cache, Vitest, build.

## 8. Ordem de build (uma fase, tasks pequenas)

1. Tokens, `.sb-card`, chips e navegação em teal (sem cabeçalho ainda): visual muda pouco, mede contraste.
2. Monograma SVG + ícones + `metadata`.
3. Cabeçalho fixo + layout + data BRT com virada de dia.
4. Carimbo no topo de `/jogos` e `/desempenho`.
5. Esqueletos (feed, detalhe, desempenho) + frase de 1,5 s + testes de honestidade.
6. Estados vazios com o monograma.
7. Referências visuais (após approve), REGISTRO #262, fechamento; M5 fechado por emenda.

## 9. Decisões registradas

- Cabeçalho universal com marca + data; carimbo é da rota (dono, 2026-09-22).
- `--sb-marca` separado de `--sb-confianca` com o mesmo hex (dono).
- "Sem sombras" da §2 revogado; sombra `0 1px 3px rgba(0,0,0,0.3)`; painel mantido `#22242B` (dono).
- Esqueleto nunca vira "sem jogos" por tempo; aos 1,5 s entra a frase de demora; vazio só com resposta (proposta do controller, aceita pelo dono depois da objeção ao timeout de 1,5 s para o vazio).
- Monograma só em versão escura; ícones 16/32/180/192/512 (dono).
- M5 substituído por esta emenda (dono).
