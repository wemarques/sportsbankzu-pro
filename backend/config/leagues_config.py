# Mapeamento das 34 Ligas monitoradas (País - Liga)
# Este dicionário associa o nome amigável ao nome técnico da FootyStats para busca via API.
# Expansão v3.5: 22 ligas originais + 11 novas ligas (Safe Bets Engine) + Liga MX

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
    "spain-segunda-division": "segunda-division",
    "england-league-one": "league-one",
    "england-league-two": "league-two",
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
    "mexico-liga-mx": "liga-mx",
}

LEAGUES_CONFIG = [
    # INGLATERRA
    {"country": "England", "name": "Premier League", "id": "premier-league"},
    {"country": "England", "name": "Championship", "id": "championship"},
    {"country": "England", "name": "League One", "id": "league-one",
     "alt_names": ["efl league one", "sky bet league one"]},
    {"country": "England", "name": "League Two", "id": "league-two",
     "alt_names": ["efl league two", "sky bet league two"]},

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
    {"country": "Brazil", "name": "Serie B", "id": "brasileirao-serie-b",
     "alt_names": ["brasileirão série b", "campeonato brasileiro série b"]},

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
    {"country": "Japan", "name": "J1 League", "id": "j-league",
     "alt_names": ["j1 league", "j-league", "meiji yasuda j1 league"]},
    {"country": "South Korea", "name": "K-League", "id": "k-league",
     "alt_names": ["k league 1", "hana 1 bank k league 1"]},

    # NÓRDICAS
    {"country": "Norway", "name": "Eliteserien", "id": "eliteserien",
     "alt_names": ["toppserien", "norwegian premier league", "norway eliteserien"]},
    {"country": "Sweden", "name": "Allsvenskan", "id": "allsvenskan",
     "alt_names": ["swedish premier league", "sweden allsvenskan"]},

    # ORIENTE MÉDIO
    {"country": "UAE", "name": "Arabian Gulf League", "id": "uae-pro-league",
     "alt_names": ["uae pro league", "adnoc pro league", "uae arabian gulf league"]},

    # EUROPA (adicionais)
    {"country": "Netherlands", "name": "Eerste Divisie", "id": "eerste-divisie",
     "alt_names": ["dutch second division", "keuken kampioen divisie"]},
    {"country": "Greece", "name": "Super League", "id": "super-league-greece",
     "alt_names": ["super league 1", "greek super league", "greece super league"]},
    {"country": "Czech Republic", "name": "Czech First League", "id": "czech-first-league",
     "alt_names": ["chance liga", "fortuna liga", "first league", "czech republic first league"]},

    # AMÉRICAS (adicionais)
    {"country": "USA", "name": "MLS", "id": "mls",
     "alt_names": ["major league soccer"]},
    {"country": "Colombia", "name": "Categoria Primera A", "id": "colombian-primera-a",
     "alt_names": ["liga betplay", "primera a", "categoría primera a", "colombia categoria primera a", "campeonato colombiano"]},

    # MÉXICO
    {"country": "Mexico", "name": "Liga MX", "id": "liga-mx",
     "alt_names": ["liga bbva mx", "liga bbva bancomer", "primera division de mexico"]},
]


# API-Football v3 league IDs (https://v3.football.api-sports.io/leagues)
# Maps internal league ID -> API-Football league numeric ID
API_FOOTBALL_LEAGUE_IDS = {
    # ENGLAND
    "premier-league": 39,
    "championship": 40,
    "league-one": 41,
    "league-two": 42,
    # SPAIN
    "la-liga": 140,
    "segunda-division": 141,
    # ITALY
    "serie-a": 135,
    "serie-b": 136,
    # GERMANY
    "bundesliga": 78,
    "2-bundesliga": 79,
    # FRANCE
    "ligue-1": 61,
    "ligue-2": 62,
    # BRAZIL
    "brasileirao-serie-a": 71,
    "brasileirao-serie-b": 72,
    # NETHERLANDS
    "eredivisie": 88,
    "eerste-divisie": 89,
    # PORTUGAL
    "primeira-liga": 94,
    # TURKEY
    "super-lig": 203,
    # BELGIUM
    "pro-league": 144,
    # SCOTLAND
    "premiership": 179,
    # AUSTRIA
    "austrian-bundesliga": 218,
    # DENMARK
    "superliga": 120,
    # SWITZERLAND
    "super-league": 207,
    # ARGENTINA
    "primera-division": 128,
    # AUSTRALIA
    "a-league": 188,
    # SAUDI ARABIA
    "professional-league": 307,
    # JAPAN
    "j-league": 98,
    # SOUTH KOREA
    "k-league": 292,
    # NORWAY
    "eliteserien": 103,
    # SWEDEN
    "allsvenskan": 113,
    # UAE
    "uae-pro-league": 305,
    # GREECE
    "super-league-greece": 197,
    # CZECH REPUBLIC
    "czech-first-league": 345,
    # USA
    "mls": 253,
    # COLOMBIA
    "colombian-primera-a": 239,
    # MEXICO
    "liga-mx": 262,
}


def get_api_football_league_id(league_id: str) -> int | None:
    """Returns the API-Football numeric league ID for a given internal league ID."""
    resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
    return API_FOOTBALL_LEAGUE_IDS.get(resolved_id)


# Leagues that use calendar-year seasons (Jan-Dec) instead of mid-year (Aug-May).
# For these leagues, the API-Football season parameter = calendar year.
# Example: Brasileirão 2026 runs Jan-Dec 2026, season param = 2026.
# European leagues (Premier League 2025/26) started Aug 2025, season param = 2025.
CALENDAR_YEAR_LEAGUES = {
    # BRAZIL
    "brasileirao-serie-a", "brasileirao-serie-b",
    # ARGENTINA (Apertura/Clausura within calendar year)
    "primera-division",
    # JAPAN
    "j-league",
    # SOUTH KOREA
    "k-league",
    # NORWAY (Mar-Nov)
    "eliteserien",
    # SWEDEN (Apr-Nov)
    "allsvenskan",
    # USA (Feb-Dec)
    "mls",
    # COLOMBIA (Feb-Dec)
    "colombian-primera-a",
    # AUSTRALIA (Oct-May, but API-Football uses start year = calendar year)
    "a-league",
    # MEXICO (Apertura/Clausura, but API-Football uses calendar year)
    "liga-mx",
    # SAUDI ARABIA (Aug-May, BUT API-Football uses the start year like European)
    # NOT included — follows European convention
    # UAE
    "uae-pro-league",
}


def get_season_for_league(league_id: str) -> int:
    """Return the correct API-Football season parameter for a league.

    Calendar-year leagues (Brazil, Japan, MLS, etc.): always use current year.
    European mid-year leagues: use current year if month >= 7, else previous year.
    """
    from datetime import datetime, timezone
    resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
    now = datetime.now(timezone.utc)

    if resolved_id in CALENDAR_YEAR_LEAGUES:
        return now.year
    # European convention: season starts mid-year
    return now.year if now.month >= 7 else now.year - 1


def get_league_config(league_id: str):
    """Busca configuração de uma liga pelo ID interno.
    Aceita IDs do frontend (ex: spain-la-liga) e resolve para a config FootyStats."""
    resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
    for league in LEAGUES_CONFIG:
        if league["id"] == resolved_id:
            return league
    return None
