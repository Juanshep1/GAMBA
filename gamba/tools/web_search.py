"""Web search tool using DuckDuckGo (no API key required)."""

from __future__ import annotations

from typing import Any

from gamba.tools.base import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using DuckDuckGo. Returns a list of results with titles, URLs, and snippets."
    inputs = {"query": "The search query string", "max_results": "Maximum results to return (default 5)"}
    output_type = "string"

    def forward(self, query: str, max_results: int = 5, **kwargs: Any) -> str:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return "Error: duckduckgo-search not installed. Run: pip install duckduckgo-search"

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")

        if not results:
            return f"No results found for: {query}"
        return "\n".join(results)
