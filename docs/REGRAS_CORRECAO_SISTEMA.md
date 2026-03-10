# Registro de Correções de Regras do Sistema

> **Objetivo:** Este arquivo documenta correções aplicadas ao sistema que devem ser consultadas quando erros semelhantes ocorrerem. Cada entrada descreve o problema, a causa raiz e as camadas de correção implementadas.

---

## 001 — Defesa contra odds alucinadas pela Mistral

**Data:** 2026-03-10
**Arquivos afetados:** `backend/services/mistral_analysis.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

O prompt da Mistral só passava 5 odds básicas (Casa, Empate, Fora, Over 2.5, BTTS Sim), mas não incluía Under 4.5 nem muitos outros mercados. A instrução dizia para "recomendar com mercado e odd" sem restringir às odds reais. Resultado: a IA inventava odds — ex: "Under 4.5 @1.95" — odd que não existia no mercado.

### Causa raiz

Falta de restrição no prompt + ausência de validação pós-processamento. A Mistral gerava recomendações com odds arbitrárias porque não havia constraint nem verificação.

### Correções aplicadas (3 camadas)

1. **Prompt expandido** — Agora passa 10 mercados de odds (Over 1.5–4.5, Under 2.5, BTTS Sim/Não) + instrução explícita: _"NAO invente odds que não estejam listadas"_.

2. **Instrução rígida no prompt** — _"A odd na recomendação DEVE ser uma das odds listadas em ODDS DO MERCADO. Se a odd de um mercado é N/A, NAO recomende esse mercado."_

3. **Validação pós-processamento** — Novo método `_validate_recommendation_odd()` que:
   - Extrai a odd da recomendação (ex: `@1.95`)
   - Compara com todas as odds reais (tolerância ±0.02)
   - Se encontra match → mantém
   - Se o mercado existe mas odd está errada → substitui pela odd real
   - Se o mercado não tem odd disponível → remove a odd falsa

### Lição aprendida

Nunca confiar que um LLM vai respeitar constraints implícitos. Sempre aplicar **defesa em profundidade**: instrução clara no prompt + validação programática na saída. Conforme a regra de investigação do projeto (CLAUDE.md), implementar guards em cada camada relevante.

---

<!-- Novas correções devem ser adicionadas abaixo, seguindo o mesmo formato -->
