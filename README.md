# SportsBank Pro

> Sistema profissional de cálculo de prognósticos esportivos com backend FastAPI, frontend Streamlit e dashboard Next.js

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red.svg)](https://streamlit.io/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Playwright](https://img.shields.io/badge/Playwright-E2E-green.svg)](https://playwright.dev/)

**Última revisão:** 2026-02-02

---

## 📊 Visão Geral

O **SportsBank Pro** é um sistema completo de análise e prognósticos esportivos que combina modelos estatísticos avançados com uma interface intuitiva e profissional.

---

## 📊 Status de Implementação

### Funcionalidades Ativas

- Backend FastAPI com endpoints REST
- Interface Streamlit com visualização de dados
- Quadro-Resumo Profissional formatado para compartilhamento
- Analise de Picks com multiplos mercados
- Graficos interativos de probabilidades
- Analise de Contexto com IA (Mistral)
- Geracao de relatorios automatizada
- Exportacao de dados (CSV, JSON, TXT)
- Filtros por liga e periodo
- Responsividade mobile/tablet (CSS customizado)

### Funcionalidades Opcionais

- Sistema de autenticacao (depende de config.yaml ou Secrets)
- Dashboard Next.js (configuracao separada)
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

O SportsBank Pro inclui um sistema de autenticacao opcional que protege o acesso ao sistema atraves de login com usuario e senha.

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
# Instalar dependências
npm i

# Iniciar servidor de desenvolvimento
npm run dev
```

Acesse o dashboard em `http://localhost:3000/`.

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

## ⚽ Ligas Suportadas (22)

| # | País | Liga | ID |
|---|------|------|----|
| 1 | England | Premier League | `premier-league` |
| 2 | England | Championship | `championship` |
| 3 | Argentina | Primera Division | `primera-division` |
| 4 | Australia | A-League | `a-league` |
| 5 | Austria | Bundesliga | `austria-bundesliga` |
| 6 | Belgium | Pro League | `pro-league` |
| 7 | Brazil | Serie A | `brazil-serie-a` |
| 8 | Brazil | Serie B | `brazil-serie-b` |
| 9 | Denmark | Superliga | `denmark-superliga` |
| 10 | France | Ligue 1 | `france-ligue-1` |
| 11 | France | Ligue 2 | `france-ligue-2` |
| 12 | Germany | Bundesliga | `germany-bundesliga` |
| 13 | Germany | 2. Bundesliga | `germany-2-bundesliga` |
| 14 | Italy | Serie A | `italy-serie-a` |
| 15 | Italy | Serie B | `italy-serie-b` |
| 16 | Netherlands | Eredivisie | `netherlands-eredivisie` |
| 17 | Portugal | Liga NOS | `portugal-liga-nos` |
| 18 | Saudi Arabia | Professional League | `saudi-professional-league` |
| 19 | Scotland | Premiership | `scotland-premiership` |
| 20 | Spain | La Liga | `spain-la-liga` |
| 21 | Switzerland | Super League | `switzerland-super-league` |
| 22 | Turkey | Süper Lig | `turkey-super-lig` |

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

Crie o arquivo `src/.env.local` (ou `.env.local` na raiz):

```bash
PY_BACKEND_URL=http://localhost:5001
```

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

# Gerar quadro-resumo profissional
GET http://localhost:5001/quadro-resumo?league=premier-league&date=week&incluir_simples=true&incluir_duplas=true&incluir_triplas=false&incluir_governanca=true
```

### Streamlit

Verifique se a interface está funcionando corretamente:

A **tela de login** deve aparecer ao acessar pela primeira vez. Após autenticação, a **tabela de jogos** deve mostrar os prognósticos com probabilidades e valores de λ nas tooltips. O **Quadro-Resumo Profissional** deve aparecer acima da tabela com opções para copiar e baixar. O **gráfico interativo** deve exibir as probabilidades de forma visual.

### Dashboard Next.js

Confirme o funcionamento do dashboard:

A **página inicial** deve carregar o `MultiLeagueSelector` e `MatchesList`. O **botão "Analisar"** deve chamar `/api/decision/pre` e exibir os picks recomendados. A **navegação** deve ser fluida e responsiva.

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
- **Claude Code:** `CLAUDE.md` na raiz do projeto com instruções, comandos e referências Context7

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
