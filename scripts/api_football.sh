#!/usr/bin/env bash
# api_football.sh — wrapper para queries debug a API-Football v3.
#
# A API_FOOTBALL_KEY e resolvida on-demand da Lambda env via aws CLI.
# NUNCA commitar key em codigo. NUNCA fazer 'export API_FOOTBALL_KEY=...'
# em shell interativa (vai parar em ~/.bash_history).
#
# Uso:
#   scripts/api_football.sh                          # default: /status
#   scripts/api_football.sh status
#   scripts/api_football.sh standings --data-urlencode "league=39" --data-urlencode "season=2025"
#   scripts/api_football.sh fixtures --data-urlencode "league=71" --data-urlencode "season=2025"
#   scripts/api_football.sh teams --data-urlencode "league=39" --data-urlencode "season=2025"
#
# Custo: ~500ms por invocacao para chamada AWS (resolve key). Se rodar
# multiplas queries em sequencia, considerar setar a key na shell (NAO
# via export — usar inline subshell):
#   KEY=$(scripts/api_football.sh _key) bash -c 'curl ... -H "x-rapidapi-key: $KEY" ...'
set -euo pipefail

if [[ -z "${API_FOOTBALL_KEY:-}" ]]; then
  API_FOOTBALL_KEY=$(aws lambda get-function-configuration \
    --function-name sportsbank-pro-backend --region us-east-1 \
    --query 'Environment.Variables.API_FOOTBALL_KEY' --output text)
fi

if [[ -z "$API_FOOTBALL_KEY" || "$API_FOOTBALL_KEY" == "None" ]]; then
  echo "ERRO: nao consegui resolver API_FOOTBALL_KEY da Lambda config." >&2
  echo "  Verificar: aws sts get-caller-identity" >&2
  echo "  Verificar: aws lambda get-function-configuration --function-name sportsbank-pro-backend --region us-east-1" >&2
  exit 1
fi

ENDPOINT="${1:-status}"
shift || true

# Modo especial: '_key' apenas imprime a key (para uso em subshell)
if [[ "$ENDPOINT" == "_key" ]]; then
  echo "$API_FOOTBALL_KEY"
  exit 0
fi

curl -s -H "x-rapidapi-key: $API_FOOTBALL_KEY" \
  "https://v3.football.api-sports.io/$ENDPOINT" "$@" \
  | python -m json.tool
