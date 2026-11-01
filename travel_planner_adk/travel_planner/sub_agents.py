from google.adk.agents import Agent

from .prompts import BUDGET_INSTRUCTION
from .prompts import DESTINATION_INSTRUCTION
from .prompts import ITINERARY_INSTRUCTION
from .schemas import DestinationRecommendations
from .tools import search_destinations
from .tools import search_web

destination_research = Agent(
    name="destination_research",
    mode="task",
    description=(
        "Recommends destinations from the place catalog. Returns JSON with "
        "place_id values the app can match to saved images."
    ),
    instruction=DESTINATION_INSTRUCTION,
    output_schema=DestinationRecommendations,
    output_key="destination_recommendations",
    tools=[search_destinations, search_web],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

itinerary_planning = Agent(
    name="itinerary_planning",
    mode="task",
    description=(
        "Builds a day-by-day plan for one destination, including attractions, "
        "meals, and pacing."
    ),
    instruction=ITINERARY_INSTRUCTION,
    tools=[search_web],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

budget_feasibility = Agent(
    name="budget_feasibility",
    mode="task",
    description=(
        "Estimates trip cost ranges, checks them against the budget, and "
        "flags practical problems."
    ),
    instruction=BUDGET_INSTRUCTION,
    tools=[search_web],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
