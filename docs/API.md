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
