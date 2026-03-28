"""Ollama provider - local LLM via HTTP."""

from __future__ import annotations

import aiohttp

from gamba.providers.base import BaseProvider, LLMResponse

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = DEFAULT_URL, default_model: str = DEFAULT_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        session = await self._get_session()
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with session.post(f"{self.base_url}/api/chat", json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {body}")
            data = await resp.json()
            return LLMResponse(
                text=data["message"]["content"],
                usage={},
                model=data.get("model", model),
                raw=data,
            )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
