from ..places import format_places
from ..places import search_places


def search_destinations(query: str) -> str:
    """Find saved destinations by city, country, or trip style.

    Use this before recommending places. Copy place_id exactly from the
    results. A destination that is not listed here cannot be shown as a card.

    Args:
        query: City, country, region, or features such as beach, safari, or alps.

    Returns:
        Matching place_id lines, or a note that nothing matched.
    """
    return format_places(search_places(query))
