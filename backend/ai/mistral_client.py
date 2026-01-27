import os
import json
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
try:
    from mistralai import Mistral
except Exception:
    Mistral = None

class MistralClient:
    def __init__(self, model: str = "mistral-medium-latest"):
        if load_dotenv:
            load_dotenv()
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.model = model
        self.client = Mistral(api_key=self.api_key) if (self.api_key and Mistral) else None

    def _fix_mojibake(self, text: str) -> str:
        if not text:
            return text
        if "�" in text or "Ã" in text:
            try:
                return text.encode("latin1").decode("utf-8")
            except Exception:
                return text
        return text

    def chat_complete(self, messages, temperature: float = 0.3, max_tokens: int = 600) -> str:
        if self.client is None:
            return json.dumps({
                "injuries_key_players": {"home": None, "away": None},
                "pressure_level": {"home": "BAIXA", "away": "ALTA"},
                "confidence_adjustment": {"recommendation": "MANTER", "reason": "stub"}
            })
        r = self.client.chat.complete(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return self._fix_mojibake(r.choices[0].message.content)

    def simple_prompt(self, prompt: str, system_prompt: str | None = None) -> str:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return self.chat_complete(msgs)
