import os
from tavily import TavilyClient
from dotenv import load_dotenv
load_dotenv()
Client=TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)
from tavily import TavilyClient
import os

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def tavily_search(query):
    response = client.search(
        query=query,
        max_results=5
    )

    results = []

    for i, r in enumerate(response["results"], start=1):
        title = r.get("title", "Unknown")
        url = r.get("url", "")
        snippet = r.get("content", "").strip()

        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ", 1)[0] + "..."

        results.append(
            f"{i}. **{title}**\n"
            f"   {url}\n"
            f"   {snippet}"
        )

    return "\n\n".join(results)