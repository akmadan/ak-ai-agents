import os
from typing import Any

from pydantic import BaseModel

from .places import PLACES_BY_ID


class PlaceCard(BaseModel):
    """A destination card for a UI client."""

    place_id: str
    name: str
    country: str
    blurb: str
    image_url: str | None = None


def image_url_for(place_id: str) -> str | None:
    """Object-storage URL for a catalog id.

    Set PLACE_IMAGE_BASE_URL to the public prefix. The object name is
    ``{place_id}.jpg``.
    """
    base = os.getenv("PLACE_IMAGE_BASE_URL", "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/{place_id}.jpg"


def cards_from_payload(payload: dict[str, Any]) -> list[PlaceCard]:
    """Turn a destination_research result into cards the UI can render."""
    places = payload.get("places")
    if not isinstance(places, list):
        return []

    cards: list[PlaceCard] = []
    seen: set[str] = set()
    for item in places:
        if not isinstance(item, dict):
            continue
        place_id = item.get("place_id")
        if not isinstance(place_id, str) or place_id in seen:
            continue
        place = PLACES_BY_ID.get(place_id)
        if place is None:
            continue
        seen.add(place_id)
        blurb = item.get("blurb")
        cards.append(
            PlaceCard(
                place_id=place.id,
                name=place.name,
                country=place.country,
                blurb=blurb if isinstance(blurb, str) else "",
                image_url=image_url_for(place.id),
            )
        )
    return cards
