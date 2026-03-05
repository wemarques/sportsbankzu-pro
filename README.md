# SportsBankZU Pro V3.5

> Sistema profissional de cálculo de prognósticos esportivos com backend FastAPI, frontend Streamlit, dashboard Next.js, placares ao vivo, auditoria contínua por IA e calibração de modelos

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red.svg)](https://streamlit.io/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Playwright](https://img.shields.io/badge/Playwright-E2E-green.svg)](https://playwright.dev/)

**Última revisão:** 2026-03-05

---

## 📊 Visão Geral

O **SportsBankZU Pro** é um sistema completo de análise e prognósticos esportivos que combina modelos estatísticos avançados com uma interface intuitiva e profissional.

---

## 📊 Status de Implementação

### Funcionalidades Ativas

- Backend FastAPI com endpoints REST
- Interface Streamlit com visualização de dados
- Quadro-Resumo Profissional formatado para compartilhamento
- Analise de Picks com multiplos mercados
- Graficos interativos de probabilidades
- Analise de Contexto com IA (Mistral)
- Auditoria continua com feedback loop completo (V3.1)
- Calibracao de probabilidades via Isotonic Regression (V3.1)
- Thresholds dinamicos de mercado ajustados pela auditoria (V3.1)
- Feedback loop para BTTS e escanteios com calibracao e correcoes automaticas (V3.2)
- Comparativo de times completo: cartoes, faltas, finalizacoes, chutes ao gol, posse (V3.2)
- Analise IA enriquecida com dados do comparativo de times (V3.2)
- Cobertura completa dos 5 leiautes CSV FootyStats: 186+442 team, 64 match, 49 league, 45+ player (V3.3)
- Perfil avancado por time: BTTS%, clean sheet%, FTS%, over 2.5%, xG for/against, posicao na liga (V3.3)
- Nova aba "Perfil" no dashboard com comparativo xG, vitorias, over 2.5, clean sheet, BTTS (V3.3)
- Dados de meio-tempo, timing de gols, cartoes por tempo, arbitro e publico (V3.3)
- Liga enriquecida: home advantage%, gols casa/fora, clean sheet%, over 2.5%, xG medio (V3.3)
- Geracao de relatorios automatizada
- Exportacao de dados (CSV, JSON, TXT)
- Filtros por liga e periodo
- Responsividade mobile/tablet (CSS customizado)
- Ordenação de jogos por horário (asc/desc) no dashboard (V3.3.1)
- Isolamento de erros por jogo/liga no backend — falha em um jogo não exclui os demais (V3.3.1)
- Placares ao vivo via FootyStats API com polling automatico a cada 60s (V3.4)
- Identificacao visual de jogos em andamento com badge "AO VIVO" pulsante e placar em destaque (V3.4)
- Endpoint `/live-scores` no backend com cache de 1 minuto para eficiencia de rate limit (V3.4)
- Recomendação de atualização do modelo na Auditoria da Rodada com diagnóstico, urgência e ações recomendadas (V3.4)
- Auditoria em lote instantânea no navegador (sem backend) com avaliação Mistral AI opcional (V3.4)
- Auto-refresh de JS desatualizado após deploys Vercel via comparação de buildId (V3.4)
- **Motor Safe Bets** com arquitetura de 3 camadas: League DNA (33 ligas), Risk Semaphore e Strategy Algorithms (V3.5)
- League DNA Matrix com categorização estática (DEFENSIVE/BALANCED/OFFENSIVE) e mercados habilitados por liga (V3.5)
- Estratégias Safe Bets: Under 3.5 Defensivo, BTTS Não, Safe Corners Over 9.5, Timing 2º Tempo (V3.5)
- Badge visual Safe Bets no dashboard com indicadores de risco (SAFE/MODERADO/NO BET) e tags por estratégia (V3.5)
- Cobertura expandida de 22 para 33 ligas monitoradas com DNA configurado (V3.5)
- Eliminação de placares falsos 0-0 que corrompiam métricas de auditoria — scores nulos agora propagados como `None` (V3.5.1)
- Endpoint `POST /api/ai/score-correction` para correção manual de resultados com re-auditoria (V3.5.1)
- Auditoria de duplas (combinadas INTRA e INTER) com taxa de acerto por tipo no cron batch audit (V3.5.1)
- Resultado visual de auditoria de duplas (ACERTOU/ERROU) com resumo de acurácia no painel de Auditoria da Rodada (V3.5.1)
- Fix status falso "AO VIVO" — guard de kickoff-time impede que jogos agendados apareçam como live (V3.5.1)
- Regra de Investigação Obrigatória adicionada ao `CLAUDE.md` — 7 passos de verificação antes de qualquer correção (V3.5.1)

### Dashboard Next.js (Produção)

- Dashboard em [sportsbankzu-pro-well.vercel.app](https://sportsbankzu-pro-well.vercel.app/dashboard)
- Seleção de ligas (33 europeias, asiáticas e sul-americanas)
- Aba Recomendadas 2026 com jogos de maior confiança
- Análise IA (Mistral) por jogo
- Favoritos com persistência em localStorage
- **Compartilhar via WhatsApp**: captura da tela e envio (Web Share API ou download + link)
- **Placares ao vivo**: atualizacao automatica de placares durante jogos em andamento com indicador visual
- **Auditoria da Rodada instantânea**: avaliação de picks (ACERTOU/ERROU) roda no navegador sem backend, com análise Mistral AI opcional

### Funcionalidades Opcionais

- Sistema de autenticacao (depende de config.yaml ou Secrets)
- CLI unificado (`python -m cli`) com Click
- Testes E2E com Playwright

### Como habilitar autenticacao

A autenticacao ja esta integrada no `app.py`. Para ativar:

1. Crie `config.yaml` localmente (na raiz) **ou** configure Secrets no Streamlit Cloud.
2. Garanta `PyYAML` instalado (ja incluso no `requirements.txt`).

---

### Arquitetura

O sistema é composto por três componentes principais que trabalham de forma integrada:

**Backend FastAPI** processa dados de jogos (CSVs locais ou fontes externas) e expõe endpoints REST com probabilidades para diferentes mercados (1X2, Over/Under, BTTS), valores de lambda (λ) e estatísticas detalhadas. O **Frontend Streamlit** consome a API do backend e apresenta os prognósticos em formato tabular e gráfico, incluindo o Quadro-Resumo Profissional formatado para compartilhamento. O **Dashboard Next.js** oferece uma interface moderna e responsiva com seleção de ligas, análise de jogos e visualização de picks recomendados.

### Funcionalidades Principais

O sistema oferece análise estatística baseada em modelos de Poisson, Expected Goals (xG) e lambda dinâmico. Gera prognósticos para múltiplos mercados incluindo Money Line, Over/Under, BTTS e Double Chance. O Quadro-Resumo Profissional apresenta mercados sugeridos, duplas e triplas SAFE com correlação controlada, além de regras de governança por regime de liga. Inclui sistema de autenticação com login e senha para controle de acesso, suporta múltiplas ligas europeias e internacionais, e permite deploy em Streamlit Cloud com configuração simplificada.

---

## 🔐 Sistema de Autenticação

O SportsBankZU Pro inclui um sistema de autenticacao opcional que protege o acesso ao sistema atraves de login com usuario e senha.

### Características

O sistema oferece autenticação baseada em usuário e senha com senhas criptografadas usando hash SHA-256. Suporta múltiplos usuários com credenciais individuais, mantém sessão ativa durante o uso, possui botão de logout na sidebar, e é compatível com Streamlit Cloud através de Secrets.

### Arquivos Necessários

Para implementar a autenticação, você precisará dos seguintes arquivos na raiz do projeto:

**auth.py** é o módulo principal de autenticação que gerencia login, logout e verificação de credenciais. **config.yaml** armazena as credenciais dos usuários com senhas em hash SHA-256. **gerar_hash_senha.py** (opcional) é um script auxiliar para gerar hash de novas senhas.

### Instalacao Rapida

A autenticacao ja esta integrada no `app.py`. Para ativar:

1. Crie o arquivo `config.yaml` na raiz do projeto **ou** configure Secrets no Streamlit Cloud.
2. Instale a dependencia `PyYAML` (ja incluso no `requirements.txt`).
3. Teste localmente com `streamlit run app.py`.

### Credenciais de Teste

O sistema vem pré-configurado com duas contas de teste:

| Usuário | Senha | Nome |
|---------|-------|------|
| `admin` | `admin` | Administrador |
| `usuario1` | `password` | Usuário Teste |

### Gerar Nova Senha

Para criar hash de uma nova senha, execute o script auxiliar:

```bash
python gerar_hash_senha.py
```

Digite sua senha quando solicitado e copie o hash gerado. Cole o hash no arquivo `config.yaml` no campo `password` do usuário correspondente.

---

## 🛠️ Pré-requisitos

Antes de iniciar, certifique-se de ter os seguintes requisitos instalados:

O sistema requer **Python 3.10 ou superior** com as bibliotecas FastAPI, Uvicorn, Pandas, Numpy, Streamlit e PyYAML. O **Backend FastAPI** deve estar acessível publicamente ou localmente em `http://localhost:5001`. Os **Secrets** devem estar configurados para o Streamlit com a variável `BACKEND_URL`. Para uso em produção, defina as variáveis de ambiente `FUTEBOL_ROOT` (ou `DATA_ROOT`) e/ou `FUTEBOL_DATA_DIR` no backend para apontar para o storage correto. Além disso, é necessário **Node.js 18 ou superior** para o dashboard Next.js.

---

## 🚀 Rodar Localmente

### 1. Backend FastAPI

Primeiro, inicie o servidor backend que processa os dados e expõe a API:

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install fastapi uvicorn pandas numpy

# Iniciar servidor
uvicorn backend.main:app --reload --port 5001
```

O backend estará disponível em `http://localhost:5001`.

### 2. Frontend Streamlit

Em seguida, inicie a interface Streamlit:

```bash
# Instalar dependências (incluindo autenticação)
pip install -r requirements.txt

# Configurar URL do backend
set BACKEND_URL=http://localhost:5001  # Windows
export BACKEND_URL=http://localhost:5001  # Linux/Mac

# Iniciar Streamlit
streamlit run app.py
```

Acesse a interface em `http://localhost:8501/`.

**Tela de Login:** Ao acessar, você verá a tela de autenticação. Use as credenciais de teste (`admin` / `admin`) para entrar.

### 3. Dashboard Next.js

Por fim, inicie o dashboard moderno:

```bash
cd frontend/next
npm install
npm run dev
```

Acesse o dashboard em `http://localhost:3000/dashboard`. Em produção: [sportsbankzu-pro-well.vercel.app/dashboard](https://sportsbankzu-pro-well.vercel.app/dashboard).

### 4. CLI (Linha de Comando)

O projeto inclui uma CLI unificada construída com Click:

```bash
# Ajuda geral
python -m cli --help

# Listar ligas configuradas
python -m cli data leagues

# Descobrir dados disponíveis
python -m cli data discover

# Buscar fixtures
python -m cli data fixtures premier-league --date today

# Gerar Quadro-Resumo
python -m cli analysis quadro premier-league

# Previsões com mercados sugeridos
python -m cli analysis predict premier-league --date tomorrow

# Auditoria com IA (requer MISTRAL_API_KEY)
python -m cli analysis audit premier-league --match-index 0

# Iniciar backend
python -m cli server api --port 5001 --reload

# Iniciar backend + Streamlit juntos
python -m cli server dev

# Validar deploy
python -m cli server validate --backend-url https://api.exemplo.com

# Gerar hash de senha
python -m cli utils hash-password

# Rodar testes
python -m cli utils test --coverage
```

Após instalar com `pip install -e .`, o comando `sportsbank` fica disponível globalmente:

```bash
sportsbank data leagues
sportsbank analysis quadro premier-league
```

### 5. Testes E2E (Playwright)

O dashboard Next.js possui testes E2E automatizados com Playwright:

```bash
cd frontend/next

# Instalar browsers (primeira vez)
npx playwright install --with-deps

# Rodar todos os testes
npm run test:e2e

# Modo visual interativo
npm run test:e2e:ui

# Com navegador visível
npm run test:e2e:headed

# Ver relatório HTML
npm run test:e2e:report
```

**Testes disponíveis:**

| Arquivo | Cobertura |
|---------|-----------|
| `e2e/home.spec.ts` | Página principal: header, banca, slider Kelly, estratégia, value bets |
| `e2e/dashboard.spec.ts` | Dashboard: sidebar, stats, gráfico, seletor de liga |
| `e2e/ai-audit.spec.ts` | Página de auditoria AI |
| `e2e/market-trends.spec.ts` | Tendências de mercado: chips, gráfico |
| `e2e/performance-stats.spec.ts` | Estatísticas: heat map, DRS zones, transfers |
| `e2e/navigation.spec.ts` | Navegação entre páginas, theme toggle |
| `e2e/api.spec.ts` | Rotas API: matches, decision/pre |

---

## ⚽ Ligas Suportadas (33)

| # | País | Liga | ID | DNA |
|---|------|------|----|-----|
| 1 | England | Premier League | `premier-league` | OFFENSIVE |
| 2 | England | Championship | `championship` | BALANCED |
| 3 | England | League One | `league-one` | DEFENSIVE |
| 4 | England | League Two | `league-two` | DEFENSIVE |
| 5 | Argentina | Primera Division | `primera-division` | BALANCED |
| 6 | Australia | A-League | `a-league` | BALANCED |
| 7 | Austria | Bundesliga | `austrian-bundesliga` | BALANCED |
| 8 | Belgium | Pro League | `pro-league` | BALANCED |
| 9 | Brazil | Serie A | `brasileirao-serie-a` | OFFENSIVE |
| 10 | Brazil | Serie B | `brasileirao-serie-b` | BALANCED |
| 11 | Colombia | Primera A | `colombian-primera-a` | BALANCED |
| 12 | Czech Republic | First League | `czech-first-league` | DEFENSIVE |
| 13 | Denmark | Superliga | `superliga` | BALANCED |
| 14 | France | Ligue 1 | `ligue-1` | BALANCED |
| 15 | France | Ligue 2 | `ligue-2` | DEFENSIVE |
| 16 | Germany | Bundesliga | `bundesliga` | OFFENSIVE |
| 17 | Germany | 2. Bundesliga | `2-bundesliga` | BALANCED |
| 18 | Greece | Super League | `super-league-greece` | BALANCED |
| 19 | Italy | Serie A | `serie-a` | BALANCED |
| 20 | Italy | Serie B | `serie-b` | DEFENSIVE |
| 21 | Japan | J-League | `j-league` | DEFENSIVE |
| 22 | Netherlands | Eredivisie | `eredivisie` | BALANCED |
| 23 | Netherlands | Eerste Divisie | `eerste-divisie` | BALANCED |
| 24 | Norway | Eliteserien | `eliteserien` | DEFENSIVE |
| 25 | Portugal | Primeira Liga | `primeira-liga` | BALANCED |
| 26 | Saudi Arabia | Professional League | `professional-league` | BALANCED |
| 27 | Scotland | Premiership | `premiership` | BALANCED |
| 28 | South Korea | K-League | `k-league` | DEFENSIVE |
| 29 | Spain | La Liga | `la-liga` | BALANCED |
| 30 | Spain | Segunda Division | `segunda-division` | BALANCED |
| 31 | Sweden | Allsvenskan | `allsvenskan` | DEFENSIVE |
| 32 | Switzerland | Super League | `super-league` | BALANCED |
| 33 | Turkey | Süper Lig | `super-lig` | BALANCED |
| 34 | UAE | Pro League | `uae-pro-league` | BALANCED |
| 35 | USA | MLS | `mls` | BALANCED |

---

## ⚙️ Configuração

### Secrets do Streamlit (Local)

Para configuração local, crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:

```toml
BACKEND_URL = "http://localhost:5001"
```

### Autenticação (Local)

O arquivo `config.yaml` já vem pré-configurado com usuários de teste. Para produção, você deve:

1. Gerar hash das suas senhas usando `python gerar_hash_senha.py`
2. Atualizar o `config.yaml` com os hashes gerados
3. **IMPORTANTE:** Adicionar `config.yaml` ao `.gitignore`

Exemplo de `config.yaml`:

```yaml
credentials:
  usernames:
    seu_usuario:
      name: "Seu Nome Completo"
      password: "hash_sha256_da_sua_senha_aqui"
    
    outro_usuario:
      name: "Outro Usuário"
      password: "hash_sha256_da_outra_senha_aqui"
```

### Variáveis do Dashboard Next.js

O dashboard Next.js requer a variável `PY_BACKEND_URL` para conectar ao backend FastAPI e exibir dados reais. Sem essa variável, o sistema usa **mock data** como fallback (comportamento intencional para desenvolvimento local sem backend).

**Setup local:**

```bash
# Copiar o arquivo de exemplo
tcp frontend/next/.env.example frontend/next/.env.local

# Editar com a URL do backend local
# PY_BACKEND_URL=http://localhost:5001
```

**Deploy no Vercel (produção):**

Para que o dashboard em produção use dados reais (e não mock data), configure a variável de ambiente no painel do Vercel:

1. Acesse **Settings > Environment Variables** no projeto Vercel
2. Adicione: `PY_BACKEND_URL` = URL do seu backend FastAPI (ex: `https://seu-endpoint.execute-api.us-east-1.amazonaws.com`)
3. Aplique para os ambientes: **Production** e **Preview**
4. Faça um novo deploy para que a variável tenha efeito

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `PY_BACKEND_URL` | Sim (produção) | URL do backend FastAPI. Sem ela, o dashboard usa mock data |
| `NEXT_PUBLIC_PY_BACKEND_URL` | Não | Variante pública para fetches client-side |

> **Importante:** A branch `main` deve ser sempre a fonte da verdade para deploys em produção. Certifique-se de que features desenvolvidas em branches de trabalho sejam mergeadas na `main` antes do deploy final.

---

## 🔒 Segurança

### Proteção de Credenciais

Para manter suas credenciais seguras, siga estas práticas recomendadas:

**Nunca faça commit do `config.yaml` com senhas reais.** Adicione o arquivo ao `.gitignore` executando `echo "config.yaml" >> .gitignore`. **Use Streamlit Secrets para produção** em vez de arquivos locais. **Gere senhas fortes** e armazene apenas os hashes SHA-256. **Mantenha credenciais de teste separadas** das credenciais de produção.

### Arquivo .gitignore

Certifique-se de que seu `.gitignore` inclui:

```
# Credenciais
config.yaml
.env
.env.local

# Dados sensíveis
*.csv
data/

# Python
__pycache__/
*.py[cod]
venv/

# Node
node_modules/
.next/
```

---

## ☁️ Deploy no Streamlit Cloud

### 1. Preparar Repositório

Antes de fazer deploy, prepare seu repositório:

```bash
# Adicionar config.yaml ao .gitignore
echo "config.yaml" >> .gitignore

# Fazer commit das alterações
git add .
git commit -m "feat: adiciona sistema de autenticação"
git push
```

### 2. Criar App no Streamlit Cloud

Acesse [streamlit.io/cloud](https://streamlit.io/cloud) e crie um novo app apontando para `app.py` na raiz do seu repositório GitHub.

### 3. Configurar Secrets

Em **Settings → Secrets**, adicione as seguintes configurações:

```toml
# URL do Backend
BACKEND_URL = "https://seu-backend-publico:5001"

# Credenciais de Autenticação
[credentials.usernames.admin]
name = "Administrador"
password = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"

[credentials.usernames.seu_usuario]
name = "Seu Nome"
password = "seu_hash_sha256_aqui"
```

**Nota:** O hash mostrado acima é da senha "admin" (apenas para exemplo).

### 4. Aguardar Build

Aguarde a conclusão da build. O app estará disponível em:

```
https://{nome-do-app}-{seu-usuario}.streamlit.app
```

---

## 🌍 Variáveis de Ambiente do Backend

O backend utiliza as seguintes variáveis de ambiente para localizar os dados:

**FUTEBOL_ROOT** (ou **DATA_ROOT**) define a raiz do projeto/dados (ex: `/data/futebol`). **FUTEBOL_DATA_DIR** especifica o caminho direto para a pasta `data` (ex: `/data/futebol/data`).

Se não definidas, o sistema usa o padrão `C:\Users\wxamb\futebol\data` (Windows) ou `/home/ubuntu/futebol/data` (Linux).

---

## ✅ Verificações Rápidas

### Backend

Teste os endpoints principais da API:

```bash
# Listar jogos de múltiplas ligas
GET http://localhost:5001/fixtures?leagues=premier-league,la-liga&date=today

# Descobrir ligas disponíveis
GET http://localhost:5001/discover

# Placares ao vivo (cache 1 min)
GET http://localhost:5001/live-scores

# Gerar quadro-resumo profissional
GET http://localhost:5001/quadro-resumo?league=premier-league&date=week&incluir_simples=true&incluir_duplas=true&incluir_triplas=false&incluir_governanca=true

# Corrigir score de jogo com dados ausentes/errados
POST http://localhost:5001/api/ai/score-correction
# Body: {"match_id": "...", "home_team": "Lanús", "away_team": "Boca Juniors", "home_goals": 0, "away_goals": 3, "league": "primera-division"}
```

### Streamlit

Verifique se a interface está funcionando corretamente:

A **tela de login** deve aparecer ao acessar pela primeira vez. Após autenticação, a **tabela de jogos** deve mostrar os prognósticos com probabilidades e valores de λ nas tooltips. O **Quadro-Resumo Profissional** deve aparecer acima da tabela com opções para copiar e baixar. O **gráfico interativo** deve exibir as probabilidades de forma visual.

### Dashboard Next.js

Confirme o funcionamento do dashboard:

A **página inicial** (`/dashboard`) deve carregar jogos por liga com filtros Hoje/Amanhã/Próxima Rodada. A **aba Recomendadas 2026** exibe jogos com maior confiança. O **botão Compartilhar** captura a tela e permite enviar via WhatsApp (em dispositivos compatíveis) ou faz download da imagem e abre o WhatsApp com o link. **Jogos ao vivo** exibem placar atualizado automaticamente a cada 60s com indicador vermelho pulsante. A **navegação** é fluida e responsiva.

---

## 🔧 Ajustes Opcionais

### CORS no FastAPI

Se o backend for público e acessado de diferentes origens, adicione middleware CORS:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://seu-app.streamlit.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### CSVs Remotos

Se o backend não tiver acesso local aos CSVs, considere usar storage público (AWS S3, Google Cloud Storage) ou criar um endpoint específico para upload/download de dados.

---

## 📝 Observações Importantes

### Dados CSV

Se CSVs forem usados pelo backend, eles precisam estar acessíveis para o servidor. Para deploy em produção, considere migrar para storage público ou criar um endpoint dedicado.

### Conectividade

Quando a variável `BACKEND_URL` não responder, o app exibirá tabelas vazias. Verifique os logs do Streamlit e a conectividade com o backend.

### Última Atualização

A tela mostra a "Última atualização (fonte)" quando o backend fornece o campo `lastUpdated` na resposta da API.

### Autenticação

O sistema de autenticação é obrigatório por padrão. Se desejar desabilitar temporariamente para testes, comente as linhas de autenticação no `app.py`.

---

## 📚 Documentação Adicional

Para informações mais detalhadas sobre componentes específicos, consulte:

- **Sistema de Autenticação:** `solucao_autenticacao_streamlit.md`
- **Quadro-Resumo Profissional:** `PROMPT_IMPLEMENTACAO_QUADRO_RESUMO_FINAL.md`
- **API do Backend:** Acesse `http://localhost:5001/docs` para documentação interativa (Swagger)
- **Claude Code:** `CLAUDE.md` na raiz do projeto com instruções, comandos, referências Context7 e regra de investigação obrigatória

---

## 🔄 Histórico de Alterações (Changelog)

### V3.5.1 — 5 de Março de 2026 (Fix Score Accuracy + Dupla Audit + Fix Live Status)

#### Backend — Score Accuracy Fix (Problema Lanús 0-3 Boca → 0-0 no sistema)
- **fix(mapper):** `FootyStatsMatchInput` — defaults de `homeGoalCount`, `awayGoalCount`, `totalGoalCount` alterados de `0` para `None` em `data_mapper.py`, eliminando a confusão entre "0 gols" e "dados ausentes"
- **fix(mapper):** `map_match_to_internal()` — fallback `0` removido do mapeamento de gols; campos agora propagam `None` quando a API não retorna dados
- **fix(fixtures):** `fixtures_service.py` — jogos ao vivo com dados de gol ausentes **não são mais defaultados para 0-0**; sistema loga warning e mantém `match_score = None`
- **fix(fixtures):** Logging de warning adicionado para jogos finalizados sem dados de gol — indica gap de cobertura da API para a liga
- **fix(audit):** `ai_analysis.py` batch audit agora **pula** jogos sem score verificado em vez de auditar contra 0-0 falso
- **fix(audit):** `cron_handler.py` — mesma validação de score `None` aplicada ao cron audit e ao tracking de dupla accuracy

#### Backend — Score Correction Endpoint
- **feat(api):** Novo endpoint `POST /api/ai/score-correction` para correção manual de resultados quando API retorna dados errados/ausentes
- **feat(api):** Correções registradas no audit DB como `SCORE_CORRECTION` com confiança 100% e rastreabilidade completa
- **feat(api):** Resposta inclui resultado corrigido calculado (1X2, total_goals, btts) para validação imediata

#### Backend — Dupla (Combinada) Audit
- **feat(audit):** Auditoria de duplas INTRA e INTER adicionada ao `cron_handler.py` batch audit
- **feat(audit):** Tracking de taxa de acerto por tipo: `dupla_intra_accuracy_pct`, `dupla_inter_accuracy_pct`, `dupla_overall_accuracy_pct`
- **feat(audit):** Contadores detalhados: `dupla_intra_correct/total`, `dupla_inter_correct/total`
- **feat(audit):** Lookup de resultado real por match ID e por homeTeam+awayTeam para avaliação de cada perna da dupla
- **fix(audit):** Dupla accuracy tracking agora valida score `None` antes de incluir no lookup — evita avaliação contra dados fantasma

#### Backend — Fix False Live Status
- **fix(status):** `status_map()` — removido `"incomplete"` do mapeamento para `"live"` em `util_service.py`; agora cai em `"scheduled"` (FootyStats usa "incomplete" para jogos não iniciados)
- **fix(fixtures):** Guard de kickoff-time em `fixtures_service.py` — se API retorna `"live"` mas kickoff é > 2 min no futuro, override para `"scheduled"` com logging
- **fix(live-scores):** Guard de kickoff-time em `/live-scores` — demote `"live"` → `"scheduled"` quando `elapsed_min < -2`, previne badges "AO VIVO" falsos

#### Processo — Regra de Investigação Obrigatória
- **docs(claude):** Adicionada seção "Regra de Investigação Obrigatória" ao `CLAUDE.md` com 7 passos mandatórios antes de qualquer correção:
  1. Não assumir causa raiz — investigar todos os caminhos de código
  2. Traçar fluxo completo da API externa até a renderização no browser
  3. Verificar todos os pontos de entrada (mapper, service, route, overlay, polling)
  4. Considerar caching e deploy (SQLite TTL, Vercel build, Lambda cold start)
  5. Validar com dados reais via logging em vez de supor valores
  6. Implementar defesa em profundidade em múltiplas camadas
  7. Testar cenário completo simulando o fluxo com dados do bug reportado

#### Frontend — Resultado de Auditoria de Duplas
- **feat(ui):** Badge ACERTOU/ERROU/PENDENTE em cada card de dupla no painel de Auditoria da Rodada (`BatchAuditPanel`)
- **feat(ui):** Resumo de acurácia de duplas com cards Intra-jogo, Inter-jogo e Geral no topo da seção de Duplas Recomendadas
- **feat(audit):** `localAudit.ts` agora avalia cada dupla contra resultados reais dos jogos finalizados — avaliação determinística no browser
- **feat(type):** Campo `resultado` (`ACERTOU`/`ERROU`/`PENDENTE`) adicionado a `AuditCombinada`; campos de accuracy adicionados a `AuditCombinadas`

### V3.5 — Março de 2026 (Motor Safe Bets — 3 Camadas)

#### Backend — Safe Bets Engine
- **feat(engine):** Motor Safe Bets com arquitetura de 3 camadas: Layer 1 (League DNA), Layer 2 (Risk Semaphore) e Layer 3 (Strategy Algorithms)
- **feat(dna):** League DNA Matrix — categorização estática de 33 ligas em DEFENSIVE/BALANCED/OFFENSIVE + eixo independente AGGRESSIVE (cartões > 3.5/jogo)
- **feat(dna):** Classificação dinâmica via season stats ao vivo com fallback para perfil estático — função `classify_league_dna()`
- **feat(risk):** Risk Semaphore bloqueia jogos com `prediction_risk > 0.65` antes de aplicar estratégias
- **feat(strategy):** Estratégia A — Under 3.5 Defensivo Conservador: cruza média de gols da liga (< 2.6) com média de gols sofridos dos times (< 1.1)
- **feat(strategy):** Estratégia B — BTTS Não: avalia BTTS% da liga (< 45%), clean sheet% mandante (> 50%) e FTS% visitante (> 40%)
- **feat(strategy):** Estratégia C — Safe Corners Over 9.5: valida média de escanteios da liga (> 10.2) e combinada dos times (> 10.5), com sub-tag Corners HT (> 4.5)
- **feat(strategy):** Estratégia D — Timing 2º Tempo: probabilidade combinada de gols no 2º tempo (> 88%)
- **feat(model):** Modelos Pydantic completos: `SafeBetsMatchInput`, `SafeBetsResult`, `StrategyResult`, `SafeBetsResponse` com enums `SafeBetTag`, `RiskLevel`, `LeagueCategory`
- **feat(model):** `TeamSafeBetsStats` com `model_validator` para flatten automático de nested stats da API FootyStats
- **feat(api):** Endpoint `POST /safe-bets/evaluate` — avaliação em batch de matches com stats pré-carregados
- **feat(api):** Endpoint `GET /safe-bets/league-dna` — consulta de perfis DNA por liga ou todas as 33
- **feat(api):** Endpoint `GET /safe-bets/leagues` — listagem de todas as ligas monitoradas com DNA integrado

#### Configuração — Ligas
- **feat(config):** `leagues_config.py` expandido de 22 para 33 ligas com nomes alternativos para matching fuzzy
- **feat(config):** Novas ligas: J-League, K-League, Eliteserien, Allsvenskan, MLS, Colombian Primera A, UAE Pro League, Super League Greece, Czech First League, League One, League Two
- **feat(sql):** Migration `002_add_safe_bets_leagues.sql` com DDL para novas tabelas e inserção de season IDs

#### Frontend — Dashboard
- **feat(ui):** Componente `SafeBetsBadge` com indicadores visuais: badge de risco (SAFE verde, MODERADO amarelo, NO BET vermelho) e tags por estratégia
- **feat(ui):** Tipos TypeScript para Safe Bets: `SafeBetTag`, `RiskLevel`, `SafeBetsResult`, `StrategyResult` + config de labels/cores em `SAFE_BET_TAG_CONFIG`
- **feat(api):** Rota proxy `POST /api/safe-bets` encaminha avaliação ao backend com timeout de 30s

### V3.4 — Marco de 2026 (Placares ao Vivo + Auditoria Local Instantânea + Recomendação do Modelo)

#### Backend
- **feat(api):** Novo endpoint `/live-scores` retorna placares e status de jogos em andamento/finalizados via FootyStats `todays-matches`
- **feat(api):** Metodo `get_live_scores()` no FootyStatsClient com cache de 1 minuto (vs 30 min do `todays-matches` padrao) para eficiencia de rate limit
- **feat(service):** `fixtures_service.py` agora extrai placar para jogos com status `live` (antes apenas `finished`), incluindo placar do intervalo (halftime)
- **feat(ai):** Prompt Mistral de auditoria em lote atualizado com campo `model_update_recommendation` no schema JSON — IA agora recomenda se modelo precisa re-treino
- **feat(ai):** Fallback de erro no `MistralAuditor` inclui `model_update_recommendation` padrão
- **fix(ai):** Otimizacao de custos da API Mistral mudando modelo padrao em todos os servicos (ContextAnalyzer, ReportGenerator, etc.) de `mistral-medium-latest`/`large` para o veloz e eficiente `mistral-small-latest`
- **fix(service):** Corrigido mapeamento em `status_map` (ignorando `incomplete`) para evitar que jogos agendados sobreponham o status "VIVO" no dashboard

#### Frontend / Dashboard
- **feat(live):** Polling automatico de placares a cada 60s quando ha jogos ao vivo (120s quando nao ha) via `/api/matches/live`
- **feat(live):** Rota `/api/matches/live` reescrita — substituido mock `simulateLive()` por chamada real ao backend
- **feat(ui):** Indicador visual "AO VIVO" com ponto vermelho pulsante na linha do jogo e no cabeçalho da liga
- **feat(ui):** Placar ao vivo em destaque (vermelho, fonte maior, pulsante) nas linhas de jogos e no card de detalhes
- **feat(ui):** Placar final com intervalo (HT) exibido no card de detalhes para jogos finalizados
- **feat(ui):** Badge de contagem de jogos ao vivo no cabeçalho da liga (ex: "2 AO VIVO")
- **feat(type):** Campo `footystatsId` adicionado ao tipo `Match` para correlacao precisa no polling
- **feat(audit):** Recomendação de atualização do modelo na "Auditoria da Rodada" — calculo determinístico local (instantâneo) baseado em Brier Score, erro lambda, acurácia geral/SAFE e acurácia por mercado
- **feat(audit):** Niveis de urgência: BAIXA, MEDIA, ALTA, CRITICA — com diagnóstico detalhado, ações recomendadas e sugestão de próximo re-treino
- **feat(audit):** Quando disponível, avaliação Mistral AI substitui cálculo local (análise mais rica)
- **feat(audit):** Novo tipo `ModelUpdateRecommendation` com `needs_update`, `urgency`, `reasons`, `recommended_actions`, `next_retrain_suggestion`
- **feat(ui):** Seção visual "Modelo Precisa de Atualização" / "Modelo Dentro dos Parâmetros" com badge de urgência colorido, lista de diagnósticos e ações
- **fix(ui):** Chamada de Analise IA em `dashboard/page.tsx` nao e mais feita automaticamente no `useEffect` para economizar custos, trocada por um botão "Gerar Análise AI" de ativacao manual no `MatchDetailCard`
- **feat(audit):** Auditoria em lote ("Auditar Rodada") agora executa inteiramente no navegador via `localAudit.ts` — avaliação determinística instantânea (ACERTOU/ERROU) para todos os mercados (1X2, Over/Under, BTTS, Double Chance) sem depender do backend Lambda
- **feat(audit):** Avaliação qualitativa Mistral AI separada em endpoint leve `/api/ai/batch-audit/evaluate` — recebe apenas estatísticas pré-computadas pelo browser (3-5s vs 30s+ anterior)
- **fix(audit):** Rota antiga `/api/ai/batch-audit` deprecada — retorna `status: "success"` com mensagem de atualização para navegadores com JS cacheado de deploys anteriores
- **fix(audit):** Mecanismo de auto-refresh via comparação de `buildId` — detecta JS desatualizado após deploys Vercel e recarrega a página automaticamente
- **fix(fetch):** Retry de carregamento de jogos estendido para incluir HTTP 503 (além de TIMEOUT) — cobre cold starts do Lambda que retornam 503
- **fix(audit):** Mensagens de erro da auditoria individual agora direcionam o usuário para "Auditar Rodada" como alternativa confiável (em vez do genérico "Serviço indisponível")
- **fix(ui):** Botão "Gerar Análise AI" restaurado no `MatchDetailCard` após ser sobrescrito durante resolução de conflito de layout
- **feat(ui):** Redesenho da coluna de status inspirado em broadcast esportivo — tags coloridas: VIVO (vermelha pulsante com gradiente e glow), FT (verde), BREVE (amarela com glow suave), ADIADO (cinza atenuado)
- **feat(ui):** Status ao vivo exibe período (1T/HT/2T) e minuto estimado a partir do `date_unix` do kickoff com heurística de override por dados de halftime
- **feat(ui):** Linha de jogo ao vivo com borda lateral vermelha e fundo avermelhado sutil; placar com text-shadow e numeração tabular
- **feat(ui):** Tag FT simplificada (sem data redundante) — display limpo e proeminente para jogos finalizados

### V3.3.1 — 28 de Fevereiro de 2026 (Estabilidade & Qualidade)

#### UI / Dashboard
- **fix(ui):** Botão "Ordenar" agora funcional — alterna entre ordem crescente/decrescente por horário do jogo
- **fix(ui):** Placar não quebra mais em 2 linhas — CSS corrigido com `min-width: 40px` e `white-space: nowrap`
- **fix(ui):** Aba "Perfil" agora visível e funcional — corrigido bug de valores falsy (`||` tratava `0` como falso, ocultando dados válidos); seção comparativa expandida por padrão
- **fix(ui):** Todas as 6 abas comparativas (Perfil, Chutes, Finalizações, Faltas, Desempenho, Escanteios & Cartões) corrigidas com `!= null` em vez de `||`
- **fix(ui):** Aba "Duplas" com mensagens de erro em pt-BR e agora envia apenas ligas carregadas (evita sobrecarga no backend)

#### Backend — Resiliência
- **fix(backend):** Isolamento de erros por jogo — `try-except` individual em cada match no `fixtures_service.py` com `exc_info=True` para tracebacks completos
- **fix(backend):** `build_records_from_matches()` protegido contra crash total — fallback para `records = []`
- **fix(backend):** `teams_to_df()` com tratamento por registro — times malformados são ignorados sem derrubar o lote
- **fix(backend):** `league_df` e `get_league_season_stats()` com try-except individual — liga com dados incompletos não impede carregamento das demais

#### Refatoração
- **refactor:** Utilitário compartilhado `mapMatchStats()` em `src/lib/matchStats.ts` — elimina 55 linhas duplicadas entre dashboard e página de match
- **refactor:** Dependências do `fetchCombinadas` estabilizadas via `useMemo` para IDs de ligas — evita re-fetches desnecessários

### V3.3 — 28 de Fevereiro de 2026 (Cobertura Total Leiautes CSV FootyStats)

#### Match CSV — 64 Data Columns (novos campos)
- **feat(match):** Half-time: `total_goals_at_half_time`, `home/away_team_goal_count_half_time`
- **feat(match):** Goal timings: `home/away_team_goal_timings` (minutos dos gols)
- **feat(match):** Card splits: `home/away_team_first_half_cards`, `home/away_team_second_half_cards`
- **feat(match):** Context: `attendance` (público), `referee` (árbitro)
- **feat(match):** Odds: `odds_btts_no` adicionado ao mapeamento

#### Team CSV — 186 Data Columns (novos campos)
- **feat(team):** Record: `wins/draws/losses`, `win/draw/loss_percentage`, `league_position` (overall/home/away)
- **feat(team):** Clean sheets: `clean_sheets`, `clean_sheet_percentage` — crítico para análise BTTS
- **feat(team):** BTTS: `btts_count`, `btts_percentage` — input direto para mercado BTTS
- **feat(team):** FTS: `fts_count`, `fts_percentage` (failed to score) — complementa análise BTTS Não
- **feat(team):** Over/Under: `over05~45_percentage`, `under15/25_percentage` — input direto para mercados O/U
- **feat(team):** xG: `xg_for_avg`, `xg_against_avg` (overall/home/away) — melhora cálculo de lambdas
- **feat(team):** Goals: `average_total_goals_per_match`, `goal_difference`, `minutes_per_goal_scored/conceded`
- **feat(team):** Half-time: `goals_scored/conceded_half_time`, médias por jogo HT
- **feat(team):** `home_advantage_percentage`, `prediction_risk`, `first_team_to_score_percentage`
- **feat(team):** PPG: `points_per_game_home/away` adicionados

#### Team CSV Pt.2 — 442 Data Columns (novos campos)
- **feat(team):** Corners against: `corners_against_per_match` (overall/home/away) — escanteios do adversário
- **feat(team):** Corner over %: `over85/95/105_corners_percentage` — input direto para mercado de escanteios
- **feat(team):** `shots_off_target_per_match`
- **feat(team):** BTTS compound: `btts_and_win_percentage`, `scored_both_halves_percentage`
- **feat(team):** 2nd half: `goals_scored/conceded_2h_per_match`, `btts_2h_percentage`
- **feat(team):** Goal timing: distribuição de gols por intervalo de 10 minutos (0-10 até 81-90)

#### League CSV — 49 Data Columns (novos campos)
- **feat(league):** Home advantage: `home_advantage_percentage`, `home_scored/defence_advantage_percentage`
- **feat(league):** Goals home/away: `average_scored_home_team`, `average_scored_away_team`
- **feat(league):** `clean_sheets_percentage` (nível liga)
- **feat(league):** Over/Under %: `over_05~45_percentage` (benchmarks da liga)
- **feat(league):** `xg_avg` (xG médio da liga), `prediction_risk`
- **feat(league):** `matches_completed`, `total_matches` (progresso da temporada)

#### Service & AI
- **feat(service):** Helper genérico `_team_stat()` para extrair qualquer coluna do teams_df
- **feat(service):** 21 novos stats extraídos por time: btts%, cs%, fts%, over25%, win%, xG for/against, corners_against, league_position, avg_total_goals
- **feat(service):** League avgs expandidos: home_advantage, clean_sheets, over25, xG
- **feat(ai):** Prompt Mistral com novas seções PERFIL DE GOLS e CLASSIFICACAO E DESEMPENHO
- **feat(ai):** Instrucoes para Mistral usar xG, BTTS%, clean sheet%, FTS%, over 2.5%, posição na liga

#### Frontend
- **feat(frontend):** Nova aba "Perfil" com barras comparativas de xG médio, xG sofrido, média gols total
- **feat(frontend):** Perfil mostra: % vitórias, Over 2.5%, Clean Sheet%, BTTS%, posição na liga
- **feat(frontend):** 26 novos campos TypeScript em MatchDetailCard, leagues.ts e page.tsx

### V3.2 — 28 de Fevereiro de 2026 (Comparativo Times + Feedback Loop BTTS/Escanteios)

- **feat(data):** Novos campos extraídos da API FootyStats: `yellow_cards`, `red_cards`, `fouls`, `offsides`, `shots_off_target` (nível de partida) — alimentam cálculos e comparativos
- **feat(api):** Novo endpoint `league-teams` com `&include=stats` busca dados agregados por time (cartões, faltas, finalizações, chutes ao gol, posse, escanteios) — corrige gap onde `teams_df` era sempre `None` no path de API
- **feat(mapper):** `map_team_to_internal()` reescrito com mapeamento completo dos campos reais da API FootyStats (`cardsAVG_overall`, `foulsAVG_overall`, `shotsAVG_overall`, `shotsOnTargetAVG_overall`, `cornersAVG_overall`, `possessionAVG_overall`, etc.)
- **feat(stats):** Novo helper `team_shots_per_match()` e cascata de fallbacks: team stats → histórico de partidas → média da liga / 2 (para cartões, faltas, finalizações, chutes ao gol, escanteios)
- **feat(stats):** Médias de liga para faltas (`foulsAVG_overall`) e finalizações (`shotsAVG_overall`) adicionadas a `league_df`
- **feat(ai):** Prompt da Mistral enriquecido com seção COMPARATIVO TIMES: posse, escanteios/jogo, cartões/jogo, finalizações/jogo, chutes ao gol/jogo, faltas/jogo — melhora fundamentação da análise
- **feat(frontend):** Aba "Finalizações" agora exibe dados reais (finalizações por jogo) com média da liga; aba "Faltas" agora exibe média da liga; tipos TypeScript atualizados
- **fix(audit):** Feedback loop (Gap 2) agora aplica correções `btts_multiplier` e `corner_multiplier` do audit DB às probabilidades — anteriormente só aplicava `lambda_home/away_multiplier`
- **fix(calibrator):** Mercados `Escanteios Over 8.5/9.5/10.5` adicionados a `CALIBRATED_MARKETS` e ao mapping `calibrate_match_stats`, permitindo calibração isotônica para escanteios
- **fix(audit):** Batch audit agora registra picks individuais por mercado via `log_pick()`, alimentando o calibrador com dados de Brier Score per-market (BTTS, corners, etc.)
- **fix(audit):** `_evaluate_pick_deterministic` agora avalia corretamente mercados de escanteios contra `total_corners` do jogo — anteriormente retornava sempre `False` (100% erro)
- **fix(market):** Thresholds de escanteios agora usam `_get_dynamic_thresholds()` do audit DB com fallback para defaults, permitindo ajuste automático via auditoria
- **fix(audit):** Novos tipos de correção `BTTS_THRESHOLD`, `BTTS_MULTIPLIER`, `CORNER_THRESHOLD`, `CORNER_MULTIPLIER` adicionados a `ADJUSTMENT_LIMITS`, permitindo que Mistral sugira e aplique correções para esses mercados
- **fix(ai):** Prompt do Mistral atualizado para incluir os novos tipos de correção no schema de `recommended_corrections`

### 28 de Fevereiro de 2026 — Fix: Servidor Indisponível (Fan-out + Retry)

- **fix(fetch):** Fan-out paralelo no carregamento de ligas — o dashboard agora divide as 22 ligas em batches de 3 e busca em paralelo via `Promise.allSettled`, evitando timeout do Lambda que processava tudo sequencialmente (45+ chamadas API FootyStats em série = 90-130s, estourando os 55s de timeout). Merge dos resultados é feito client-side em `getMatchesByLeague()` (`frontend/next/src/lib/api.ts`). **REGRA: NÃO remover este fan-out — sem ele, o sistema volta a dar timeout com as 22 ligas.**
- **fix(fetch):** Auto-retry (1x) na API route `fetch/route.ts` para TIMEOUT, CONNECTION_ERROR e HTTP 502/503/504 (cold start do Lambda)
- **fix(dashboard):** `handleRetry` agora replica a lógica completa do carregamento inicial (retry em cold start + fallback today→week)
- **fix(dashboard):** CONNECTION_ERROR adicionado à lista de erros retentáveis no carregamento inicial

### V3.1 — 26 de Fevereiro de 2026 (Auditoria Contínua + Calibração)

- **feat(audit):** Cron `today_audit` às 23:45 BRT para auditar jogos do mesmo dia (além do `batch_audit` de ontem às 20h)
- **feat(pipeline):** Correções de lambda do audit DB aplicadas automaticamente no cálculo de previsões
- **feat(pipeline):** Ajuste de confiança via Mistral ContextAnalyzer (AUMENTAR/MANTER/REDUZIR) aplicado às probabilidades 1X2
- **feat(pipeline):** Thresholds dinâmicos de mercado (BTTS, Over/Under, Double Chance) lidos do audit DB com fallback para valores hardcoded
- **feat(modeling):** Novo módulo `calibrator.py` com Isotonic Regression para calibração de probabilidades:
  - Fallback por volume: liga (≥50 amostras) → regime (≥30) → passthrough
  - Validação temporal com `TimeSeriesSplit` (sem data leakage)
  - Critério de aceitação via Brier Score
  - Cron `retrain_calibrators` para re-treino semanal
- **feat(ai):** Campo `impact_percentage` (0-20) adicionado ao schema de `confidence_adjustment` do ContextAnalyzer

### 22 de Fevereiro de 2026

- **fix(layout):** Corrige scroll independente dos painéis esquerdo e direito. O painel direito agora permanece fixo na tela com scroll interno, enquanto o painel esquerdo rola a lista de jogos de forma independente.
- **fix(auditoria):** Adiciona scroll automático para o resultado da auditoria individual ao clicar em "Auditar", garantindo que o resultado seja sempre visível para o usuário.
- **fix(auditoria):** Garante que o modal de auditoria em lote seja sempre visível, mesmo quando o backend está indisponível.

### 21 de Fevereiro de 2026

- **feat(dashboard):** Adiciona prognósticos de cartões e escanteios nas abas correspondentes.
- **fix(dashboard):** Corrige a exibição de prognósticos abaixo dos jogos, que não apareciam devido a um problema de layout flex.
- **fix(dashboard):s** Corrige a exibição de odds para cartões e escanteios, que mostravam "-" em vez dos valores corretos.

---

## 🤝 Suporte

Para dúvidas, problemas ou sugestões:

1. Consulte a documentação completa na pasta do projeto
2. Verifique os logs do Streamlit e do backend
3. Teste os endpoints da API diretamente
4. Revise as configurações de Secrets e variáveis de ambiente

---

## 📄 Licença

Este projeto é proprietário e confidencial. Todos os direitos reservados.

---

**Desenvolvido com ⚽ para análise profissional de prognósticos esportivos**
