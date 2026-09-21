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

**Ruling do dono que define a apuração (2026-09-21, verbatim):** As oito sessões da segunda remessa foram conduzidas com pessoas reais olhando as telas aprovadas. As duas sessões analíticas da primeira remessa ficam fora da apuração por terem sido feitas sobre jogos diferentes das telas do protocolo.

## Item 1 — Objeto de decisão (tela 1, talão)

Mostrar a tela por 5 s, perguntar: "qual mercado e qual odd mínima?"

### Perfil casual (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | sim | sim | 4,2 | 4 |
| 2 | não (Under 2.5) | não (1,59) | 3,2 | 5 |
| 3 | sim | sim | 3,6 | 4 |
| 4 | sim | sim | 4,1 | 3 |
| 5 | sim | sim | 4,4 | 4 |
| 6 | sim | sim | 4,8 | 5 |

**Acerto do perfil:** 5/6 (83%) · **Tempo mediano:** 4,15 s · exigido ceil(0,8·6)=5 → **passa**

### Perfil analítico (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | sim | sim | 2,9 | 5 |
| 2 | sim | sim | 3,4 | 4 |
| 3 | sim | sim | 3,9 | 4 |
| 4 | sim | sim | 4,6 | 5 |
| x1 | fora da apuração — jogo diferente (Udinese × Cagliari, Over 3.5 a 1,47): respondeu Under 3.5 | 1,55 | 3,2 | 4 |
| x2 | fora da apuração — jogo diferente (Tottenham × Aston Villa, Cartões Under 2.5 a 1,55): respondeu Cartões Over 2.5 | 1,55 | 2,2 | 4 |

**Acerto do perfil:** 4/4 (100%) · **Tempo mediano:** 3,65 s · exigido ceil(0,8·4)=4 → **passa** (com x1/x2 somados seria 4/6 com 5 exigidos; excluídos pelo ruling acima, por protocolo)

## Item 2 — Objeto de rigor (tela 2, tabela de mercados)

Mostrar a tela por 5 s, perguntar o que a pessoa entendeu da tabela
(mercados avaliados, qual "vale", por quê). Registro qualitativo — sem
critério numérico pré-registrado para este item.

| # | Perfil | O que entendeu (resumo) | Confiança (1-5) |
|---|---|---|---|
| 1 | casual | disponibiliza prognósticos para jogos de futebol | 4 |
| 2 | casual | apresenta palpites para jogos de futebol | 5 |
| 3 | casual | mostra quais opções de aposta têm valor | 4 |
| 4 | casual | compara as odds e indica a melhor opção | 3 |
| 5 | casual | diz se a aposta vale ou não vale | 4 |
| 6 | casual | lista de mercados com odds e uma recomendação | 5 |
| 7 | analítico | compara odd atual, odd justa e edge para classificar cada mercado | 5 |
| 8 | analítico | valor esperado e a decisão recomendada para cada linha | 4 |
| 9 | analítico | filtra mercados em que a odd oferecida supera a odd justa | 4 |
| 10 | analítico | hierarquiza oportunidades por valor e status de decisão | 5 |
| x1, x2 | analítico (fora da apuração) | "os cálculos não consideraram os dados históricos do campeonato, só métricas genéricas" | 4 |

## Item 3 — Compreensão do hero (tela 3, `/`, primeira visita)

Mostrar a tela por 5 s, perguntar: "o que o painel faz, em uma frase?".
Marcar **entendeu** / **não entendeu** por pessoa (julgamento do dono sobre
a resposta livre, sem gabarito fechado).

### Perfil casual (4-6 pessoas)

| # | Entendeu? (sim/não) | Resposta (resumo) | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1–6 | sim (6/6) | "o painel apresenta palpites/prognósticos para jogos de futebol"; 2 pessoas sentiram falta da situação dos times no campeonato | — | — |

**Acerto do perfil:** 6/6 (100%)

### Perfil analítico (4-6 pessoas)

| # | Entendeu? (sim/não) | Resposta (resumo) | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1–4 | sim (4/4) | "apresenta prognósticos para jogos de futebol" | — | — |
| x1, x2 | sim (fora da apuração) | idem, com a ressalva das "métricas genéricas" | — | — |

**Acerto do perfil:** 4/4 (100%)

## Veredito

- [x] Critério pré-registrado atingido nos dois perfis no item 1 (>= 80%
      acerto, <= 5s mediana) **e** compreensão do hero (item 3) satisfatória
      — corte de `/jogos` como padrão e remoção do legado liberados.
- [ ] Critério NÃO atingido em algum item — abrir uma entrada nova no
      REGISTRO com o que precisa mudar (tela 1, tela 2 e/ou hero) ANTES de
      fechar a fase 6. O corte fica bloqueado até nova rodada.

Preenchido por: Welligton (dono; sessões e ruling) e o controller (tabulação pela regra pré-registrada), em 2026-09-21. Nota do controller sobre a segunda remessa e a afirmação do dono: REGISTRO #257-a.
