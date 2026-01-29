import json
import hashlib
import logging
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger("sportsbank.ai.cache")

class CacheManager:
    """Gerencia cache de análises e auditorias para otimizar custos da API Mistral."""
    
    def __init__(self, db_path: str = "ai_cache.db", ttl_hours: int = 24):
        # Usando SQLite local para cache rápido e simples, independente do PostgreSQL de auditoria principal
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            self.db_path = "/tmp/ai_cache.db"
        else:
            self.db_path = db_path
            
        self.ttl = timedelta(hours=ttl_hours)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                cache_key TEXT PRIMARY KEY,
                type TEXT,
                home_team TEXT,
                away_team TEXT,
                response TEXT,
                created_at DATETIME,
                expires_at DATETIME
            )
        """)
        conn.commit()
        conn.close()

    def _generate_key(self, type: str, home: str, away: str) -> str:
        key_str = f"{type}:{home.lower()}:{away.lower()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, type: str, home: str, away: str) -> Optional[Dict[str, Any]]:
        key = self._generate_key(type, home, away)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT response FROM ai_cache WHERE cache_key = ? AND expires_at > ?", (key, datetime.now()))
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Erro ao ler cache: {e}")
        return None

    def set(self, type: str, home: str, away: str, response: Dict[str, Any]):
        key = self._generate_key(type, home, away)
        now = datetime.now()
        expires = now + self.ttl
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ai_cache (cache_key, type, home_team, away_team, response, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (key, type, home, away, json.dumps(response), now, expires))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
