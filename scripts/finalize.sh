#!/usr/bin/env bash
# finalize.sh — Sincroniza arquivos, commita e faz push para GitHub.
# Uso: bash scripts/finalize.sh "mensagem do commit (#NNN)"
# Ou sem argumento para commit interativo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT_ROOT="$(cd "$REPO_ROOT/.." && pwd)"

echo "=== 1/4 Sincronizando arquivos espelhados ==="

# REGRAS
if [ -f "$REPO_ROOT/docs/REGRAS_CORRECAO_SISTEMA.md" ]; then
    cp "$REPO_ROOT/docs/REGRAS_CORRECAO_SISTEMA.md" "$PARENT_ROOT/docs/REGRAS_CORRECAO_SISTEMA.md"
    echo "  REGRAS: sportsbankzu-pro -> raiz OK"
fi

# CLAUDE.md
if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    cp "$REPO_ROOT/CLAUDE.md" "$PARENT_ROOT/CLAUDE.md"
    echo "  CLAUDE.md: sportsbankzu-pro -> raiz OK"
fi

echo ""
echo "=== 2/4 Staging alterações ==="
cd "$REPO_ROOT"
git add -A
git status --short

# Check if there are changes to commit
if git diff --cached --quiet 2>/dev/null; then
    echo "  Nenhuma alteração para commitar."
    exit 0
fi

echo ""
echo "=== 3/4 Commit ==="
if [ $# -ge 1 ]; then
    COMMIT_MSG="$1"
else
    echo "Mensagem do commit (ou Ctrl+C para cancelar):"
    read -r COMMIT_MSG
fi

git commit -m "$COMMIT_MSG

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

echo ""
echo "=== 4/4 Push para GitHub ==="
git push origin main

echo ""
echo "=== Finalizado ==="
echo "Commit: $(git log --oneline -1)"
echo ""
echo "Se alterou backend, execute tambem:"
echo "  python scripts/deploy_lambda.py"
