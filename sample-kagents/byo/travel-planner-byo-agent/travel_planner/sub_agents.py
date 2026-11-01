import os

from google.adk.agents import Agent

from .prompts import BUDGET_INSTRUCTION
from .prompts import DESTINATION_INSTRUCTION
from .prompts import ITINERARY_INSTRUCTION
from .schemas import DestinationRecommendations
from .tools import search_destinations
from .tools import search_web

_MODEL = os.getenv("AGENT_MODEL", "gemini-2.5-flash")

destination_research = Agent(
    name="destination_research",
    model=_MODEL,
    description=(
        "Recommends destinations from the place catalog. Returns JSON with "
        "place_id values the app can match to saved images."
    ),
    instruction=DESTINATION_INSTRUCTION,
    output_schema=DestinationRecommendations,
    output_key="destination_recommendations",
    tools=[search_destinations, search_web],
)

itinerary_planning = Agent(
    name="itinerary_planning",
    model=_MODEL,
    description=(
        "Builds a day-by-day plan for one destination, including attractions, "
        "meals, and pacing."
    ),
    instruction=ITINERARY_INSTRUCTION,
    tools=[search_web],
)

budget_feasibility = Agent(
    name="budget_feasibility",
    model=_MODEL,
    description=(
        "Estimates trip cost ranges, checks them against the budget, and "
        "flags practical problems."
    ),
    instruction=BUDGET_INSTRUCTION,
    tools=[search_web],
)
