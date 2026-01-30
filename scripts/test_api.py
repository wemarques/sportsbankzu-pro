import os
from dotenv import load_dotenv
from backend.services.footstats_client import FootyStatsClient

def test_connection():
    load_dotenv("backend/.env")
    client = FootyStatsClient()
    print("Testando conexão com FootyStats API...")
    
    result = client.get_league_list(chosen_only=False)
    
    if result.get("success"):
        leagues = result.get("data", [])
        print(f"Sucesso! Conexão estabelecida. Total de ligas encontradas: {len(leagues)}")
        # Testar resolução de uma liga específica da nossa lista
        season_id = client.resolve_season_id("Brazil", "Serie A")
        print(f"Resolução de liga (Brazil Serie A): Season ID = {season_id}")
    else:
        print(f"Erro na conexão: {result.get('error') or result.get('message')}")

if __name__ == "__main__":
    test_connection()
