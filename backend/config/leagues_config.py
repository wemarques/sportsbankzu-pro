# Mapeamento das 22 Ligas monitoradas (País - Liga)
# Reduced from 37 to 22 in #078r — removed 15 with insufficient data.

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
    "brazil-serie-a": "brasileirao-serie-a",
    "brazil-serie-b": "brasileirao-serie-b",
    "netherlands-eredivisie": "eredivisie",
    "portugal-liga-nos": "primeira-liga",
    "scotland-premiership": "premiership",
    "denmark-superliga": "superliga",
    "turkey-super-lig": "super-lig",
    "england-league-one": "league-one",
    "usa-mls": "mls",
    "colombia-primera-a": "colombian-primera-a",
    "mexico-liga-mx": "liga-mx",
}

LEAGUES_CONFIG = [
    # INGLATERRA
    {"country": "England", "name": "Premier League", "id": "premier-league"},
    {"country": "England", "name": "Championship", "id": "championship"},
    {"country": "England", "name": "League One", "id": "league-one",
     "alt_names": ["efl league one", "sky bet league one"]},

    # ESPANHA
    {"country": "Spain", "name": "La Liga", "id": "la-liga"},

    # ITÁLIA
    {"country": "Italy", "name": "Serie A", "id": "serie-a"},
    {"country": "Italy", "name": "Serie B", "id": "serie-b"},

    # ALEMANHA
    {"country": "Germany", "name": "Bundesliga", "id": "bundesliga"},
    {"country": "Germany", "name": "2. Bundesliga", "id": "2-bundesliga"},

    # FRANÇA
    {"country": "France", "name": "Ligue 1", "id": "ligue-1"},

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
    {"country": "Denmark", "name": "Superliga", "id": "superliga"},

    # AMÉRICAS
    {"country": "Argentina", "name": "Primera División", "id": "primera-division"},
    {"country": "Australia", "name": "A-League", "id": "a-league"},
    {"country": "USA", "name": "MLS", "id": "mls",
     "alt_names": ["major league soccer"]},
    {"country": "Colombia", "name": "Categoria Primera A", "id": "colombian-primera-a",
     "alt_names": ["liga betplay", "primera a", "categoría primera a", "colombia categoria primera a", "campeonato colombiano"]},
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
    # SPAIN
    "la-liga": 140,
    # ITALY
    "serie-a": 135,
    "serie-b": 136,
    # GERMANY
    "bundesliga": 78,
    "2-bundesliga": 79,
    # FRANCE
    "ligue-1": 61,
    # BRAZIL
    "brasileirao-serie-a": 71,
    "brasileirao-serie-b": 72,
    # NETHERLANDS
    "eredivisie": 88,
    # PORTUGAL
    "primeira-liga": 94,
    # TURKEY
    "super-lig": 203,
    # BELGIUM
    "pro-league": 144,
    # SCOTLAND
    "premiership": 179,
    # DENMARK
    "superliga": 120,
    # ARGENTINA
    "primera-division": 128,
    # AUSTRALIA
    "a-league": 188,
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
    # USA (Feb-Dec)
    "mls",
    # COLOMBIA (Feb-Dec)
    "colombian-primera-a",
    # AUSTRALIA (Oct-May, but API-Football uses start year = calendar year)
    "a-league",
    # MEXICO (Apertura/Clausura, but API-Football uses calendar year)
    "liga-mx",
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


# ─── #166 — API-Football Odds Ingestion v2 ──────────────────────────────
# Per-league bookmaker priority for odds extraction. Keys are internal slugs
# (same as LEAGUES_CONFIG['id']). Regional coverage matters for Latin leagues
# where Bet365/Pinnacle don't consistently publish O/U goals.
PRIORITY_BOOKMAKERS: dict[str, list[str]] = {
    "default":               ["bet365", "pinnacle", "1xbet", "betfair", "unibet"],
    "mls":                   ["draftkings", "fanduel", "caesars", "bet365", "pinnacle"],
    "brasileirao-serie-a":   ["betano", "bet365", "1xbet", "pinnacle", "sportingbet"],
    "brasileirao-serie-b":   ["betano", "bet365", "1xbet", "pinnacle"],
    "liga-mx":               ["1xbet", "bet365", "caliente", "pinnacle"],
    "primera-division":      ["1xbet", "bet365", "pinnacle"],       # Argentina
    "colombian-primera-a":   ["1xbet", "bet365", "betplay", "pinnacle"],
}

# API-Football numeric bet ID → internal market key.
# Intentionally left EMPTY until validated via `curl /odds/bets` with a live
# API key. Name matching remains the primary identifier. Unknown IDs (any
# non-empty ID absent from this map) are logged as warnings so we can
# populate the map from real API data rather than from guessed values.
BET_ID_MAP: dict[int, str] = {}


def get_priority_bookmakers(league_id: str | None) -> list[str]:
    """Return per-league bookmaker priority. Falls back to default."""
    if not league_id:
        return PRIORITY_BOOKMAKERS["default"]
    resolved = LEAGUE_ID_ALIASES.get(league_id, league_id)
    return PRIORITY_BOOKMAKERS.get(resolved, PRIORITY_BOOKMAKERS["default"])
