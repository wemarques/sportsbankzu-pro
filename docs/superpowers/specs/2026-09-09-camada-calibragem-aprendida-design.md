# Camada de calibragem aprendida — design

**Data:** 2026-09-09
**Autor:** sessão de brainstorming com Welligton
**Status:** design aprovado; plano de implementação ainda não escrito
**Relacionado:** #244 (a publicada não é probabilidade), #245 (a deflação piora as seis famílias), #246-a (corredor por probabilidade), #230-a (pré-registro de gate), #200 (audit_results vazado), #079 (MIN_N_BRIER), #011 (classificação usa raw, EV usa deflacionada)

---

## 1. Problema

A probabilidade publicada está sistematicamente abaixo da frequência real. Medido no
`prediction_ledger` × `ledger_outcomes` — fonte pré-jogo, sem vazamento — sobre 18.378
previsões em 220 jogos: **erro médio ponderado de −10,2 pontos**. Nos extremos chega a
−29,5 (`Corners Over 5.5`: real 91,3%, publicada 61,8%).

A causa está isolada (#244, #245): `apply_probability_deflation` multiplica por um fator que
cai conforme a probabilidade sobe (0,95 em 55%; 0,75 em 85%) e encolhe as **duas** pontas de
um par complementar. Pares de escanteio somam 100,0% no raw e 76,8–86,3% depois. Medido em
grade de intensidade por família, o melhor fator é **zero em cinco das seis famílias** — o
redutor não está mal repartido, está errado em todas, em graus diferentes.

O redutor é fixo, global e não aprende. Este documento especifica a camada que o substitui.

## 2. Decisões tomadas, com a razão

| # | Decisão | Razão |
|---|---|---|
| D1 | A camada aprende a **correção do que o motor produz**, não a previsão do zero | Com 220 jogos limpos, um preditor completo aprenderia ruído. A correção tem poucos parâmetros e ataca o erro já medido. |
| D2 | Atualização **automática, com trava de passo e reversão** | Aprende continuamente sem poder dar um salto errado. Cada mudança vira linha auditável. |
| D3 | Recorte **por família, com a liga ganhando autonomia conforme a amostra** | Hoje se comporta como "uma curva por família"; conforme os dados chegam, ligas com histórico próprio se descolam sozinhas. É o mecanismo literal de "se aperfeiçoar à medida que recebe dados". |
| D4 | Os **limiares são re-derivados junto**, mantendo o volume publicado constante | Sem isso, a mudança de calibração e a de volume se misturam e a próxima medição fica ilegível. Medido: com a probabilidade corrigida, os picks de EV positivo vão de 13,8% para 25,2% (1,8×; Double Chance de 2 para 41). |
| D5 | A curva é **semeada pelo backfill com peso que decai** | Dá sinal desde o primeiro dia; o backfill perde peso sozinho conforme o ledger cresce. |
| D6 | Forma da função: **dois parâmetros no espaço do logit** | É o que 220 jogos sustentam; é monótono por construção; a trava e a reversão ficam triviais; é legível. |

## 3. O modelo

Para um pick com probabilidade `p` saindo do motor, família `f`, liga `l`:

```
logit(p_corrigida) = a[f,l] + b[f,l] · logit(p)
```

Ajuste por regressão logística ponderada, com `logit(p)` como único regressor e o desfecho
`0/1` do `ledger_outcomes` como alvo. Escalonamento de Platt, uma célula por vez.

- **`a`** é o deslocamento sistemático. Positivo = o motor publica abaixo da realidade.
- **`b`** é a dispersão. `b < 1` = o motor exagera nos extremos; `b > 1` = encolhe demais.

A deflação atual é um `b` fixo e escondido, igual para todos. Aqui ele é medido, por família,
e se move.

**Entrada:** `prediction_ledger.raw_prob`. Não `iso_prob` — medido que `iso == raw` em 100%
das 19.772 linhas, o passo isotônico do #216 nunca produziu nada. Ele sai junto com as
bandas; fica **um** passo de calibração, não dois sendo um deles morto.

### 3.1 Encolhimento hierárquico

Três níveis: global → família → liga.

```
peso      = n_efetivo / (n_efetivo + k)
θ_célula  = peso · θ̂_própria + (1 − peso) · θ_pai
```

**`n_efetivo` conta JOGOS, não picks.** Escanteios têm 7.299 picks em 220 jogos; `Over 2.5` e
`BTTS` do mesmo jogo dividem o mesmo placar e não são observações independentes. Contar picks
daria autonomia quase total à célula em cima de 220 jogos de informação real.

Esta é a mesma classe de erro de todos os defeitos medidos nesta sessão: o #243 comparou odd
em escala errada, o #244 leu calibração numa fonte recomputada pós-jogo, o #196 pareou
desfechos de jogos diferentes. Todos foram contagem indevida. O bootstrap por bloco-jogo usado
em todas as medições é a mesma decisão, e ela precisa estar **dentro do estimador**, não só
nos relatórios.

`k` — quantos jogos uma célula precisa para valer tanto quanto o pai — é a razão entre a
variância da estimativa dentro da célula e a variância entre células, estimada dos próprios
dados. Com menos de 5 células com amostra acima do piso, essa razão não é estimável e `k` cai
em **40 jogos** — o dobro do piso de decisão do #079, ou seja, uma célula precisa do dobro do
mínimo para valer tanto quanto o pai. O fato de ter caído no valor fixo fica gravado na linha
da versão.

### 3.2 Semente do backfill

A semente entra como amostra na mesma média ponderada:

```
θ_família = (n_ledger · θ̂_ledger + n_prior · θ_backfill) / (n_ledger + n_prior)
```

O decaimento é a própria aritmética: conforme `n_ledger` cresce, o backfill perde peso. Não há
segundo mecanismo a manter.

`n_prior` **não** é 8.403 (o número de jogos do backfill). O backfill é uma reconstrução, e o
que ele reconstrói nunca foi publicado a ninguém. `n_prior` é medido assim:

```
concordancia = fração dos picks sobrepostos (mesmo jogo, mercado, seleção) em que a
               probabilidade do backfill está a menos de 2 pontos da publicada no ledger
n_prior      = 150 · concordancia          (teto de 150 jogos, piso de 0)
```

O teto de 150 é deliberadamente uma fração pequena dos 8.403 jogos do backfill: mesmo com
concordância perfeita, a semente vale menos que o ledger vai valer em poucos meses. Se a
sobreposição tiver menos de 30 picks, `concordancia` não é estimável e `n_prior = 75` (metade
do teto), registrado como `semente_nao_validada`. Nada bloqueia — a semente entra de qualquer
forma; a medição decide só quanto ela vale.

### 3.3 Guardas dentro do estimador

- **`b > 0` obrigatório.** `b ≤ 0` inverteria a ordem das probabilidades, e a regra do corredor
  (#246-a) decide por ordem. Célula com `b` não positivo é marcada rejeitada e usa o pai. O
  estimador sinaliza; quem decide é a governança.
- **Sem peso por recência.** Descontar jogo antigo é natural, mas com 220 jogos joga fora
  amostra que não sobra. Gancho explícito para quando uma família passar de mil jogos.
- **Só ledger pré-jogo.** `audit_results` é proibido como fonte de calibração pela regra #244,
  e o repositório não tem sequer caminho de código para ele.

## 4. Arquitetura

Pacote novo `backend/modeling/calibragem/`:

| módulo | responsabilidade | depende de |
|---|---|---|
| `curva.py` | `aplicar(p_raw, a, b) -> p_corrigida`. Só a matemática do logit. | nada |
| `estimador.py` | Recebe `(p_raw, desfecho, família, liga)` e devolve `(a, b)` por célula com o encolhimento. | `curva` |
| `repositorio.py` | Lê a amostra do ledger; lê e grava versões dos parâmetros. | banco |
| `governanca.py` | Decide se um `(a, b)` proposto pode ser adotado: trava, piso, reversão. | nada |

**Fronteira:** o estimador nunca toca o banco, o repositório nunca faz conta, a governança
nunca ajusta. Cada um testável sozinho. É o oposto de `_calibrar_com_detalhe`, que hoje faz
busca no banco, matemática e política de produto na mesma função.

### 4.1 Persistência

Tabela nova `calibragem_versoes`: uma linha por `(família, liga, versão)` com `a`, `b`,
`n_jogos`, `brier_validacao`, `origem` (semente ou ledger), `status` (vigente | revertida |
rejeitada | abaixo_do_piso | encurtada | inalterada), `fator_encurtamento`, `criada_em`,
`motivo`.

**Não** reusar a tabela `corrections`: é um log de escalares sem versionamento e sem histórico
de reversão. O #247 mostrou o resultado — `corner_multiplier = 0,238` gravado em 36 ligas, um
valor fora da grade `[0,75 … 1,10]`, vivo há meses sem ninguém ver.

### 4.2 Pontos de contato

**Leitura:** `_calibrar_com_detalhe` em `ev_classification.py` passa a ter um único caminho,
`curva.aplicar(...)`. A pilha de hoje — `_band_deflation`, `_league_deflation_factor`, a
meia-banda de BTTS (#152), a de gols (#165-e) e a penalidade extra de Under 2.5 (#113) — sai de
`ev_classification` e vai inteira para `calibragem/legado.py`, congelada, com um único chamador:
`curva.aplicar` quando a célula ainda está na versão 0 (Seção 6.1). Nenhuma flag, nenhum segundo
caminho vivo — conviver com dois regimes de deflação é o defeito que o #244 mediu. `legado.py` é
apagado quando nenhuma célula referenciar mais a versão 0.

**Escrita:** etapa nova no `cron_handler`, depois de `registrar_desfechos_do_jogo`. Carrega a
amostra, ajusta, submete à governança, grava a versão.

### 4.3 Fora de escopo

A deflação de λ no `poisson_matrix` (`lambda_multiplier`, `btts_multiplier`) fica onde está —
é upstream e molda o `raw` que a camada recebe; o parâmetro `a` absorve o efeito residual. O
motor de escanteios, o filtro de corredor (#246-a) e os limiares de probabilidade
(`safe_prob`, `neutro_prob`) também não são tocados.

## 5. Governança

### 5.1 Trava, expressa em pontos de probabilidade

Limitar `a` e `b` separadamente é difícil de raciocinar: o mesmo `Δa` move pouco no meio da
escala e muito nas pontas. A trava é definida na saída:

> Entre a versão vigente e a proposta, nenhum pick pode mudar mais que **2 pontos de
> probabilidade**, medido como `max |curva_nova(p) − curva_vigente(p)|` para `p ∈ [0,02; 0,98]`.

Proposta que ultrapassa não é rejeitada: é **encurtada** ao longo do segmento entre vigente e
proposta até caber, e o fator de encurtamento fica gravado. Célula encurtada em rodadas
seguidas está dizendo que a correção é grande e o sistema caminha até lá devagar — que é o
comportamento certo, e visível.

### 5.2 Piso de amostra

Célula com menos de **20 jogos** com desfecho não tem `(a, b)` próprio: usa o pai e registra
`abaixo_do_piso`. Reusa `MIN_N_BRIER = 20`, a constante que o #079 já adota para "não decide".
Acima do piso, o encolhimento assume e a transição é suave.

### 5.3 Reversão, fora da amostra por construção

Os jogos que uma versão avalia são **os que ela serviu**. Uma versão adotada no ciclo *t*
publica; os jogos liquidados até *t+1* nunca fizeram parte do ajuste dela. No ciclo seguinte,
por célula:

- Brier do que a vigente **realmente publicou** nesses jogos;
- Brier do que a anterior **teria publicado** neles.

Vigente pior → revertida. É a disciplina do #230-a por ciclo, sem infraestrutura extra — o
ledger já grava o que foi publicado.

Reverte pelo **ponto**, exigindo ≥ 20 jogos na janela, sem esperar o IC excluir zero. A
assimetria justifica: reversão falsa volta para uma versão já validada, custo quase zero;
reversão que não acontece deixa uma versão ruim publicando por mais um ciclo.

**Anti-oscilação:** após uma reversão, o limite de passo daquela célula cai pela metade; **duas
reversões seguidas congelam a célula** no pai e emitem alerta para revisão humana. Célula que
não melhora em duas tentativas não tem problema de passo, tem problema de modelo.

### 5.4 Nada em silêncio

Todo ciclo grava **uma linha por célula, sempre** — adotada, encurtada, rejeitada, abaixo do
piso, revertida, ou inalterada por falta de dado novo — mais uma linha de resumo no log.

Não é zelo genérico. O #247 achou um gate (`odds_value_added < −0,015`) que **nunca disparou em
33 ligas** e ninguém sabia. O #246 só encontrou o filtro de corredor porque `[CORRIDOR-DROPPED]`
vazou no log de um teste. Um sistema que muda o número sozinho e só registra quando muda é um
sistema onde a inação é invisível.

### 5.5 Limiares re-derivados

A classificação usa prob **raw** (proibição 11), então `safe_prob` e `neutro_prob` não se
movem. O volume sobe por `ev` e `edge`, que consomem a probabilidade corrigida. Em
`DEFAULT_THRESHOLDS`, por categoria: `safe_ev`, `neutro_ev`, `safe_edge`, `neutro_edge`.
`neutro_ev` está hoje em `0,00`, que é por que "EV positivo" e "publicado" são a mesma coisa.

A re-derivação é casamento de quantil: para cada família, os quatro valores que reproduzem,
sobre a mesma janela, a **mesma contagem de picks por classe** da versão anterior. O volume
fica constante por construção e passa a ser alavanca separada.

Curva e limiar mudam **juntos, na mesma versão e na mesma linha de auditoria**. Separá-los
recria a convivência de dois regimes que o #244 mediu.

## 6. Bordas e falhas

### 6.1 Dia zero

A versão 0 **não** é um `(a, b)` ajustado à curva atual: dois parâmetros no logit não
reproduzem exatamente a pilha de bandas, e um controle positivo com tolerância frouxa não vale
nada. A versão 0 é um **sentinela que significa "a curva legada"**, e a curva legada é a função
de hoje, movida sem alteração para `calibragem/legado.py`.

Isso mantém a promessa da Seção 4.2 — existe **um só** caminho de deflação vivo, `curva.aplicar`,
que para a versão 0 delega ao legado. Não são dois regimes convivendo; é um regime com um valor
inicial. `legado.py` nasce congelado (proibido editar) e é apagado quando nenhuma célula
referenciar mais a versão 0; um teste guarda essa transição.

No dia do deploy o painel publica **exatamente** o que publicava na véspera, e o controle
positivo do teste 1 é uma igualdade, não uma aproximação. A semente do backfill continua sendo
*prior da proposta*, não ponto de partida do publicado, e a trava de 2 pontos faz a caminhada
até lá levar várias rodadas — cada uma com auditoria e chance de reverter.

### 6.2 Regra de contagem no ledger

O `prediction_ledger` é append-only e guarda **várias gerações por jogo** (Toronto × Nashville
tem duas, 03:09 e 11:09, com números diferentes). Treinar em todas conta o mesmo jogo mais de
uma vez e dá mais peso aos jogos recomputados mais vezes.

**Regra: uma linha por `(jogo, mercado, seleção)`, a última geração antes do kickoff** — o que
o operador viu por último e o que a versão de fato publicou. Fica no repositório, junto com a
contagem por jogo.

### 6.3 Falhas

| situação | comportamento |
|---|---|
| Banco indisponível ao publicar | Snapshot dos parâmetros vigentes empacotado no deploy + cache TTL por liga (padrão do #231-a). **Nunca** cai para identidade. O payload sai **marcado** como servido do snapshot — o #238 mostrou o custo de fallback silencioso. |
| Família ou liga sem amostra | Cai no pai; o pai cai na versão 0. Sempre definido, sempre registrado de onde veio. |
| Mercado sem odd | A calibração não precisa de preço, só de `(p_raw, desfecho)` — cartões (88,3% sem odd) são calibrados normalmente. A **re-derivação de limiar** precisa de EV: onde quase não há preço, os limiares não se movem e a versão registra isso em vez de fingir que calculou. |
| Desfecho atrasado | O ciclo consome só o liquidado, e grava quantos jogos entraram — para distinguir "não fez nada por falta de dado" de "não fez nada por escolha". |
| Temporada nova / liga nova | A hierarquia resolve: poucos jogos, fica perto da família. |

## 7. Testes

| # | Teste | Protege |
|---|---|---|
| 1 | Versão 0 reproduz a produção com **igualdade exata** num payload real (delega ao legado) | A costura |
| 1b | Quando nenhuma célula está na versão 0, `legado.py` não tem chamador | A transição, para o legado não virar permanente |
| 2 | Dados sintéticos de um `(a, b)` conhecido são recuperados pelo estimador | Se não recupera o que gerou, não recupera o real |
| 3 | 1 jogo com 40 picks dá o mesmo peso que 1 jogo com 2 picks | `n_efetivo` em jogos |
| 4 | Proposta distante é encurtada; mudança ≤ 2 pp; fator gravado | A trava |
| 5 | Dois ciclos piores seguidos congelam a célula e alertam | Anti-oscilação |
| 6 | Contagem por classe após re-derivação bate com a anterior | Volume constante |
| 7 | A decisão do corredor num jogo real é idêntica com e sem a camada | Monotonicidade, e portanto #246-a |
| 8 | Um ciclo sobre fixture emite exatamente uma linha por célula | Nada em silêncio |
| 9 | O repositório não tem caminho de código para `audit_results` | Regra #244, no estilo do `test_225c_fallback_morto.py` |

Mais a prova empírica da proibição 14: Brier e erro de calibração numa janela retida, com e sem
a camada, antes de qualquer commit que a ligue.

## 8. Critério de fracasso, pré-registrado

Escrito antes de construir, pelo mesmo motivo do #230-a:

> **Se depois de seis ciclos o Brier fora da amostra da camada não for melhor que o da deflação
> atual, a camada é abandonada, não ajustada.**

Um sistema de aprendizado que precisa ser ajustado à mão para ganhar não está aprendendo — está
sendo dirigido, e aí a deflação fixa é mais honesta e mais barata.

## 9. Caminho de crescimento

Dois eixos, ambos medidos e nenhum opinado:

- **Mais dados por célula compram autonomia** — a liga se descola da família na proporção da
  própria amostra.
- **Resíduo estruturado compra flexibilidade** — se os resíduos por banda mostrarem padrão
  sistemático que `(a, b)` não captura, aquela família ganha uma curva livre (isotônica
  hierárquica) no lugar dos dois parâmetros.

Começar em dois parâmetros não fecha a porta da curva livre; define o critério para atravessá-la.
