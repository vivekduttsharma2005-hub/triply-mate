"""Tavily web search. Returns structured results so sources can be shown in the final plan."""
import os

from observability import log

_client = None


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient

        _client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _client


def tavily_search(query: str, max_results: int = 5) -> dict:
    """-> {"results": [{"title","url","snippet"}], "error": str|None}. Never raises."""
    if not os.getenv("TAVILY_API_KEY"):
        return {"results": [], "error": "Web search is not configured (missing TAVILY_API_KEY)."}
    try:
        response = _get_client().search(query=query, max_results=max_results)
    except Exception as e:
        log.warning("tavily search failed: %s", type(e).__name__)
        return {"results": [], "error": f"Web search failed ({type(e).__name__})."}
    results = []
    for r in response.get("results", []):
        snippet = (r.get("content") or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400].rsplit(" ", 1)[0] + "..."
        results.append({"title": r.get("title") or "Untitled", "url": r.get("url") or "", "snippet": snippet})
    return {"results": results, "error": None}


def format_results(results: list) -> str:
    """Compact text block for an LLM prompt."""
    if not results:
        return "(no results)"
    return "\n\n".join(f"[{i}] {r['title']}\n{r['url']}\n{r['snippet']}" for i, r in enumerate(results, 1))
