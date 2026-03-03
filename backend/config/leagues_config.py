# Mapeamento das 33 Ligas monitoradas (País - Liga)
# Este dicionário associa o nome amigável ao nome técnico da FootyStats para busca via API.
# Expansão v3.5: 22 ligas originais + 11 novas ligas (Safe Bets Engine)

# Aliases: IDs do frontend -> IDs do backend (para FootyStats API)
# Permite que o frontend use IDs como "spain-la-liga" e o backend resolva para a config correta
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
    # --- 11 new leagues (Safe Bets Engine v3.5) ---
    "japan-j-league": "j-league",
    "south-korea-k-league": "k-league",
    "norway-eliteserien": "eliteserien",
    "sweden-allsvenskan": "allsvenskan",
    "uae-pro-league": "uae-pro-league",
    "netherlands-eerste-divisie": "eerste-divisie",
    "greece-super-league": "super-league-greece",
    "usa-mls": "mls",
    "czech-first-league": "czech-first-league",
    "colombia-primera-a": "colombian-primera-a",
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

    # RESTO DO MUNDO (existentes)
    {"country": "Argentina", "name": "Primera División", "id": "primera-division"},
    {"country": "Australia", "name": "A-League", "id": "a-league"},
    {"country": "Saudi Arabia", "name": "Professional League", "id": "professional-league"},

    # --- 11 NOVAS LIGAS (Safe Bets Engine v3.5) ---
    # ÁSIA
    {"country": "Japan", "name": "J-League", "id": "j-league",
     "alt_names": ["j1-league", "meiji yasuda j1 league"]},
    {"country": "South Korea", "name": "K-League", "id": "k-league",
     "alt_names": ["k league 1", "hana 1 bank k league 1"]},

    # NÓRDICAS
    {"country": "Norway", "name": "Eliteserien", "id": "eliteserien",
     "alt_names": ["toppserien", "norwegian premier league"]},
    {"country": "Sweden", "name": "Allsvenskan", "id": "allsvenskan",
     "alt_names": ["swedish premier league"]},

    # ORIENTE MÉDIO
    {"country": "UAE", "name": "UAE Pro League", "id": "uae-pro-league",
     "alt_names": ["arabian gulf league", "adnoc pro league"]},

    # EUROPA (adicionais)
    {"country": "Netherlands", "name": "Eerste Divisie", "id": "eerste-divisie",
     "alt_names": ["dutch second division", "keuken kampioen divisie"]},
    {"country": "Greece", "name": "Super League", "id": "super-league-greece",
     "alt_names": ["super league 1", "greek super league"]},
    {"country": "Czech Republic", "name": "Czech First League", "id": "czech-first-league",
     "alt_names": ["chance liga", "fortuna liga", "first league"]},

    # AMÉRICAS (adicionais)
    {"country": "USA", "name": "MLS", "id": "mls",
     "alt_names": ["major league soccer"]},
    {"country": "Colombia", "name": "Campeonato Colombiano", "id": "colombian-primera-a",
     "alt_names": ["liga betplay", "primera a", "categoría primera a"]},
]


def get_league_config(league_id: str):
    """Busca configuração de uma liga pelo ID interno.
    Aceita IDs do frontend (ex: spain-la-liga) e resolve para a config FootyStats."""
    resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
    for league in LEAGUES_CONFIG:
        if league["id"] == resolved_id:
            return league
    return None
