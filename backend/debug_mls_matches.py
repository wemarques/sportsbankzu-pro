import os
import sys
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

API_KEY = os.getenv("FOOTYSTATS_API_KEY")
BASE_URL = "https://api.footystats.org"

# MLS Season ID from previous check
MLS_SEASON_ID = 16504
TARGET_TEAMS = ["FC Cincinnati", "Portland Timbers", "New York RB", "Los Angeles FC"]

def check_mls_matches():
    print(f"Investigando jogos da MLS (Season ID: {MLS_SEASON_ID})...")
    
    url = f"{BASE_URL}/league-matches?key={API_KEY}&season_id={MLS_SEASON_ID}"
    try:
        response = requests.get(url)
        data = response.json()
        
        if not data.get("success"):
            print(f"Erro na API: {data.get('message')}")
            return

        matches = data.get("data", [])
        print(f"Total de jogos retornados para a temporada: {len(matches)}")
        
        found_count = 0
        print("\n--- Buscando jogos dos times mencionados pelo usuário ---")
        
        # Ordenar por data para facilitar visualização
        matches.sort(key=lambda x: x.get("date_unix", 0))
        
        for m in matches:
            home = m.get("home_name")
            away = m.get("away_name")
            date_str = m.get("date_unix")
            status = m.get("status")
            
            # Converter unix timestamp para data legível
            match_date = datetime.fromtimestamp(date_str)
            date_formatted = match_date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Verificar se é um dos times alvo ou se a data é hoje/ontem/amanhã
            is_target = any(t in home or t in away for t in TARGET_TEAMS)
            
            # Vamos focar nos jogos de Março de 2026
            if match_date.year == 2026 and match_date.month == 3:
                # Se for dia 7, 8 ou 9
                if match_date.day in [7, 8, 9]:
                    print(f"[{date_formatted}] {home} vs {away} (Status: {status})")
                    if is_target:
                        print(f"   >>> JOGO ALVO ENCONTRADO! <<<")
                        found_count += 1

        if found_count == 0:
            print("\nNenhum jogo dos times alvo encontrado nas datas próximas (7, 8, 9 de Março).")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    check_mls_matches()
