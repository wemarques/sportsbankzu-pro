# Plano Detalhado de Execução

Estrutura nova:
- backend/{routes,services,models,auth,utils,migrations,modeling}
- frontend/{next/src,streamlit}
- tests/{unit,integration,e2e}
- config/, data/{fixtures,migrations}, docs/, docker/, .github/workflows

Mapeamento inicial:
- Autenticação: mover auth.py → backend/auth/authenticator.py; gerar_hash_senha.py → backend/auth/password_utils.py
- Utilitários: feature_engineering.py, pick_classifier.py → backend/utils/
- Serviços: audit_and_adjust.py → backend/services/; backend/audit.py → backend/services/audit_service.py
- Migrações: migrate_sqlite_to_postgres.py → backend/migrations/
- Frontend Streamlit: consolidar em frontend/streamlit/app.py
- Next.js: mover src/* → frontend/next/src e configs para frontend/next/
- Config: pytest.ini, futuros config.yaml → config/

Ordem de execução:
1) Criar diretórios
2) Copiar/mover arquivos conforme mapeamento
3) Atualizar imports (ex.: from auth → from backend.auth.authenticator)
4) Extrair rotas/serviços/modelos de backend/main.py para módulos dedicados
5) Remover duplicações (manter um Streamlit)
6) Testes e ajustes finais

Riscos e mitigações:
- Quebra de imports → rodar testes e checks após cada mudança
- Perda de funcionalidade → copiar antes de remover originais, validar incrementalmente
- Conflitos Next.js → mover com cuidado mantendo estrutura src/app e APIs
