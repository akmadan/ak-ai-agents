from fastmcp import FastMCP

from places import format_places
from places import search_places

mcp = FastMCP("place-catalog")


@mcp.tool
def search_destinations(query: str) -> str:
    """Find saved destinations by city, country, or trip style.

    Use this before recommending places. Copy place_id exactly from the
    results. A destination that is not listed here cannot be shown as a card.

    Args:
        query: City, country, region, or features such as beach, safari, or alps.
    """
    return format_places(search_places(query))


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
