import requests
import os
import json
import logging
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger("sportsbank.footstats")

class FootyStatsClient:
    """Cliente para integração com a API FootyStats (football-data-api.com)."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.football-data-api.com"):
        self.api_key = api_key or os.getenv("FOOTYSTATS_API_KEY", "example")
        self.base_url = base_url
        
        # Configuração de Cache
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.db_path = "/tmp/api_cache.db"
        else:
            self.db_path = "api_cache.db"
        
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados de cache SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    endpoint TEXT,
                    params TEXT,
                    response TEXT,
                    created_at DATETIME,
                    expires_at DATETIME
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao inicializar cache da API: {e}")

    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Gera uma chave única para o cache baseada no endpoint e parâmetros."""
        params_str = json.dumps(params, sort_keys=True)
        key_str = f"{endpoint}:{params_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Busca dados no cache se ainda forem válidos."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT response FROM api_cache WHERE cache_key = ? AND expires_at > ?", 
                (cache_key, datetime.now())
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Erro ao ler cache da API: {e}")
        return None

    def _save_to_cache(self, cache_key: str, endpoint: str, params: Dict[str, Any], response: Dict[str, Any], ttl_minutes: int = 60):
        """Salva a resposta no cache com um tempo de vida (TTL)."""
        try:
            now = datetime.now()
            expires = now + timedelta(minutes=ttl_minutes)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO api_cache (cache_key, endpoint, params, response, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cache_key, endpoint, json.dumps(params), json.dumps(response), now, expires))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar cache da API: {e}")

    def _request(self, endpoint: str, params: Dict[str, Any] = {}, ttl_minutes: int = 60) -> Dict[str, Any]:
        """Realiza a requisição para a API com suporte a cache."""
        params["key"] = self.api_key
        cache_key = self._generate_cache_key(endpoint, params)
        
        # Tenta cache primeiro
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            logger.info(f"Usando dados do cache para {endpoint}")
            return cached_data

        # Se não houver cache, faz a requisição
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                self._save_to_cache(cache_key, endpoint, params, data, ttl_minutes)
                return data
            else:
                logger.error(f"Erro na resposta da API FootyStats: {data.get('message', 'Erro desconhecido')}")
                return {"success": False, "message": data.get("message")}
                
        except Exception as e:
            logger.error(f"Falha na requisição para {endpoint}: {e}")
            return {"success": False, "error": str(e)}

    def get_league_list(self, chosen_only: bool = True) -> Dict[str, Any]:
        """Retorna a lista de ligas disponíveis."""
        params = {"chosen_leagues_only": "true" if chosen_only else "false"}
        return self._request("league-list", params, ttl_minutes=1440) # Cache de 24h

    def get_league_matches(self, season_id: int, page: int = 1) -> Dict[str, Any]:
        """Retorna todas as partidas de uma temporada específica."""
        params = {"season_id": season_id, "page": page}
        return self._request("league-matches", params, ttl_minutes=120) # Cache de 2h

    def get_todays_matches(self, date: Optional[str] = None, timezone: str = "America/Sao_Paulo") -> Dict[str, Any]:
        """Retorna os jogos do dia (ou de uma data específica)."""
        params = {"timezone": timezone}
        if date:
            params["date"] = date
        return self._request("todays-matches", params, ttl_minutes=30) # Cache de 30min para jogos do dia

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        """Retorna detalhes profundos de uma partida (Lineups, Trends, H2H)."""
        params = {"match_id": match_id}
        return self._request("match", params, ttl_minutes=60)

    def get_league_season_stats(self, season_id: int) -> Dict[str, Any]:
        """Retorna estatísticas agregadas da temporada e times."""
        params = {"season_id": season_id}
        return self._request("league-season", params, ttl_minutes=360) # Cache de 6h

    def get_league_tables(self, season_id: int) -> Dict[str, Any]:
        """Retorna as tabelas de classificação da liga."""
        params = {"league_id": season_id} # O endpoint league-tables usa league_id mas refere-se ao season_id
        return self._request("league-tables", params, ttl_minutes=360)

    def resolve_season_id(self, country: str, league_name: str) -> Optional[int]:
        """Resolve o season_id dinamicamente buscando na lista de ligas da API."""
        leagues_data = self.get_league_list(chosen_only=False)
        if not leagues_data.get("success"):
            return None
            
        for league in leagues_data.get("data", []):
            # A API retorna o nome como "USA MLS" ou "England Premier League"
            api_league_name = league.get("name", "").lower()
            if country.lower() in api_league_name and league_name.lower() in api_league_name:
                # Retorna o ID da temporada mais recente (último da lista)
                seasons = league.get("season", [])
                if seasons:
                    return seasons[-1].get("id")
        return None
