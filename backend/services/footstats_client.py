import requests
import os
import json
import logging
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger("sportsbankzu.footstats")

class FootyStatsClient:
    """Cliente para integração com a API FootyStats (football-data-api.com)."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.football-data-api.com"):
        self.api_key = api_key or os.getenv("FOOTYSTATS_API_KEY", "example")
        if self.api_key == "example":
            logger.warning("FootyStatsClient initialized with 'example' API key. Live data will likely fail.")
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

    def _get_from_cache(self, cache_key: str, max_age_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Busca dados no cache se ainda forem válidos.

        Args:
            cache_key: chave do cache
            max_age_minutes: se fornecido, rejeita entradas mais velhas que este valor
                             (mesmo que expires_at ainda não tenha passado).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if max_age_minutes is not None:
                # Respeita o TTL solicitado pelo chamador, não apenas o TTL original
                min_created = datetime.now() - timedelta(minutes=max_age_minutes)
                cursor.execute(
                    "SELECT response FROM api_cache WHERE cache_key = ? AND expires_at > ? AND created_at > ?",
                    (cache_key, datetime.now(), min_created)
                )
            else:
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

    # HTTP status codes that warrant an automatic retry
    _RETRYABLE_STATUS_CODES = {502, 503, 504, 429}

    def _request(self, endpoint: str, params: Dict[str, Any] = {}, ttl_minutes: int = 60, timeout: int = 15) -> Dict[str, Any]:
        """Realiza a requisição para a API com suporte a cache e retry automático."""
        params["key"] = self.api_key
        cache_key = self._generate_cache_key(endpoint, params)

        # Tenta cache primeiro (respeitando o TTL solicitado pelo chamador)
        cached_data = self._get_from_cache(cache_key, max_age_minutes=ttl_minutes)
        if cached_data:
            logger.info(f"Usando dados do cache para {endpoint}")
            return cached_data

        # Se não houver cache, faz a requisição (com 1 retry automático para erros transientes)
        url = f"{self.base_url}/{endpoint}"
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                t0 = time.monotonic()
                response = requests.get(url, params=params, timeout=timeout)
                elapsed_ms = int((time.monotonic() - t0) * 1000)

                if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < max_attempts:
                    logger.warning(
                        f"[{endpoint}] HTTP {response.status_code} (attempt {attempt}/{max_attempts}, {elapsed_ms}ms) — retrying in 2s"
                    )
                    time.sleep(2)
                    continue

                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    self._save_to_cache(cache_key, endpoint, params, data, ttl_minutes)
                    logger.info(f"[{endpoint}] OK ({elapsed_ms}ms, attempt {attempt})")
                    return data
                else:
                    logger.warning(
                        f"[{endpoint}] success=False (HTTP {response.status_code}, {elapsed_ms}ms): {data.get('message', 'unknown')}"
                    )
                    return {"success": False, "message": data.get("message")}

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"[{endpoint}] Timeout after {timeout}s (attempt {attempt}/{max_attempts})")
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(f"[{endpoint}] Connection error (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else "?"
                logger.error(f"[{endpoint}] HTTP {status} error: {e}")
                break  # Non-retryable HTTP error
            except Exception as e:
                last_error = e
                logger.error(f"[{endpoint}] Unexpected error (attempt {attempt}/{max_attempts}): {e}", exc_info=True)
                break

        logger.error(f"[{endpoint}] Failed after {max_attempts} attempts: {last_error}")
        return {"success": False, "error": str(last_error)}

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

    def get_live_scores(self, timezone: str = "America/Sao_Paulo") -> Dict[str, Any]:
        """Retorna jogos do dia com cache curto (1 min) para placares ao vivo."""
        params = {"timezone": timezone}
        return self._request("todays-matches", params, ttl_minutes=1)  # Cache de 1 min para live scores

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        """Retorna detalhes profundos de uma partida (Lineups, Trends, H2H)."""
        params = {"match_id": match_id}
        return self._request("match", params, ttl_minutes=60)

    def get_league_season_stats(self, season_id: int) -> Dict[str, Any]:
        """Retorna estatísticas agregadas da temporada e times."""
        params = {"season_id": season_id}
        return self._request("league-season", params, ttl_minutes=360) # Cache de 6h

    def get_league_teams(self, season_id: int, include_stats: bool = True) -> Dict[str, Any]:
        """Retorna os times de uma temporada com estatísticas agregadas (cards, fouls, shots, etc.)."""
        params = {"season_id": season_id}
        if include_stats:
            params["include"] = "stats"
        # Longer timeout: this endpoint returns heavy payload with all team stats
        return self._request("league-teams", params, ttl_minutes=360, timeout=20)  # Cache de 6h

    def get_league_tables(self, season_id: int) -> Dict[str, Any]:
        """Retorna as tabelas de classificação da liga."""
        params = {"league_id": season_id} # O endpoint league-tables usa league_id mas refere-se ao season_id
        return self._request("league-tables", params, ttl_minutes=360)

    # Suffixes that indicate cup/reserve/youth/playoff competitions.
    # Used by resolve_season_id to deprioritize these when looking for the main league.
    _CUP_SUFFIXES = ("cup", "playoff", "play-off", "play off", "reserve", "u19", "u21", "women", "super cup")

    def resolve_season_id(self, country: str, league_name: str, alt_names: Optional[List[str]] = None) -> Optional[int]:
        """Resolve o season_id dinamicamente buscando na lista de ligas da API.
        Tries the primary league_name first, then alt_names for leagues with
        multiple possible API names (e.g. Portugal: Primeira Liga / Liga NOS / Liga Portugal).

        Deprioritizes cup/reserve/youth competitions to avoid false matches
        (e.g. "J-League Cup" when looking for "J1 League")."""
        leagues_data = self.get_league_list(chosen_only=False)
        if not leagues_data.get("success"):
            logger.warning(f"resolve_season_id: league-list API failed for {country}/{league_name}")
            return None

        names_to_try = [league_name.lower()]
        if alt_names:
            names_to_try.extend(n.lower() for n in alt_names)

        country_lower = country.lower()
        best_match = None  # (season_id, api_league_name, is_cup)

        for league in leagues_data.get("data", []):
            api_league_name = league.get("name", "").lower()
            if country_lower not in api_league_name:
                continue
            for name in names_to_try:
                if name in api_league_name:
                    seasons = league.get("season", [])
                    if not seasons:
                        continue
                    sid = seasons[-1].get("id")
                    is_cup = any(s in api_league_name for s in self._CUP_SUFFIXES)

                    # Prefer non-cup matches; if we already have a non-cup match, skip cups
                    if best_match is not None:
                        if best_match[2] and not is_cup:
                            # Current best is a cup, this is not — upgrade
                            best_match = (sid, api_league_name, is_cup)
                        # Otherwise keep the first non-cup match
                    else:
                        best_match = (sid, api_league_name, is_cup)

                    # If we found a non-cup match, no need to keep searching
                    if not is_cup:
                        break
            # If we already have a non-cup match, stop iterating leagues
            if best_match and not best_match[2]:
                break

        if best_match:
            logger.info(f"resolve_season_id: {country}/{league_name} -> '{best_match[1]}' season_id={best_match[0]}")
            return best_match[0]

        logger.warning(f"resolve_season_id: no match for {country} with names {names_to_try}")
        return None
