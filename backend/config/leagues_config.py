# Mapeamento das 22 Ligas solicitadas (País - Liga)
# Este dicionário associa o nome amigável ao nome técnico da FootyStats para busca via API.

# Aliases: IDs do frontend -> IDs do backend (para FootyStats API)
# Permite que o frontend use IDs como "spain-la-liga" e o backend resolva para a config correta
# Inclui as 22 ligas do frontend (mesmo as que já batem, para garantir cobertura)
LEAGUE_ID_ALIASES = {
    "premier-league": "premier-league",
    "championship": "championship",
    "a-league": "a-league",
    "primera-division": "primera-division",
    "pro-league": "pro-league",
    "spain-la-liga": "la-liga",
    "italy-serie-a": "serie-a",
    "italy-serie-b": "serie-b",
    "germany-bundesliga": "bundesliga",
    "germany-2-bundesliga": "2-bundesliga",
    "france-ligue-1": "ligue-1",
    "france-ligue-2": "ligue-2",
    "brazil-serie-a": "brasileirao-serie-a",
    "brazil-serie-b": "brasileirao-serie-b",
    "netherlands-eredivisie": "eredivisie",
    "portugal-liga-nos": "primeira-liga",
    "saudi-professional-league": "professional-league",
    "scotland-premiership": "premiership",
    "austria-bundesliga": "austrian-bundesliga",
    "denmark-superliga": "superliga",
    "switzerland-super-league": "super-league",
    "turkey-super-lig": "super-lig",
}

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
    {"country": "Portugal", "name": "Primeira Liga", "id": "primeira-liga",
     "alt_names": ["liga nos", "liga portugal", "liga betclic"]},
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
    """Busca configuração de uma liga pelo ID interno.
    Aceita IDs do frontend (ex: spain-la-liga) e resolve para a config FootyStats."""
    resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
    for league in LEAGUES_CONFIG:
        if league["id"] == resolved_id:
            return league
    return None
