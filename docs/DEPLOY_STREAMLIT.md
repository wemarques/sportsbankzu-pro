# Deploy do Streamlit (Cloud)
## Secrets necessários
- BACKEND_URL: URL pública do backend FastAPI (ex.: https://api.seudominio.com)
- MISTRAL_API_KEY: chave da Mistral AI

## Como configurar no Streamlit Cloud
1. Acesse seu app no Streamlit Cloud
2. Abra “Settings” → “Secrets”
3. Cole em TOML:
```
[general]
BACKEND_URL = "https://api.seudominio.com"
MISTRAL_API_KEY = "sua_chave"
```
4. Salve e clique em “Rerun” / “Redeploy”

## Uso local
Crie `.streamlit/secrets.toml` (não versionado):
```
[general]
BACKEND_URL = "http://127.0.0.1:8000"
MISTRAL_API_KEY = "sua_chave"
```
Inicie backend e depois:
```
streamlit run streamlit/app.py
```

## Diagnóstico
- A página mostra `Backend: <URL>`. Se erro, ajuste BACKEND_URL.
- Em “Análise de Contexto (AI)”, insira resumo e gere relatório.
