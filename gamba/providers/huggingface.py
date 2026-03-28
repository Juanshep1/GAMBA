"""HuggingFace Inference API provider - raw aiohttp."""

from __future__ import annotations

import aiohttp

from gamba.providers.base import BaseProvider, LLMResponse

API_URL = "https://router.huggingface.co/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


class HuggingFaceProvider(BaseProvider):
    def __init__(self, api_token: str, default_model: str = DEFAULT_MODEL) -> None:
        self.api_token = api_token
        self.default_model = default_model
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                }
            )
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
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with session.post(API_URL, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"HuggingFace error {resp.status}: {body}")
            data = await resp.json()
            choice = data["choices"][0]["message"]
            return LLMResponse(
                text=choice["content"],
                usage=data.get("usage", {}),
                model=data.get("model", model),
                raw=data,
            )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
