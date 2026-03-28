"""Video search tool - searches YouTube via DuckDuckGo videos."""

from __future__ import annotations

from typing import Any

from gamba.tools.base import BaseTool


class VideoSearchTool(BaseTool):
    name = "video_search"
    description = "Search for videos on YouTube and other platforms. Returns titles, URLs, durations, and descriptions."
    inputs = {"query": "The search query", "max_results": "Maximum results (default 5)"}
    output_type = "string"

    def forward(self, query: str, max_results: int = 5, **kwargs: Any) -> str:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return "Error: duckduckgo-search not installed. Run: pip install duckduckgo-search"

        results = []
        with DDGS() as ddgs:
            for r in ddgs.videos(query, max_results=max_results):
                title = r.get("title", "Untitled")
                url = r.get("content", r.get("embed_url", ""))
                duration = r.get("duration", "")
                publisher = r.get("publisher", "")
                desc = r.get("description", "")[:150]
                line = f"**{title}**"
                if publisher:
                    line += f" [{publisher}]"
                if duration:
                    line += f" ({duration})"
                if url:
                    line += f"\n{url}"
                if desc:
                    line += f"\n{desc}"
                results.append(line + "\n")

        if not results:
            return f"No videos found for: {query}"
        return "\n".join(results)
