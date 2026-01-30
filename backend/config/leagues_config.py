# Mapeamento das 22 Ligas solicitadas (País - Liga)
# Este dicionário associa o nome amigável ao nome técnico da FootyStats para busca via API.

LEAGUES_CONFIG = [
    {"country": "England", "name": "Premier League", "id": "premier-league"},
    {"country": "England", "name": "Championship", "id": "championship"},
    {"country": "Argentina", "name": "Primera Division", "id": "primera-division"},
    {"country": "Australia", "name": "A-League", "id": "a-league"},
    {"country": "Austria", "name": "Bundesliga", "id": "austria-bundesliga"},
    {"country": "Belgium", "name": "Pro League", "id": "pro-league"},
    {"country": "Brazil", "name": "Serie A", "id": "brazil-serie-a"},
    {"country": "Brazil", "name": "Serie B", "id": "brazil-serie-b"},
    {"country": "Denmark", "name": "Superliga", "id": "denmark-superliga"},
    {"country": "France", "name": "Ligue 1", "id": "france-ligue-1"},
    {"country": "France", "name": "Ligue 2", "id": "france-ligue-2"},
    {"country": "Germany", "name": "Bundesliga", "id": "germany-bundesliga"},
    {"country": "Germany", "name": "2. Bundesliga", "id": "germany-2-bundesliga"},
    {"country": "Italy", "name": "Serie A", "id": "italy-serie-a"},
    {"country": "Italy", "name": "Serie B", "id": "italy-serie-b"},
    {"country": "Netherlands", "name": "Eredivisie", "id": "netherlands-eredivisie"},
    {"country": "Portugal", "name": "Liga NOS", "id": "portugal-liga-nos"},
    {"country": "Saudi Arabia", "name": "Professional League", "id": "saudi-professional-league"},
    {"country": "Scotland", "name": "Premiership", "id": "scotland-premiership"},
    {"country": "Spain", "name": "La Liga", "id": "spain-la-liga"},
    {"country": "Switzerland", "name": "Super League", "id": "switzerland-super-league"},
    {"country": "Turkey", "name": "Süper Lig", "id": "turkey-super-lig"},
]

def get_league_config(league_id: str):
    """Busca configuração de uma liga pelo ID interno."""
    for league in LEAGUES_CONFIG:
        if league["id"] == league_id:
            return league
    return None
