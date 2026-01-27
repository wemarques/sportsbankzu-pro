# SportsBank Pro API

## Endpoints

- GET /health
- GET /leagues/
- GET /fixtures?leagues=la-liga,premier-league&date=today
- GET /quadro-resumo?league=premier-league&date=week&formato=detalhado
- POST /predictions/
- GET /predictions/{prediction_id}
- POST /decision/pre
- POST /probabilities
- POST /ml/predict
- GET /discover
 
### POST /ai/analyze-context
- Payload: { "home_team": "Arsenal", "away_team": "Chelsea", "news_summary": "..." }
- Resposta: { "analysis": { "injuries_key_players": {"home": "str", "away": "str"}, "pressure_level": {"home": "ALTA|MEDIA|BAIXA", "away": "ALTA|MEDIA|BAIXA"}, "confidence_adjustment": {"recommendation": "AUMENTAR|MANTER|REDUZIR", "reason": "str"} } }
 
### POST /ai/generate-report
- Payload: { "home_team": "Arsenal", "away_team": "Chelsea", "stats": { "lambda_home": 1.2, "lambda_away": 1.0 }, "market": "Over 2.5", "classification": "SAFE", "probability": 65 }
- Resposta: { "report": "texto" }

## Notas

- /fixtures retorna matches[] com odds, stats, h2h, forms e metadados.
- /quadro-resumo retorna quadro_texto e contagens (jogos, duplas, triplas).
 
## Contratos
 
### POST /decision/pre
- Payload: { matches: [ { id, leagueId, homeTeam, awayTeam, odds, stats, datetime } ] }
- Resposta: { picks: [ { market, prob, odds, ev, risk } ] }
 
### POST /predictions/
- Payload: { match_id, features: { ... } }
- Resposta: { picks: [ { market, prob, odds, ev, risk } ] }
 
### GET /predictions/{prediction_id}
- Resposta: { id, status }
