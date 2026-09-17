# Rodada 2 do teste de 5s — material recapturado (#258)

**Recapturado em:** 2026-09-17, contra o produto reconstruído (`next build` +
`next start`, porta 3001, commit `46fb499` já na árvore), `PY_BACKEND_URL`
apontado para a Lambda Function URL de produção (nunca o API Gateway — regra
#114/#203). Dados reais, sem stub.

**Jogo "vale" encontrado:** `hoje` já tinha um card em estado "vale" —
**Málaga CF × Villarreal (La Liga)**, pick **Under 3.5 gols**, paga 1,50
(mínimo 1,47). O script tentou `hoje` primeiro e parou aí, sem precisar cair
para `amanha` (comportamento padrão confirmado, sem flag `--dia`).

**Arquivos (6 PNGs, 3 telas × 2 viewports):**
- `tela-1-talao-mobile.png` / `tela-1-talao-desktop.png` — objeto de decisão (card "vale" em `/jogos`)
- `tela-2-tabela-mobile.png` / `tela-2-tabela-desktop.png` — objeto de rigor (tabela de mercados no detalhe do jogo)
- `tela-3-hero-mobile.png` / `tela-3-hero-desktop.png` — compreensão (`/`, primeira visita, sem cookies)

Viewports: celular 390×844, desktop 1440×900.

## Hero — ramo e tempo (fix C)

Script agora corre `Promise.race` entre `waitForSelector("article")` e
`waitForFunction` do texto `HERO.semTalao` ("Sem talão publicado hoje ou
ontem.", `src/lib/copy.ts`), até 30s, em vez do `waitForTimeout(1500)` fixo
que a rodada 1 usava (`diagnostico-B-C.md` mediu o card-prova levando até
~7.3s para resolver).

Medido nesta captura:
- **mobile:** ramo `card` (Málaga CF × Villarreal, estado=vale) em **12.23s**
- **desktop:** ramo `card` (Málaga CF × Villarreal, estado=vale) em **4.53s**

Os dois ramos resolveram via card-prova (não precisou do fallback
`HERO.semTalao`); a variação de tempo entre mobile/desktop reflete o
fan-out real de 13 ligas na primeira visita, não um artefato do script.

## Tabela de mercados — sem bloco navy (fix B)

Antes do `table#mercados.screenshot()`, o script agora mede
`getBoundingClientRect().bottom` da tabela e redimensiona a viewport
(`page.setViewportSize`) para caber o rodapé, em loop curto (até 3
tentativas, porque o próprio resize pode mudar o layout do `aside sticky`).
Isso elimina o bloco navy sólido que aparecia quando `rect.bottom` da tabela
ficava fora da viewport renderizada de 900px (causa raiz documentada em
`diagnostico-B-C.md`: `locator.screenshot()` usa um clip do CDP limitado à
viewport atual; a área não pintada devolvia a cor de fundo do `body`).
Confirmado visualmente em `tela-2-tabela-desktop.png` e
`tela-2-tabela-mobile.png`: as 11 linhas da tabela de Málaga × Villarreal
aparecem completas, sem corte, sem navy.

## Motivo de duas palavras (fix A, #258, commit 46fb499)

O jogo "vale" desta captura (Málaga × Villarreal) não tem nenhum mercado com
`reason_code=BORDERLINE_LINE_MARGIN` no momento da captura — dado real,
variável a cada rodada de odds/predições, fora do controle do script. Por
isso `tela-2-tabela-{viewport}.png` não exibe literalmente "linha no
limite".

Verificação independente, ao vivo, contra o mesmo build rodando em
localhost:3001 (não incluída nos 6 PNGs oficiais, apenas navegação manual
via Playwright para confirmar o fix): **Monza × Sassuolo** (`/jogos?dia=amanha`)
— o mesmo confronto que a rodada 2 original (commit `51b1955`, antes do fix)
já tinha capturado — mostrava antes:

```
Over 2.5 gols   69%   1,44   1,82   não vale
```

e agora, pós-rebuild, mostra:

```
Over 2.5 gols   69%   1,44   1,81   linha no limite
```

(`Vila Nova × América Mineiro`, mesmo dia, mesma condição, confirma o
mesmo padrão.) Isso prova o fix #258 funcionando ponta a ponta em produção
— a mudança de "não vale" para "linha no limite" é exatamente o
`BORDERLINE_LINE_MARGIN → "linha no limite"` adicionado em `reasonCodes.ts`
no commit `46fb499`. A cobertura também está garantida pelos 6 testes
unitários + 1 teste de cobertura desse mesmo commit
(`frontend/next/tests/unit/reasonCodes.test.ts`).

**Reproduzir a verificação do fix A isoladamente:** com o servidor de pé,
abrir `/jogos?dia=amanha`, localizar o card "Monza × Sassuolo" (estado
"vale") e checar a linha "Over 2.5 gols" na tabela de detalhe.

**Reproduzir a captura completa:** `node scripts/capturar-telas-teste-5s.mjs --base=http://localhost:3001`
a partir de `frontend/next`, com o servidor de produção de pé na porta 3001
(`PY_BACKEND_URL` apontando para a Lambda Function URL de produção). Use
`--dia=hoje` ou `--dia=amanha` para fixar um dia; sem a flag, o script tenta
os dois antes de desistir. Se nenhum dos dois tiver jogo "vale" no momento
da captura, o script salva só as telas de hero (não dependem de pick) e
termina com código de saída 1 — não fabrica card nenhum.

## Mudanças no script nesta rodada

- **Fix B:** antes do print de `table#mercados`, mede `rect.bottom` e
  redimensiona a viewport (`Math.ceil(rect.bottom + 16)`) até caber o
  rodapé da tabela — elimina o clip do CDP que devolvia bloco navy sólido.
- **Fix C:** troca o `waitForTimeout(1500)` fixo do hero por uma corrida
  (`Promise.race`) entre `waitForSelector("article")` e `waitForFunction`
  do texto `HERO.semTalao`, até 30s; loga o ramo vencido e os segundos
  decorridos desde o `goto`.
