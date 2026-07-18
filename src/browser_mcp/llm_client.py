import asyncio
import os
import random

import httpx

# Status HTTP transitórios que valem retry (rate limit + erros de servidor).
# 4xx de auth/validação (400/401/403) NÃO entram — são permanentes.
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 5
_MAX_BACKOFF = 30.0


class LLMClient:
    """Multi-provider LLM client using OpenAI-compatible API format."""

    def __init__(
        self,
        provider: str = None,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", self._default_model())
        self.base_url = base_url or os.getenv("LLM_BASE_URL", self._default_base_url())
        self.max_tokens = max_tokens
        self.temperature = temperature

    def _default_model(self) -> str:
        defaults = {
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.1",
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    def _default_base_url(self) -> str:
        defaults = {
            "deepseek": "https://api.deepseek.com/v1",
            "openai": "https://api.openai.com/v1",
            "ollama": "http://localhost:11434/v1",
        }
        return defaults.get(self.provider, "https://api.openai.com/v1")

    async def initialize(self):
        """No-op para compatibilidade com server.py."""
        pass

    @staticmethod
    def _backoff(attempt: int, response: httpx.Response | None) -> float:
        """Segundos de espera antes do próximo retry.

        Honra o header Retry-After (comum em 429); senão usa backoff exponencial
        com jitter, limitado a _MAX_BACKOFF.
        """
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), _MAX_BACKOFF)
                except ValueError:
                    pass
        return min(2.0**attempt, _MAX_BACKOFF) + random.uniform(0, 0.5)

    async def _request(self, url: str, headers: dict, payload: dict) -> dict:
        """POST com retry + backoff exponencial em 429/5xx/timeout/erro de rede.

        Não faz retry em 4xx de auth/validação (permanentes) — esses propagam
        na primeira tentativa via raise_for_status.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self._backoff(attempt, response))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self._backoff(attempt, None))
                    continue
                raise
        # Só é alcançado se o loop esgotar sem return/raise (não deve ocorrer).
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LLM request falhou após retries sem exceção capturada")

    async def chat(self, messages: list[dict]) -> str:
        """Send messages to the LLM and return the response text."""
        if self.provider == "anthropic":
            return await self._chat_anthropic(messages)

        data = await self._request(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )
        return data["choices"][0]["message"]["content"]

    async def _chat_anthropic(self, messages: list[dict]) -> str:
        """Handle Anthropic's different API format."""
        system = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system += msg["content"] + "\n"
            else:
                chat_messages.append(msg)

        data = await self._request(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            {
                "model": self.model,
                "system": system.strip(),
                "messages": chat_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )
        return data["content"][0]["text"]


# Singleton instance
llm_client = LLMClient()
