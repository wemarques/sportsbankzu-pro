import os
import json
import logging
import time
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
try:
    from mistralai import Mistral
except Exception:
    Mistral = None

logger = logging.getLogger("sportsbankzu.ai.client")

# Transient HTTP status codes that warrant a retry
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds
_SDK_TIMEOUT = 60  # seconds — avoid cold-start timeouts on Lambda


class MistralClient:
    def __init__(self, model: str = "mistral-small-latest"):
        if load_dotenv:
            load_dotenv()
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.model = model
        self.client = Mistral(api_key=self.api_key, timeout_ms=_SDK_TIMEOUT * 1000) if (self.api_key and Mistral) else None

    def _fix_mojibake(self, text: str) -> str:
        if not text:
            return text
        if "�" in text or "Ã" in text:
            try:
                return text.encode("latin1").decode("utf-8")
            except Exception:
                return text
        return text

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if an exception is a transient error worth retrying."""
        exc_str = str(exc).lower()
        if "timeout" in exc_str or "timed out" in exc_str:
            return True
        if "connection" in exc_str and ("reset" in exc_str or "refused" in exc_str or "error" in exc_str):
            return True
        for code in _RETRYABLE_STATUSES:
            if str(code) in exc_str:
                return True
        return False

    def chat_complete(self, messages, temperature: float = 0.3, max_tokens: int = 1000) -> str:
        if self.client is None:
            # Fallback mock mais completo e condizente com as novas instruções
            return json.dumps({
                "injuries_key_players": {"home": "Sem dados", "away": "Sem dados"},
                "pressure_level": {"home": "MEDIA", "away": "MEDIA"},
                "tactical_insight": "Aguardando conexão com Mistral API.",
                "confidence_adjustment": {"recommendation": "MANTER", "reason": "Modo offline.", "impact_percentage": 0},
                "independent_prediction": {"total_goals_estimate": 0.0, "reasoning": "Offline."}
            })

        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                r = self.client.chat.complete(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return self._fix_mojibake(r.choices[0].message.content)
            except Exception as e:
                last_exc = e
                if self._is_retryable(e) and attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(f"[MistralClient] Transient error (attempt {attempt + 1}/{_MAX_RETRIES}): {e}. Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    raise

        raise last_exc  # type: ignore[misc]

    def simple_prompt(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 4000) -> str:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return self.chat_complete(msgs, max_tokens=max_tokens)
