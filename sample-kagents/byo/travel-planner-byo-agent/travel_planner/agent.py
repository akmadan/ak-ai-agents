import os

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from .prompts import SUPERVISOR_INSTRUCTION
from .sub_agents import budget_feasibility
from .sub_agents import destination_research
from .sub_agents import itinerary_planning

root_agent = Agent(
    name="travel_planner",
    model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
    description=(
        "Plans a trip by delegating to destination, itinerary, and budget "
        "specialists."
    ),
    instruction=SUPERVISOR_INSTRUCTION,
    tools=[
        AgentTool(agent=destination_research),
        AgentTool(agent=itinerary_planning),
        AgentTool(agent=budget_feasibility),
    ],
)
