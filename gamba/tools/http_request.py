"""HTTP request tool - fetch any URL."""

from __future__ import annotations

from typing import Any

from gamba.tools.base import BaseTool


class HttpRequestTool(BaseTool):
    name = "http_request"
    description = "Make an HTTP GET or POST request to a URL. Returns the response text."
    inputs = {
        "url": "The URL to request",
        "method": "HTTP method: GET or POST (default GET)",
        "body": "Optional request body for POST",
    }
    output_type = "string"

    def forward(self, url: str, method: str = "GET", body: str = "", **kwargs: Any) -> str:
        import asyncio
        import aiohttp

        async def _fetch() -> str:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "POST":
                    async with session.post(url, data=body, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        text = await resp.text()
                        return f"Status: {resp.status}\n{text[:5000]}"
                else:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        text = await resp.text()
                        return f"Status: {resp.status}\n{text[:5000]}"

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return loop.run_in_executor(pool, lambda: asyncio.run(_fetch()))  # type: ignore
        except RuntimeError:
            return asyncio.run(_fetch())
