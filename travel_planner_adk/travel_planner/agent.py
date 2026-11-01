import os

from google.adk.agents import Agent

from .prompts import SUPERVISOR_INSTRUCTION
from .sub_agents import budget_feasibility
from .sub_agents import destination_research
from .sub_agents import itinerary_planning

root_agent = Agent(
    name="travel_planner",
    model=os.getenv("AGENT_MODEL", "gemini-flash-latest"),
    description=(
        "Plans a trip by delegating to destination, itinerary, and budget "
        "specialists."
    ),
    instruction=SUPERVISOR_INSTRUCTION,
    sub_agents=[
        destination_research,
        itinerary_planning,
        budget_feasibility,
    ],
)
