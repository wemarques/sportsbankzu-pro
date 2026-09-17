# Rodada 2 do teste de 5s — material capturado

**Capturado em:** 2026-09-17, contra o produto construído real (`next build`
+ `next start`, porta 3001), `PY_BACKEND_URL` apontado para a Lambda Function
URL de produção (nunca o API Gateway — regra #114/#203). Dados reais, sem
stub.

**Jogo "vale" encontrado:** `hoje` não tinha nenhum card em estado "vale" no
momento da captura; `amanha` tinha um — **Monza × Sassuolo (Serie A)**, pick
BTTS — SIM, paga 1,67 (mínimo 1,53). O script tentou `hoje` primeiro,
registrou a ausência e seguiu para `amanha` sem fabricar nada.

**Arquivos (6 PNGs, 3 telas × 2 viewports):**
- `tela-1-talao-mobile.png` / `tela-1-talao-desktop.png` — objeto de decisão (card "vale" em `/jogos?dia=amanha`)
- `tela-2-tabela-mobile.png` / `tela-2-tabela-desktop.png` — objeto de rigor (tabela de mercados no detalhe do jogo)
- `tela-3-hero-mobile.png` / `tela-3-hero-desktop.png` — compreensão (`/`, primeira visita, sem cookies)

Viewports: celular 390×844, desktop 1440×900.

**Reproduzir:** `node scripts/capturar-telas-teste-5s.mjs --base=http://localhost:3001`
a partir de `frontend/next`, com o servidor de produção de pé na porta 3001.
Use `--dia=hoje` ou `--dia=amanha` para fixar um dia; sem a flag, o script
tenta os dois antes de desistir. Se nenhum dos dois tiver jogo "vale" no
momento da captura, o script salva só as telas de hero (não dependem de
pick) e termina com código de saída 1 — não fabrica card nenhum.
