from langchain_core.tools import tool
from tavily import TavilyClient

from config import TAVILY_API_KEY, WEB_TOP_K


@tool
def search_web(query: str) -> str:
    """Search the public web for general medical background.

    Use this to explain a term or fill a gap the user's report does not cover.
    Do not treat web results as the user's personal lab values or history.
    """
    if not TAVILY_API_KEY:
        return "Web search is unavailable because TAVILY_API_KEY is not set."
    try:
        response = TavilyClient(api_key=TAVILY_API_KEY).search(
            query=query,
            max_results=WEB_TOP_K,
        )
    except Exception as exc:
        return f"Web search failed: {exc}"

    results = response.get("results") or []
    if not results:
        return "No web results found."

    parts = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or ""
        content = (item.get("content") or "").strip()
        parts.append(f"[{index}] {title}\n{url}\n{content}")
    return "\n\n".join(parts)
