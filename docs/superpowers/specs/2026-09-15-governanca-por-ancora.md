# Governança por âncora — janela de reversão que enche e teto de deriva

**Data:** 2026-09-15
**Regra:** `REGRAS_ATIVAS` #253
**Relacionado:** #248 (camada de calibragem), #252-c (amostra só pré-apito), proibição 16

## 1. Objetivo e contexto

A reversão da camada #248 nunca disparou em produção. Medido em `calibragem_versoes`
(Corners, célula-família):

```
ciclo      versao  status     a       b
09-10 23:02   1   encurtada  0.0515  1.0527
09-11 02:46   2   encurtada  0.1050  1.1091
...           ...  (2pp por ciclo, 10 ciclos seguidos)
09-13 23:03  10   encurtada  0.6303  1.7250
09-14 01:29  11   revertida  0       1        (restauração manual)
```

Duas causas, as duas no desenho:

1. **A janela zera a cada ciclo.** `janela_de_reversao(picks, vigente.criada_em)`: toda célula
   encurtada gera versão nova, então `criada_em` é sempre o cron anterior (≤ 8h). A janela é **por
   célula de liga** (o estimador cria célula própria para toda liga da amostra; a célula-família não
   serve nenhum pick hoje). Medido na amostra pré-apito (221 jogos em 11,1 dias, 20 ligas): de 0,27
   a 3,62 jogos por dia por liga. Nenhuma liga junta 20 jogos em 8h.
2. **Não há teto acumulado.** A trava limita 2pp **por ciclo**; nada limita a soma. 10 ciclos = até
   20pp antes de qualquer julgamento fora da amostra.

## 2. Rastreabilidade (origem → destino)

| Dado | Produtor | Intermediário | Consumidor |
|---|---|---|---|
| `publicado_em` do pick | `prediction_ledger.published_at` | `repositorio.carregar_amostra` → `Pick.publicado_em` | janela |
| histórico de vigência | `gravar_ciclo` (cópias `vigente`, depois `substituida`) | `repositorio.carregar_historico` (novo) | `governanca.curva_servida` |
| âncora | linhas `ancorada`/`revertida` de `calibragem_versoes` | `repositorio.ancoras_do_historico` (pura) | `ciclo.planejar` |

O histórico `vigente`/`substituida` existe desde o primeiro ciclo (medido acima). O serving lê a
vigente com TTL de 300 s (`CALIBRAGEM_TTL_S`): um pick publicado até 5 min depois de uma troca pode
ter sido servido pela versão anterior. Aceito e documentado — a troca acontece no cron, fora do pico.

## 3. Desenho

**Âncora** (`repositorio.ancoras_do_historico(linhas)`, função pura sobre as linhas da tabela):
- última linha da célula com status `ancorada` ou `revertida` → âncora = seus `(a, b)`,
  `desde` = seu `criada_em`;
- sem nenhuma → âncora `(0, 1)`, `desde` = `criada_em` da **primeira** linha da célula
  (o instante em que a camada começou a decidir sobre ela);
- célula sem linha nenhuma → `(0, 1)`, `desde = None` (janela vazia).

**Curva servida** (`governanca.curva_servida(historico, instante)`): o `(a, b)` da última cópia
`vigente`/`substituida` com `criada_em < instante`; nenhuma → `(0, 1)`.

**Reversão** (`governanca.avaliar_reversao(janela, historico, ancora, vigente, reversoes_seguidas)`):

| condição | ação |
|---|---|
| janela < 20 jogos | `manter` (motivo com o nº de jogos) |
| Brier(servido) > Brier(âncora) e reversões seguidas ≥ 1 | `congelar` |
| Brier(servido) > Brier(âncora) | `reverter` → grava a âncora como `revertida` |
| Brier(servido) ≤ Brier(âncora) e vigente ≠ âncora | `ancorar` → linha `ancorada` com os `(a, b)` da vigente |
| Brier(servido) ≤ Brier(âncora) e vigente = âncora | `manter` |

Brier(servido): cada pick com `aplicar(p_legado, curva_servida(historico, pick.publicado_em))`.
Brier(âncora): `aplicar(p_legado, âncora)`. Mesmos picks, mesmos desfechos.

**Teto** (`governanca.avaliar_proposta(..., ancora=, teto=TETO_DERIVA_PP)`): a proposta é encurtada
até satisfazer **as duas** restrições — `distancia_maxima(vigente, final) ≤ limite` e
`distancia_maxima(âncora, final) ≤ teto`. Bissecção sobre o segmento vigente→proposta mantendo
sempre um ponto viável (`t = 0` é viável porque a vigente já respeita o teto). Sem movimento possível
→ status `inalterada`, motivo `teto de deriva`. `inalterada` não é promovida, então **não cria versão
nova** e não mexe na janela.

**Reversões seguidas:** conta `revertida` da mais recente para trás; **só `ancorada` zera**.
`adotada`/`encurtada` passam a ser ignoradas: com versões girando todo ciclo, movimento não é
validação — se zerassem, sempre haveria uma `adotada` entre duas reversões e o congelamento nunca
chegaria (a mesma forma do defeito da janela). `ancorada` entra em `STATUS_DE_DECISAO`/
`STATUS_VALIDOS` e não é promovida: a vigente não muda.

**Uma leitura por ciclo:** `planejar` lê o histórico inteiro uma vez (`carregar_historico`) e deriva
âncora, vigência, último status e reversões seguidas por funções puras
(`ancoras_do_historico`, `vigencia_do_historico`, `ultimo_status_do_historico`,
`reversoes_seguidas_do_historico`). A promoção de `gravar_ciclo` sai de
`operacoes_de_gravacao(linhas)`, o mesmo plano que a simulação multi-ciclo dos testes executa em
memória — o teste roda a regra de produção, não uma cópia.

Removidos: `repositorio.carregar_anterior` — a reversão volta para a âncora, não para a versão
imediatamente anterior (a anterior de uma sequência de encurtamentos é quase a mesma curva) — e as
versões SQL de `ultimo_status_de_ciclo`/`contar_reversoes_seguidas`, substituídas pelas funções
puras sobre o histórico.

## 4. Critérios de aceite

1. Replay do formato de produção (proposta distante, 10 ciclos, janela sem jogos): distância
   vigente↔âncora ≤ 0,04 (+ tolerância da grade) em todo ciclo; a governança antiga passa de 0,15.
2. Versões girando todo ciclo, 5 jogos novos por ciclo, curva servida pior: a reversão dispara no
   ciclo em que a janela chega a 20 jogos; a janela antiga (`criada_em` da vigente) teria 5.
3. Curva servida melhor: linha `ancorada`; no ciclo seguinte o teto é medido a partir da nova âncora.
4. Duas reversões seguidas com versões girando: `congelada`, e continua congelada.
5. `ensaio_calibragem.py` roda sobre o banco real sem escrever.

## 5. Bordas

- Pick sem `publicado_em`: fora da janela (como hoje).
- `publicado_em` e `criada_em` incomparáveis (fuso): fora da janela, com log.
- Célula congelada: nada é avaliado (congelamento pegajoso preservado).
- Âncora `revertida` antiga com `(a, b)` nulos: tratada como `(0, 1)`.

## 6. Contratos de saída (Etapa 2-bis)

Escrito: linhas de `calibragem_versoes` com o status novo `ancorada`. Leitores:

| Leitor | Filtra por | Efeito |
|---|---|---|
| `carregar_vigentes` / serving / `limiares_por_familia` | `status = 'vigente'` | nenhum: `ancorada` não é promovida |
| `ultimo_status_do_historico` | `STATUS_DE_DECISAO` | passa a enxergar `ancorada` (não congela) |
| contagem de reversões seguidas | `revertida`/`ancorada` | `ancorada` **zera**; `adotada`/`encurtada` deixam de zerar |
| índice único `idx_calibragem_vigente_unico` | `status = 'vigente'` | nenhum |
| `scripts/ensaio_calibragem.py` | usa `planejar` | contadores ganham `ancoradas` |

Nenhum leitor fora de `backend/modeling/calibragem/` e do ensaio (varredura por
`calibragem_versoes`, `carregar_anterior`, `STATUS_*`).

## 7. Efeito acumulado (Etapa 5)

Premissas medidas: 3 ciclos/dia; jogos pré-apito com desfecho **por liga** (a janela é por célula
de liga): mls 3,62/dia, brasileirao-serie-b 1,90/dia, mediana ≈ 1,0/dia, bundesliga 0,27/dia.

| horizonte | antes (#248) | depois (#253) |
|---|---|---|
| 1 ciclo | ≤ 2pp da vigente | ≤ 2pp da vigente **e** ≤ 4pp da âncora |
| 10 ciclos (~3,3 dias) | até 20pp; janela com 0 jogos | ≤ 4pp da âncora em toda célula. **Nenhuma** das 20 ligas junta 20 jogos: nenhuma é julgada — o teto é a única rede ativa |
| 100 ciclos (~33 dias) | até a saturação da sigmoide; nunca julgada | ≤ 4pp da âncora vigente. 14 de 20 ligas juntam 20 jogos e são julgadas ao menos uma vez (mls a cada ~17 ciclos); 6 ligas (pro-league, ligue-1, superliga, 2-bundesliga, premiership, bundesliga) seguem sem julgamento, presas no teto |

Leitura: o desenho **não** faz a reversão chegar rápido; faz ela **poder** chegar (a janela deixa de
zerar) e limita o dano enquanto não chega. O pior caso por célula passa de ilimitado para 4pp da
última curva validada. Julgar mais cedo exigiria somar jogos entre ligas da mesma família — fora do
escopo deste item.

**Redes de segurança e prova de disparo** (critérios 1–4, forçados em teste,
`tests/calibragem/test_15_governanca_por_ancora.py`): teto de deriva (para), reversão para a âncora
(desfaz), congelamento após duas reversões sem validação (trava para humano).

**Isto não liga a camada.** `CALIBRAGEM_ENABLED` segue `false`; ligar é decisão separada.

---

## 8. Emenda #253-a — julgamento por família

### 8.1 Motivo
A janela por célula de liga (§7) não junta 20 jogos em 10 ciclos em nenhuma das 20 ligas. Somando as
ligas da família, sobre as publicações reais de 09-03 a 09-14 (28 inícios de janela a cada 8h):
**mediana 5,5 ciclos, p90 10, máximo 11** até 20 jogos.

### 8.2 Desenho
`governanca.julgar_familia(janela, vigencia, ancoras, vigentes, reversoes_seguidas)` substitui
`avaliar_reversao`. Entradas por célula da família: `vigencia[(f, l)]`, `ancoras[(f, l)]`,
`vigentes[(f, l)]`.

- **Curva servida do pick** (`governanca.curva_servida_do_pick`): última cópia vigente da célula
  `(f, liga do pick)` com `criada_em < publicado_em`; sem ela, a da célula `(f, "")`; sem ela, `(0, 1)`.
  É a ordem de `curva.aplicar_versao` (`parametros.get((f, l)) or parametros.get((f, ""))`).
- **Âncora do pick** (`governanca.ancora_do_pick`): `ancoras[(f, liga)]`, senão `ancoras[(f, "")]`,
  senão `(0, 1)`.
- **Janela:** picks da família com `publicado_em > desde`, `desde` = âncora de `(f, "")`; sem histórico
  dela, o `desde` mais recente entre as células da família; nenhum → vazia.
- **Veredito:** < 20 jogos → `manter`. Servido pior → `reverter` (ou `congelar` com reversões seguidas
  da família ≥ 1, contadas na célula `(f, "")`). Não pior e alguma célula vigente ≠ sua âncora →
  `ancorar`. Senão `manter`.
- **Aplicação** (`ciclo.planejar`): o veredito ≠ `manter` gera linha para **todas** as células da
  família — as do ajuste e as vigentes fora dele (`n_jogos=0`, `origem="julgamento-familia"`).
  Congelamento pegajoso por célula continua. `manter` → `avaliar_proposta` por célula, com teto contra a
  própria âncora.

### 8.3 Critérios de aceite
1. 5 ligas, 1 jogo por liga por ciclo, servida pior: a família reverte no ciclo 5, todas as células; o
   controle por liga teria 4 jogos.
2. Mesmo cenário, servida melhor: todas `ancorada` no ciclo 5.
3. Servida pior por 9 ciclos: `revertida` no 5, `congelada` em todas no 9.
4. Pick publicado antes de a liga ter vigente própria é pontuado pela curva da família.
5. Célula vigente fora do ajuste também reverte.
6. Teto de 4pp por célula continua valendo em todo ciclo.

### 8.4 Efeito acumulado (Etapa 5)
| horizonte | #253 (por liga) | #253-a (por família) |
|---|---|---|
| 1 ciclo | ≤ 2pp; ≤ 4pp da âncora | igual |
| 10 ciclos | nenhuma liga julgada; teto é a única rede | cada família julgada ao menos uma vez em 90% dos inícios medidos (p90 = 10 ciclos) |
| 100 ciclos | 14/20 ligas julgadas ≥ 1 vez | uma janela nova a cada ~5,5 ciclos: ~18 julgamentos por família; cada `ancorada` move a âncora ≤ 4pp e exige 20 jogos novos sem perder |

Redes provadas em teste forçado: teto (para), reversão da família (desfaz), congelamento da família
(trava para humano).

### 8.5 Contratos de saída (Etapa 2-bis)
Mesmos status do #253; muda **quantas** linhas um veredito escreve (todas as células da família). Os
leitores (`carregar_vigentes`, serving, `limiares_por_familia`, ensaio) não mudam de contrato.
`avaliar_reversao` sai do código (sem chamador em produção).
