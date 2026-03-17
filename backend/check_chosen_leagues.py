import os
import sys
import requests
import json
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

API_KEY = os.getenv("FOOTYSTATS_API_KEY")
BASE_URL = "https://api.footystats.org"

# Season ID que estamos tentando usar
MLS_SEASON_ID = 16504

def verify_chosen_leagues():
    print(f"Verificando se a liga {MLS_SEASON_ID} está na lista de 'chosen leagues'...")
    
    url = f"{BASE_URL}/league-list?key={API_KEY}&chosen_leagues_only=true"
    try:
        response = requests.get(url)
        data = response.json()
        
        if not data.get("success"):
            print(f"Erro na API: {data.get('message')}")
            return

        leagues = data.get("data", [])
        print(f"Total de ligas escolhidas: {len(leagues)}")
        
        found = False
        for l in leagues:
            for s in l.get("season", []):
                if str(s.get("id")) == str(MLS_SEASON_ID):
                    print(f"✅ Liga MLS encontrada! (Season ID: {s.get('id')})")
                    found = True
                    break
        
        if not found:
            print(f"❌ Liga MLS (Season ID {MLS_SEASON_ID}) NÃO está na lista de ligas escolhidas.")
            print("Lista de IDs disponíveis:")
            for l in leagues:
                s_ids = [s.get("id") for s in l.get("season", [])]
                print(f"   - {l.get('name')}: {s_ids}")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    verify_chosen_leagues()
