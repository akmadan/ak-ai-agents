from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from .places import PLACES_BY_ID


class RecommendedPlace(BaseModel):
    """One catalog destination the UI can turn into a card."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(
        description=(
            "Exact place_id copied from search_destinations. Never invent an id."
        )
    )

    @field_validator("place_id")
    @classmethod
    def known_place(cls, value: str) -> str:
        if value not in PLACES_BY_ID:
            raise ValueError(
                "Unknown place_id. Call search_destinations and copy place_id exactly."
            )
        return value
    blurb: str = Field(
        description=(
            "Why this place fits the trip, the suitable season, a rough trip "
            "shape, and what would make it a poor fit. Cite sources used."
        )
    )


class DestinationRecommendations(BaseModel):
    """Structured result from destination_research."""

    model_config = ConfigDict(extra="forbid")

    places: list[RecommendedPlace] = Field(
        min_length=1,
        max_length=4,
        description="Catalog destinations to show as cards, best fit first.",
    )
    assumptions: str = Field(
        description=(
            "Details that were missing and what you assumed. Mention catalog "
            "places you considered and skipped."
        )
    )
