import re
import requests
import os
import json
import logging
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("sportsbankzu.footstats")

_KEY_QS_RE = re.compile(r'([?&])key=[^&\s"\']+', re.IGNORECASE)


def _redact_key(text: Any) -> str:
    """Mascara qualquer ?key=... ou &key=... em strings (ex: URLs em mensagens de exceção do requests)."""
    if text is None:
        return ""
    return _KEY_QS_RE.sub(r'\1key=***REDACTED***', str(text))

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

    def _open_db(self) -> sqlite3.Connection:
        """Open SQLite connection with WAL mode and busy timeout (#119d)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        """Inicializa o banco de dados de cache SQLite."""
        try:
            conn = self._open_db()
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
            conn = self._open_db()
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
            conn = self._open_db()
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
        # Strip internal cache namespace param before sending to API
        params.pop("_cache_ns", None)

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
                    try:
                        from backend.services.reliability_tracker import track_api_call
                        track_api_call("footystats", True)
                    except Exception:
                        pass
                    return data
                else:
                    msg = data.get("message", "unknown")
                    is_auth = any(kw in str(msg).lower() for kw in (
                        "key", "subscription", "expired", "invalid", "unauthorized", "forbidden",
                        "payment", "plan", "quota", "limit exceeded", "access denied",
                    ))
                    if is_auth:
                        logger.error(
                            f"[{endpoint}] AUTH/PAYMENT issue (HTTP {response.status_code}, {elapsed_ms}ms): {msg}. "
                            "Check FOOTYSTATS_API_KEY and subscription at football-data-api.com"
                        )
                        return {"success": False, "auth_error": True, "message": msg}
                    logger.warning(
                        f"[{endpoint}] success=False (HTTP {response.status_code}, {elapsed_ms}ms): {msg}"
                    )
                    return {"success": False, "message": msg}

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"[{endpoint}] Timeout after {timeout}s (attempt {attempt}/{max_attempts})")
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(f"[{endpoint}] Connection error (attempt {attempt}/{max_attempts}): {_redact_key(e)}")
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else "?"
                logger.error(f"[{endpoint}] HTTP {status} error: {_redact_key(e)}")
                break  # Non-retryable HTTP error
            except Exception as e:
                last_error = e
                logger.error(f"[{endpoint}] Unexpected error (attempt {attempt}/{max_attempts}): {_redact_key(e)}", exc_info=False)
                break

        logger.error(f"[{endpoint}] Failed after {max_attempts} attempts: {_redact_key(last_error)}")
        try:
            from backend.services.reliability_tracker import track_api_call
            track_api_call("footystats", False)
        except Exception:
            pass
        return {"success": False, "error": _redact_key(last_error)}

    def get_league_list(self, chosen_only: bool = True) -> Dict[str, Any]:
        """Retorna a lista de ligas disponíveis."""
        params = {"chosen_leagues_only": "true" if chosen_only else "false"}
        return self._request("league-list", params, ttl_minutes=1440) # Cache de 24h

    def get_league_matches(self, season_id: int, page: int = 1) -> Dict[str, Any]:
        """Retorna uma página de partidas de uma temporada. Preferir get_all_league_matches()."""
        params = {"season_id": season_id, "page": page}
        return self._request("league-matches", params, ttl_minutes=120)  # Cache de 2h

    # ── #154 — Paginação completa de league-matches ──────────────
    _all_matches_cache: Dict[int, Tuple[float, list]] = {}
    _ALL_MATCHES_CACHE_TTL = 900  # 15 minutos

    def get_all_league_matches(self, season_id: int, max_per_page: int = 1000, max_pages: int = 10) -> Dict[str, Any]:
        """Busca TODAS as páginas de league-matches para uma temporada (#154).

        Usa max_per_page=1000 (máximo da API) para minimizar calls.
        Safety cap de max_pages evita loop infinito.
        Retorna dict compatível com get_league_matches: {"success": True, "data": [...]}.
        """
        # ── In-memory cache (sobrevive entre invocations no mesmo Lambda container) ──
        now = time.monotonic()
        cached = self._all_matches_cache.get(season_id)
        if cached:
            ts, matches = cached
            if now - ts < self._ALL_MATCHES_CACHE_TTL:
                logger.debug(f"[league-matches-all] CACHE HIT season={season_id} ({len(matches)} matches)")
                return {"success": True, "data": matches}

        all_matches: list = []
        page = 1

        while page <= max_pages:
            params = {"season_id": season_id, "page": page, "max_per_page": max_per_page}
            response = self._request("league-matches", params, ttl_minutes=120, timeout=20)

            if not response.get("success"):
                # Se page 1 falhou, retorna erro; se page N>1 falhou, retorna o que temos
                if page == 1:
                    return response
                logger.warning(f"[league-matches-all] season={season_id} page={page} failed, returning {len(all_matches)} matches from pages 1-{page-1}")
                break

            data = response.get("data", [])
            all_matches.extend(data)

            pager = response.get("pager", {})
            max_page = pager.get("max_page", 1)

            logger.info(
                f"[league-matches-all] season={season_id} page={page}/{max_page} "
                f"fetched={len(data)} total_so_far={len(all_matches)}"
            )

            if page >= max_page or len(data) == 0:
                break
            page += 1

        # Cache em memória
        self._all_matches_cache[season_id] = (now, all_matches)
        logger.info(f"[league-matches-all] season={season_id} DONE: {len(all_matches)} matches in {page} page(s)")
        return {"success": True, "data": all_matches}

    def get_todays_matches(self, date: Optional[str] = None, timezone: str = "America/Sao_Paulo") -> Dict[str, Any]:
        """Retorna os jogos do dia (ou de uma data específica)."""
        params = {"timezone": timezone}
        if date:
            params["date"] = date
        return self._request("todays-matches", params, ttl_minutes=5) # Cache de 5min (reduzido de 30min para placares ao vivo)

    def get_live_scores(self, timezone: str = "America/Sao_Paulo") -> Dict[str, Any]:
        """Retorna jogos do dia com cache curto (30s) para placares ao vivo."""
        params = {"timezone": timezone}
        return self._request("todays-matches", params, ttl_minutes=0.5)  # Cache de 30s para live scores

    def get_match_details(self, match_id: int) -> Dict[str, Any]:
        """Retorna detalhes profundos de uma partida (Lineups, Trends, H2H)."""
        params = {"match_id": match_id}
        return self._request("match", params, ttl_minutes=60)

    def get_match_live_details(self, match_id: int) -> Dict[str, Any]:
        """Retorna detalhes de uma partida com cache curto (30s) para scores ao vivo.

        Uses a separate cache key suffix ('_live') to avoid collision with
        get_match_details() which caches the same endpoint for 60 minutes.
        Without this separation, a pre-match detail fetch would serve stale
        0-0 scores for up to 60 minutes during a live match.
        """
        params = {"match_id": match_id, "_cache_ns": "live"}
        return self._request("match", params, ttl_minutes=0.5)  # Cache de 30s

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

    # ==================================================================
    # #141 — League Referees
    # ==================================================================
    def get_league_referees(self, season_id: int, ttl_minutes: int = 1440) -> Dict[str, Any]:
        """Retorna a lista de árbitros da liga + estatísticas (cards/fouls/etc.).

        Endpoint FootyStats `/league-referees`. ~65 datapoints por árbitro:
        appearances, yellow_cards_overall, red_cards_overall, fouls_per_game,
        cards_per_game_overall, etc.

        Cache padrão: 24h (lista muda raramente; stats atualizadas diariamente).
        """
        params = {"season_id": season_id}
        return self._request("league-referees", params, ttl_minutes=ttl_minutes)

    # ==================================================================
    # #142 — Team Last X (recent form)
    # ==================================================================
    def get_team_lastx(self, team_id: int, ttl_minutes: int = 120) -> Dict[str, Any]:
        """Retorna últimas 5/6/10 partidas de uma equipa com stats agregadas.

        Endpoint FootyStats `/lastx`. Retorna 3 buckets por equipa:
        last_5, last_6, last_10 — cada um com goals/cards/corners/xg médios.

        Fonte canónica para forma recente. Mais preciso e mais barato do
        que filtrar `league-matches` por equipa (#108c).

        Cache padrão: 2h (forma muda lentamente; valores agregados de N jogos).
        """
        params = {"team_id": team_id}
        return self._request("lastx", params, ttl_minutes=ttl_minutes)

    # Suffixes that indicate cup/reserve/youth/playoff competitions.
    # Used by resolve_season_id to deprioritize these when looking for the main league.
    _CUP_SUFFIXES = ("cup", "playoff", "play-off", "play off", "reserve", "u19", "u21", "women", "super cup")

    def resolve_season_id(self, country: str, league_name: str, alt_names: Optional[List[str]] = None) -> Optional[int]:
        """Resolve o season_id dinamicamente buscando na lista de ligas da API.
        Tries the primary league_name first, then alt_names for leagues with
        multiple possible API names (e.g. Portugal: Primeira Liga / Liga NOS / Liga Portugal).

        Deprioritizes cup/reserve/youth competitions to avoid false matches
        (e.g. "J-League Cup" when looking for "J1 League")."""
        result = self.resolve_season_ids(country, league_name, alt_names=alt_names, n_seasons=1)
        if result:
            return result[0][0]
        return None

    def resolve_season_ids(
        self,
        country: str,
        league_name: str,
        alt_names: Optional[List[str]] = None,
        n_seasons: int = 3,
    ) -> List[Tuple[int, str]]:
        """Resolve up to n_seasons season IDs for a league, most recent first.

        Returns a list of (season_id, api_league_name) tuples ordered from
        newest to oldest.  If the league has fewer seasons than requested,
        returns whatever is available.

        Args:
            country: Country name (e.g. "England")
            league_name: Primary league name
            alt_names: Alternative league names to try
            n_seasons: Number of historical seasons to return (default 3)
        """
        leagues_data = self.get_league_list(chosen_only=False)
        if not leagues_data.get("success"):
            logger.warning(f"resolve_season_ids: league-list API failed for {country}/{league_name}")
            return []

        names_to_try = [league_name.lower()]
        if alt_names:
            names_to_try.extend(n.lower() for n in alt_names)

        country_lower = country.lower()
        best_match = None  # (seasons_list, api_league_name, is_cup)

        for league in leagues_data.get("data", []):
            api_league_name = league.get("name", "").lower()
            if country_lower not in api_league_name:
                continue
            for name in names_to_try:
                if name in api_league_name:
                    seasons = league.get("season", [])
                    if not seasons:
                        continue
                    # Get last n_seasons season IDs (most recent last in API → reverse)
                    recent = seasons[-n_seasons:] if len(seasons) >= n_seasons else seasons
                    season_ids = [s.get("id") for s in recent if s.get("id")]
                    season_ids.reverse()  # most recent first

                    is_cup = any(s in api_league_name for s in self._CUP_SUFFIXES)

                    if best_match is not None:
                        if best_match[2] and not is_cup:
                            best_match = (season_ids, api_league_name, is_cup)
                    else:
                        best_match = (season_ids, api_league_name, is_cup)

                    if not is_cup:
                        break
            if best_match and not best_match[2]:
                break

        if best_match:
            result = [(sid, best_match[1]) for sid in best_match[0]]
            logger.info(
                f"resolve_season_ids: {country}/{league_name} -> '{best_match[1]}' "
                f"seasons={[r[0] for r in result]}"
            )
            return result

        logger.warning(f"resolve_season_ids: no match for {country} with names {names_to_try}")
        return []
