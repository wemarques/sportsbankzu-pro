@echo off
REM run_eos_audit.bat — Caminho 1 do REGRA #173.
REM
REM Resolve DATABASE_URL a partir das environment variables da Lambda
REM sportsbank-pro-backend (RDS PostgreSQL) e roda o script de auditoria
REM end-of-season.
REM
REM Requisitos:
REM   - aws CLI configurado com perfil padrao (`aws configure`).
REM   - psycopg2-binary instalado: pip install psycopg2-binary.
REM
REM Uso:
REM   scripts\run_eos_audit.bat
REM   scripts\run_eos_audit.bat --days 90
REM
REM Output: reports\end_of_season_audit.md

setlocal

echo ================================================================
echo  EoS Audit (REGRA #173 — Caminho 1)
echo ================================================================
echo.

echo [1/3] Resolvendo DATABASE_URL via Lambda config...
for /f "tokens=*" %%i in ('aws lambda get-function-configuration --function-name sportsbank-pro-backend --region us-east-1 --query "Environment.Variables.DATABASE_URL" --output text 2^>nul') do set DATABASE_URL=%%i

if "%DATABASE_URL%"=="" (
    echo ERRO: nao consegui obter DATABASE_URL da Lambda.
    echo Verifique:
    echo   - aws CLI configurado: aws sts get-caller-identity
    echo   - permissao para lambda:GetFunctionConfiguration
    echo   - regiao us-east-1
    exit /b 1
)
if "%DATABASE_URL%"=="None" (
    echo ERRO: DATABASE_URL nao esta configurada na Lambda.
    exit /b 1
)
echo OK: DATABASE_URL resolvida.
echo.

echo [2/3] Verificando psycopg2-binary...
python -c "import psycopg2" 2>nul
if errorlevel 1 (
    echo Instalando psycopg2-binary...
    pip install psycopg2-binary
    if errorlevel 1 (
        echo ERRO: falha ao instalar psycopg2-binary.
        exit /b 1
    )
)
echo OK: psycopg2 disponivel.
echo.

echo [3/3] Rodando auditoria end-of-season...
python scripts\audit_end_of_season_picks.py %*
if errorlevel 1 (
    echo ERRO no script de auditoria.
    exit /b 1
)
echo.
echo ================================================================
echo  Relatorio salvo em: reports\end_of_season_audit.md
echo ================================================================

endlocal
