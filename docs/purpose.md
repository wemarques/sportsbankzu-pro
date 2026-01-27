# Propósito dos Arquivos

app.py — Interface Streamlit principal com autenticação e consumo da API backend
auth.py — Módulo de autenticação (login/logout, verificação de credenciais)
feature_engineering.py — Rotinas de engenharia de features
pick_classifier.py — Classificação/seleção de picks
audit_and_adjust.py — Script de auditoria e ajustes operacionais
migrate_sqlite_to_postgres.py — Migração de base local para Postgres
backend/main.py — Servidor FastAPI com rotas e lógica atual consolidada
backend/audit.py — Funções de auditoria
backend/summary_report.py — Geração de quadro-resumo tabular
backend/modeling/* — Cálculos estatísticos (Poisson, λ, filtros, validações)
backend/lambda_handler.py — Entrypoint para execução/lambda
streamlit/app.py — Interface alternativa Streamlit focada em consumo da API
src/* — Dashboard Next.js (páginas, componentes e APIs)
tests/* — Testes unitários dos módulos de modelagem
scripts/* — Utilitários de desenvolvimento e automação
pytest.ini — Configuração de testes
requirements.txt — Dependências Python de alto nível
solucao_autenticacao_streamlit.md — Documento de autenticação Streamlit
