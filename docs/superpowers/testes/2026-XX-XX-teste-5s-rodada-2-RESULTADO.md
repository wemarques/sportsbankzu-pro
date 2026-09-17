# Teste de 5 segundos — rodada 2 (produto construído)

**Contexto.** A rodada 1 foi dispensada pelo dono por indisponibilidade de
participantes humanos — nada foi simulado nem inventado no lugar dela
(REGISTRO #254-b). Esta é, portanto, a **validação humana integral** e o
**portão de corte** de `/jogos` como rota padrão e da remoção do legado
(spec §7, #254-b): sem os critérios abaixo atingidos nos três itens, o corte
não acontece.

**Critério pré-registrado (spec §7, mesmo da rodada 1):** acerto >= 80% por
perfil e tempo mediano <= 5 s no objeto de decisão (tela 1, o talão).

**Regra de apuração pré-registrada pelo dono (2026-09-17, antes das sessões):**
- Acerto do item 1 = mercado E mínimo corretos (pergunta composta; meio acerto não conta).
- Passa por perfil: acertos ≥ ceil(0,8 · n) — n=4 exige 4/4; n=5, 4; n=6, 5 — E mediana dos tempos do item 1 ≤ 5 s.
- Os dois perfis precisam passar para o corte.
- Item 3 entra relatado (entendeu / não entendeu por pessoa), sem número de corte.
- Item 2: síntese qualitativa por perfil, uma linha cada, no #257-a.


**Telas usadas** (`rodada-2-telas/`, capturadas do produto construído, não
mockup):
- `tela-1-talao-{mobile,desktop}.png` — objeto de decisão (card "vale" em `/jogos`)
- `tela-2-tabela-{mobile,desktop}.png` — objeto de rigor (tabela de mercados no detalhe)
- `tela-3-hero-{mobile,desktop}.png` — compreensão (`/`, primeira visita, hero)

## Item 1 — Objeto de decisão (tela 1, talão)

Mostrar a tela por 5 s, perguntar: "qual mercado e qual odd mínima?"

### Perfil casual (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%) · **Tempo mediano:** __ s

### Perfil analítico (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%) · **Tempo mediano:** __ s

## Item 2 — Objeto de rigor (tela 2, tabela de mercados)

Mostrar a tela por 5 s, perguntar o que a pessoa entendeu da tabela
(mercados avaliados, qual "vale", por quê). Registro qualitativo — sem
critério numérico pré-registrado para este item.

| # | Perfil | O que entendeu (resumo) | Confiança (1-5) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |

## Item 3 — Compreensão do hero (tela 3, `/`, primeira visita)

Mostrar a tela por 5 s, perguntar: "o que o painel faz, em uma frase?".
Marcar **entendeu** / **não entendeu** por pessoa (julgamento do dono sobre
a resposta livre, sem gabarito fechado).

### Perfil casual (4-6 pessoas)

| # | Entendeu? (sim/não) | Resposta (resumo) | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%)

### Perfil analítico (4-6 pessoas)

| # | Entendeu? (sim/não) | Resposta (resumo) | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%)

## Veredito

- [ ] Critério pré-registrado atingido nos dois perfis no item 1 (>= 80%
      acerto, <= 5s mediana) **e** compreensão do hero (item 3) satisfatória
      — corte de `/jogos` como padrão e remoção do legado liberados.
- [ ] Critério NÃO atingido em algum item — abrir uma entrada nova no
      REGISTRO com o que precisa mudar (tela 1, tela 2 e/ou hero) ANTES de
      fechar a fase 6. O corte fica bloqueado até nova rodada.

Preenchido por: __________ em __________.
