# SportsBank Pro - Deploy Streamlit
Calculo de prognosticos esportivos com backend FastAPI e Streamlit.

## Visão Geral
- Frontend Streamlit (app.py) consome o backend FastAPI (fixtures, decision/pre, quadro-resumo).
- O backend pode usar CSVs locais ou fontes externas e expõe probabilidades (1X2, O/U, BTTS), lambdas e estatísticas.
- O Quadro-Resumo Profissional gera um texto formatado com mercados, duplas/triplas e governança.
- Revisão desta documentação: 2026-01-18.

## Pré-requisitos
- Python 3.10+
- Backend FastAPI acessível publicamente ou local (http://localhost:5001)
- Secrets configurados para o Streamlit (BACKEND_URL)
- Para uso em produção, defina `FUTEBOL_ROOT` (ou `DATA_ROOT`) e/ou `FUTEBOL_DATA_DIR` no backend para apontar para o storage correto.
- Node.js 18+ (para o dashboard Next)

## Rodar localmente
1) Inicie o backend:

```bash
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn pandas numpy
uvicorn backend.main:app --reload --port 5001
```

2) Inicie o Streamlit:

```bash
pip install -r requirements.txt
set BACKEND_URL=http://localhost:5001
streamlit run app.py
```

3) Acesse:
- http://localhost:8501/

4) Inicie o dashboard (Next):

```bash
npm i
npm run dev
```

5) Acesse:
- http://localhost:3000/

## Configuração de Secrets (local)
- Crie o arquivo .streamlit/secrets.toml na raiz:

```toml
BACKEND_URL = "http://localhost:5001"
```

## Variáveis do dashboard (Next)
- Crie `src/.env.local` (ou `.env.local` na raiz):

```bash
PY_BACKEND_URL=http://localhost:5001
```

## Deploy no Streamlit Cloud
1) Suba este repositório no GitHub/GitLab.
2) Crie um novo app apontando para app.py na raiz.
3) Em Settings → Secrets, adicione:

```toml
BACKEND_URL = "https://seu-backend-publico:5001"
```

4) Aguarde a build; o app estará disponível em:
- https://{nome-do-app}-{seu-usuario}.streamlit.app

## Variáveis de ambiente do backend
- `FUTEBOL_ROOT` (ou `DATA_ROOT`): raiz do projeto/dados (ex: `/data/futebol`).
- `FUTEBOL_DATA_DIR`: caminho direto para a pasta `data` (ex: `/data/futebol/data`).

## Verificações rápidas
- Backend:
  - `GET http://localhost:5001/fixtures?leagues=premier-league,la-liga&date=today`
  - `GET http://localhost:5001/discover`
  - `GET http://localhost:5001/quadro-resumo?league=premier-league&date=week&incluir_simples=true&incluir_duplas=true&incluir_triplas=false&incluir_governanca=true`
- Streamlit:
  - A tabela mostra jogos e o gráfico exibe probabilidades e `λ` nas tooltips.
  - O Quadro-Resumo Profissional aparece acima da tabela e permite copiar/baixar.
- Dashboard:
  - Página inicial carrega `MultiLeagueSelector` e `MatchesList`.
  - Botão “Analisar” chama `/api/decision/pre` e exibe picks.

## Ajustes opcionais
- CORS no FastAPI caso o backend seja público:
  - Adicione middleware permitindo origem do Streamlit Cloud.
- CSVs remotos:
  - Se o backend não tiver acesso local aos CSVs, use storage público ou um endpoint.

## Observações
- Se CSVs forem usados pelo backend, eles precisam estar acessíveis para o servidor (ou migrados para storage público/endpoint).
- Quando BACKEND_URL não responder, o app exibirá tabelas vazias; verifique logs e conectividade.
- A tela mostra a "Última atualização (fonte)" quando o backend fornece `lastUpdated`.
