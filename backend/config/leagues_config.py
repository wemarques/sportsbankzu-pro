# Mapeamento das 22 Ligas solicitadas (País - Liga)
# Este dicionário associa o nome amigável ao nome técnico da FootyStats para busca via API.

LEAGUES_CONFIG = [
    # INGLATERRA
    {"country": "England", "name": "Premier League", "id": "premier-league"},
    {"country": "England", "name": "Championship", "id": "championship"},
    {"country": "England", "name": "League One", "id": "league-one"},
    {"country": "England", "name": "League Two", "id": "league-two"},
    
    # ESPANHA
    {"country": "Spain", "name": "La Liga", "id": "la-liga"},
    {"country": "Spain", "name": "Segunda División", "id": "segunda-division"},
    
    # ITÁLIA
    {"country": "Italy", "name": "Serie A", "id": "serie-a"},
    {"country": "Italy", "name": "Serie B", "id": "serie-b"},
    
    # ALEMANHA
    {"country": "Germany", "name": "Bundesliga", "id": "bundesliga"},
    {"country": "Germany", "name": "2. Bundesliga", "id": "2-bundesliga"},
    
    # FRANÇA
    {"country": "France", "name": "Ligue 1", "id": "ligue-1"},
    {"country": "France", "name": "Ligue 2", "id": "ligue-2"},
    
    # BRASIL
    {"country": "Brazil", "name": "Serie A", "id": "brasileirao-serie-a"},
    {"country": "Brazil", "name": "Serie B", "id": "brasileirao-serie-b"},
    
    # OUTROS EUROPA
    {"country": "Netherlands", "name": "Eredivisie", "id": "eredivisie"},
    {"country": "Portugal", "name": "Primeira Liga", "id": "primeira-liga"},
    {"country": "Turkey", "name": "Süper Lig", "id": "super-lig"},
    {"country": "Belgium", "name": "Pro League", "id": "pro-league"},
    {"country": "Scotland", "name": "Premiership", "id": "premiership"},
    {"country": "Austria", "name": "Bundesliga", "id": "austrian-bundesliga"},
    {"country": "Denmark", "name": "Superliga", "id": "superliga"},
    {"country": "Switzerland", "name": "Super League", "id": "super-league"},
    
    # RESTO DO MUNDO
    {"country": "Argentina", "name": "Primera División", "id": "primera-division"},
    {"country": "Australia", "name": "A-League", "id": "a-league"},
    {"country": "Saudi Arabia", "name": "Professional League", "id": "professional-league"}
]

def get_league_config(league_id: str):
    """Busca configuração de uma liga pelo ID interno."""
    for league in LEAGUES_CONFIG:
        if league["id"] == league_id:
            return league
    return None
