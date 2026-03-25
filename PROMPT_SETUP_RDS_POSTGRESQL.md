# PROMPT — Configurar AWS RDS PostgreSQL para o Backend Lambda

## CONTEXTO

O backend SportsBank Pro roda na AWS Lambda e usa SQLite efêmero em `/tmp/audit.db`. Isso causa perda de dados (thresholds, correções, auditorias) em cada cold start da Lambda. O sistema já tem suporte completo a PostgreSQL em `backend/audit.py` — só precisa de um RDS e variáveis de ambiente.

## OBJETIVO

Criar um RDS PostgreSQL na AWS (free tier), configurar o acesso da Lambda, e setar as variáveis de ambiente para que o `audit.py` use PostgreSQL em vez de SQLite.

---

## PASSO 1 — Criar instância RDS PostgreSQL

Rodar via AWS CLI (requer AWS CLI configurado):

```bash
# Criar Security Group para o RDS
aws ec2 create-security-group \
  --group-name sportsbank-rds-sg \
  --description "SportsBank RDS PostgreSQL access" \
  --region us-east-1

# Obter o ID do security group criado
SG_ID=$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values=sportsbank-rds-sg \
  --query "SecurityGroups[0].GroupId" \
  --output text \
  --region us-east-1)

echo "Security Group ID: $SG_ID"

# Liberar porta 5432 para a Lambda (acessível pela VPC/internet)
# Para simplificar, liberamos 0.0.0.0/0 — em produção, restringir ao CIDR da VPC da Lambda
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5432 \
  --cidr 0.0.0.0/0 \
  --region us-east-1

# Criar instância RDS PostgreSQL (Free Tier)
aws rds create-db-instance \
  --db-instance-identifier sportsbank-pro-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username postgres \
  --master-user-password "Galaxy10@" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids $SG_ID \
  --publicly-accessible \
  --backup-retention-period 7 \
  --no-multi-az \
  --region us-east-1 \
  --tags Key=Project,Value=SportsBank-Pro

echo "RDS criando... aguarde 5-10 minutos"
```

Aguardar a instância ficar disponível:
```bash
aws rds wait db-instance-available \
  --db-instance-identifier sportsbank-pro-db \
  --region us-east-1

echo "RDS pronto!"
```

Obter o endpoint do RDS:
```bash
RDS_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier sportsbank-pro-db \
  --query "DBInstances[0].Endpoint.Address" \
  --output text \
  --region us-east-1)

echo "RDS Host: $RDS_HOST"
echo "DATABASE_URL: postgresql://postgres:Galaxy10%40@${RDS_HOST}:5432/postgres"
```

---

## PASSO 2 — Configurar variáveis de ambiente na Lambda

```bash
# Obter o RDS host primeiro (do passo anterior)
RDS_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier sportsbank-pro-db \
  --query "DBInstances[0].Endpoint.Address" \
  --output text \
  --region us-east-1)

# Atualizar variáveis de ambiente da Lambda
# IMPORTANTE: preservar as variáveis existentes (MISTRAL, AWS, FOOTYSTATS keys)
# Primeiro, obter as variáveis existentes:
EXISTING_ENV=$(aws lambda get-function-configuration \
  --function-name sportsbank-pro-backend \
  --query "Environment.Variables" \
  --output json \
  --region us-east-1)

echo "Variáveis existentes: $EXISTING_ENV"

# Agora adicionar as variáveis de PostgreSQL SEM apagar as existentes
# Usar jq para merge (ou manualmente):
aws lambda update-function-configuration \
  --function-name sportsbank-pro-backend \
  --region us-east-1 \
  --environment "Variables={
    PGHOST=${RDS_HOST},
    PGPORT=5432,
    PGDATABASE=postgres,
    PGUSER=postgres,
    PGPASSWORD=Galaxy10@,
    DATABASE_URL=postgresql://postgres:Galaxy10%40@${RDS_HOST}:5432/postgres,
    $(echo $EXISTING_ENV | python -c "import sys,json; d=json.load(sys.stdin); print(','.join(f'{k}={v}' for k,v in d.items()))")
  }"
```

NOTA: O comando acima precisa preservar as variáveis existentes (MISTRAL_API_KEY, FOOTYSTATS_API_KEY, AWS keys, etc). Se o merge automático falhar, adicionar manualmente no console AWS:
1. Abrir AWS Console → Lambda → sportsbank-pro-backend → Configuration → Environment variables
2. Adicionar estas variáveis SEM remover as existentes:
   - `PGHOST` = (endpoint do RDS, ex: sportsbank-pro-db.xxxx.us-east-1.rds.amazonaws.com)
   - `PGPORT` = 5432
   - `PGDATABASE` = postgres
   - `PGUSER` = postgres
   - `PGPASSWORD` = Galaxy10@
   - `DATABASE_URL` = postgresql://postgres:Galaxy10%40@ENDPOINT:5432/postgres

---

## PASSO 3 — Criar tabelas no PostgreSQL

O `audit.py` já tem `init_db()` que cria as tabelas automaticamente na primeira conexão. Mas para garantir, executar manualmente:

```bash
# Testar conexão e criar tabelas
psql "postgresql://postgres:Galaxy10%40@${RDS_HOST}:5432/postgres" -c "
CREATE TABLE IF NOT EXISTS audit_results (
    id SERIAL PRIMARY KEY,
    match_id TEXT NOT NULL,
    league TEXT,
    audit_data JSONB,
    match_status TEXT DEFAULT 'scheduled',
    audited_by TEXT DEFAULT 'system',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS thresholds (
    id SERIAL PRIMARY KEY,
    market TEXT UNIQUE NOT NULL,
    safe_threshold REAL,
    neutro_threshold REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS corrections (
    id SERIAL PRIMARY KEY,
    match_id TEXT,
    league TEXT,
    correction_type TEXT,
    parameter_name TEXT,
    old_value REAL,
    new_value REAL,
    suggested_by TEXT DEFAULT 'mistral_audit',
    applied_by TEXT DEFAULT 'system',
    audit_confidence INTEGER DEFAULT 0,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_match ON audit_results(match_id);
CREATE INDEX IF NOT EXISTS idx_audit_league ON audit_results(league);
CREATE INDEX IF NOT EXISTS idx_corrections_match ON corrections(match_id);
CREATE INDEX IF NOT EXISTS idx_corrections_league ON corrections(league);
"

echo "Tabelas criadas com sucesso!"
```

Se `psql` não estiver disponível localmente, pode rodar via Python:
```python
import psycopg2

conn = psycopg2.connect(
    host="ENDPOINT_DO_RDS",
    database="postgres",
    user="postgres",
    password="Galaxy10@",
    port=5432
)
conn.autocommit = True
cursor = conn.cursor()
# Executar os CREATE TABLE acima
```

---

## PASSO 4 — Verificar que audit.py usa PostgreSQL

O `backend/audit.py` já tem a lógica correta:

```python
def _use_postgres() -> bool:
    if not psycopg2:
        return False
    if os.getenv("DATABASE_URL"):
        return True
    # Check individual vars
    return all(DEFAULT_PG_CONFIG.get(k) for k in ("host", "database", "user", "password"))
```

Quando `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` estiverem setados na Lambda, `_use_postgres()` retorna `True` e todas as operações (log_audit, log_correction, get_thresholds, etc) usam PostgreSQL em vez de SQLite.

NÃO é necessário alterar código do backend — apenas setar as variáveis de ambiente.

---

## PASSO 5 — Redesployar Lambda e testar

```bash
# Redesployar para que a Lambda carregue as novas variáveis
python scripts/deploy_lambda.py

# Testar health
curl -s "https://4eksz2n7h5.execute-api.us-east-1.amazonaws.com/prod/health"

# Testar se PostgreSQL está conectado — auditar qualquer jogo
# A resposta deve funcionar sem erro de banco
curl -s "https://4eksz2n7h5.execute-api.us-east-1.amazonaws.com/prod/api/ai/match/test-123/audit" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"predictions": [], "ai_summary": {}}'
```

---

## PASSO 6 — Configurar .env local para desenvolvimento

Criar/atualizar `.env` na raiz do projeto para desenvolvimento local:

```bash
# .env (NÃO commitar — já está no .gitignore)
DATABASE_URL=postgresql://postgres:Galaxy10%40@localhost:5432/postgres
PGHOST=localhost
PGPORT=5432
PGDATABASE=postgres
PGUSER=postgres
PGPASSWORD=Galaxy10@
```

Isso permite usar o PostgreSQL local em desenvolvimento e o RDS em produção.

---

## CUSTOS ESTIMADOS

RDS db.t3.micro (Free Tier elegível):
- **Primeiros 12 meses**: GRÁTIS (750 horas/mês + 20GB storage)
- **Após free tier**: ~$15-18/mês (db.t3.micro on-demand)
- **Storage**: 20GB gp3 incluído no free tier, depois ~$2.30/mês
- **Backup**: 7 dias incluído

---

## SEGURANÇA — IMPORTANTE

1. A senha `Galaxy10@` está em texto plano nos comandos acima. Em produção, usar AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name sportsbank-pro/db-password \
  --secret-string "Galaxy10@" \
  --region us-east-1
```

2. O security group está aberto para `0.0.0.0/0` na porta 5432. Em produção, restringir ao CIDR da VPC da Lambda ou usar VPC endpoints.

3. NÃO commitar `.env` com credenciais no Git. Verificar que `.env` está no `.gitignore`.

---

## VERIFICAÇÃO FINAL

Após todos os passos:

1. `aws rds describe-db-instances --db-instance-identifier sportsbank-pro-db` → Status: available
2. `curl health endpoint` → responde sem erro
3. Auditar um jogo no dashboard → auditoria salva no PostgreSQL
4. Aplicar correção → persiste após cold start da Lambda
5. Verificar no psql: `SELECT count(*) FROM audit_results;` → deve ter registros

Se tudo funcionar, as correções de auditoria, thresholds e lambda_multipliers vão persistir permanentemente em vez de se perderem em cold starts.
