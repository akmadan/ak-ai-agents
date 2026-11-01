import os

from tavily import TavilyClient

_MAX_RESULTS = 5


def search_web(query: str) -> str:
    """Search the public web for current travel information.

    Use this for destination facts, seasons, attractions, restaurants, and
    published price ranges. Snippets are not bookings or live inventory.

    Args:
        query: A specific search query.

    Returns:
        Numbered results with a title, URL, and snippet.
    """
    cleaned = query.strip()
    if not cleaned:
        return "Web search needs a non-empty query."

    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "Web search is unavailable because TAVILY_API_KEY is not set."

    try:
        response = TavilyClient(api_key=api_key).search(
            query=cleaned,
            max_results=_MAX_RESULTS,
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
