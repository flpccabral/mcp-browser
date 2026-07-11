import os

import httpx


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

    async def chat(self, messages: list[dict]) -> str:
        """Send messages to the LLM and return the response text."""
        if self.provider == "anthropic":
            return await self._chat_anthropic(messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
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

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "system": system.strip(),
                    "messages": chat_messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]


# Singleton instance
llm_client = LLMClient()
